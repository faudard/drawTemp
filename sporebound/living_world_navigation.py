"""R35.D1: bounded, collision-aware off-focus NPC walking on authored stages.

Optional NPC stop positions use the *existing* exploration scene geometry.
An NPC with positional stops remains at its previous location until the shortest
route to its next stop must start. It then walks one cardinal cell per world
minute, regardless of camera focus or simulation advance batch size.

Cross-scene travel is NOT interpolated here: a scene handoff still happens at
its scheduled stop. No second navmesh, mutable NPC registry or wall-clock timer.
"""
from __future__ import annotations

from collections import deque

from .model import require

# Stable path tie breaking for equal-length routes on all operating systems.
DIRECTIONS = ((0, -1), (-1, 0), (1, 0), (0, 1))
MAX_STAGE_CELLS = 32 * 32


def _point(value, stage):
    if (type(value) is not list or len(value) != 2
            or any(type(c) is not int for c in value)):
        return False
    x, y = value
    return (0 <= x < stage["width"]
            and 0 <= y < stage["height"]
            and tuple(value) not in {tuple(p) for p in stage["blocked"]})


def shortest_path(stage, start, goal):
    """Return stable 4-neighbour path or None; examine <=1024 grid cells."""
    require(_point(start, stage) and _point(goal, stage),
            "NPC route endpoint is invalid or blocked")
    source, target = tuple(start), tuple(goal)
    if source == target:
        return [list(source)]
    width, height = stage["width"], stage["height"]
    require(width * height <= MAX_STAGE_CELLS, "NPC scene exceeds grid budget")
    blocked = {tuple(p) for p in stage["blocked"]}
    seen = {source: None}
    queue = deque([source])
    while queue:
        current = queue.popleft()
        for dx, dy in DIRECTIONS:
            cell = (current[0] + dx, current[1] + dy)
            if (not (0 <= cell[0] < width and 0 <= cell[1] < height)
                    or cell in blocked or cell in seen):
                continue
            seen[cell] = current
            if cell == target:
                result = [target]
                while seen[result[-1]] is not None:
                    result.append(seen[result[-1]])
                return [list(c) for c in reversed(result)]
            queue.append(cell)
    return None


def validate_npc_navigation(spec, exploration):
    """Legacy schedules without positions are unchanged.

    Geometric navigation is all-or-none per NPC. Every authored consecutive
    leg must be feasible before the project is accepted, including midnight.
    """
    require(type(exploration) is dict, "NPC navigation scenes must be a mapping")
    for npc in spec["npcs"]:
        stops = npc["schedule"]
        positioned = ["pos" in stop for stop in stops]
        if not any(positioned):
            continue
        require(all(positioned),
                "NPC movement requires coordinates on every schedule stop")
        for stop in stops:
            stage = exploration.get(stop["scene"])
            require(stage is not None, "NPC coordinates require an exploration scene")
            require(_point(stop["pos"], stage),
                    "NPC schedule cell is outside scene or blocked")
        for i, source in enumerate(stops):
            target = stops[(i + 1) % len(stops)]
            if source["scene"] != target["scene"]:
                continue  # Named scene handoff, not continuous pathfinding.
            path = shortest_path(exploration[source["scene"]],
                                 source["pos"], target["pos"])
            require(path is not None, "NPC schedule crosses disconnected terrain")
            minutes = ((target["minute"] - source["minute"]) % 1440)
            if minutes == 0:  # One-stop schedule, 24-hour self-loop.
                minutes = 1440
            require(len(path) - 1 <= minutes,
                    "NPC route exceeds its available schedule minutes")


def active_leg(npc, story_flags, minute, *, skip_conditions=True):
    """Return previous + next eligible stop and absolute local interval."""
    require(type(minute) is int and 0 <= minute < 1440,
            "Invalid NPC calendar minute")
    eligible = [stop for stop in npc["schedule"]
                if (not skip_conditions or "when" not in stop or
                    story_flags.get(stop["when"]["flag"], False)
                    is stop["when"]["eq"])]
    if not eligible:
        return None
    index = next((idx for idx in range(len(eligible) - 1, -1, -1)
                  if eligible[idx]["minute"] <= minute), -1)
    prior = eligible[index]
    following = eligible[(index + 1) % len(eligible)]
    prior_minute = prior["minute"] if index >= 0 else prior["minute"] - 1440
    next_minute = following["minute"]
    if next_minute <= prior_minute:
        next_minute += 1440
    return prior, following, prior_minute, next_minute


def resolve_npc(npc, flags, minute, exploration):
    """Find actual cell at arbitrary tick, with no per-tick NPC mutation."""
    positional = "pos" in npc["schedule"][0]
    # For positional NPCs the geometry is independent from story flags.
    # Conditions enable/disable *activity*, never change past positions.
    leg = active_leg(npc, flags, minute, skip_conditions=not positional)
    if leg is None:
        result = {"scene": None, "activity": "unavailable"}
        if "pos" in npc["schedule"][0]:
            result.update({"pos": None, "moving": False})
        return result
    prior, following, _, arrival = leg
    activity = prior["activity"]
    if positional and "when" in prior:
        if flags.get(prior["when"]["flag"], False) is not prior["when"]["eq"]:
            activity = "unavailable"
    result = {"scene": prior["scene"], "activity": activity}
    if "pos" not in prior:
        return result  # Legacy schedule shape is preserved.
    result.update({"pos": list(prior["pos"]), "moving": False})
    if prior["scene"] != following["scene"]:
        result["handoff_pending"] = True
        return result
    path = shortest_path(exploration[prior["scene"]],
                         prior["pos"], following["pos"])
    require(path is not None, "Validated NPC path became disconnected")
    duration = len(path) - 1
    departure = arrival - duration
    if minute > departure and duration:
        # A positional actor leaves their previous activity during travel.
        traversed = min(duration, minute - departure)
        result["pos"] = path[traversed]
        result["activity"] = "travel"
        result["moving"] = True
    return result


__all__ = ["shortest_path", "validate_npc_navigation", "resolve_npc"]

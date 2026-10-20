"""R37.D3 — bounded squad alerts and role-aware *proposals*, never orders executed.

The authored squad registry lives in GameProject's R37 extension and the actor
positions come from R35. All communication is direct and range/path limited:
no omniscient group blackboard, multi-hop relays, hidden unit movement or CT
command injection. Returns a detached, deterministic diagnostic only.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from .living_world_navigation import DIRECTIONS, _point, shortest_path
from .model import require

ROLES = frozenset(("officer", "vanguard", "protector", "flanker",
                   "archer", "medic", "scout"))
MAX_SQUAD_MEMBERS = 8
MAX_RADIO_RANGE = 16
RANK = {"seen": 0, "heard": 1, "memory": 2, "none": 3}


def _ident(value):
    return (type(value) is str and 1 <= len(value) <= 64
            and value[0].isascii() and value[0].islower()
            and all(ch.isascii() and (ch.islower() or ch.isdigit() or ch == "_")
                    for ch in value))


def validate_squad(spec):
    """One optional group binding per positioned R35 real-time agent."""
    require(type(spec) is dict
            and set(spec) == {"id", "role", "radio_range"}
            and _ident(spec["id"]) and type(spec["role"]) is str
            and spec["role"] in ROLES
            and type(spec["radio_range"]) is int
            and 0 <= spec["radio_range"] <= MAX_RADIO_RANGE,
            "Invalid R37 squad: id, role and 0..16 radio range required")
    return deepcopy(spec)


def _route(stage, source, dest):
    return shortest_path(stage, list(source), list(dest))


def _nearest_adjacent(stage, actor, destination, occupied, *, direction=None):
    """Stable reachable neighbor selection, ignoring occupied destinations."""
    candidates = []
    for dx, dy in DIRECTIONS:
        cell = [destination[0] + dx, destination[1] + dy]
        if not _point(cell, stage) or tuple(cell) in occupied:
            continue
        path = _route(stage, actor, cell)
        if path is None:
            continue
        distance = len(path) - 1
        # Flank: prefer a cell off the direct actor→target axis at equal cost.
        lateral = 0 if direction is None else (
            abs((cell[0]-destination[0])*direction[1] -
                (cell[1]-destination[1])*direction[0]))
        candidates.append((distance, -lateral, cell[1], cell[0], path))
    if not candidates:
        return None
    return min(candidates)[-1]


def coordinate_squad(stage, squad_id, members, *, scene, tick):
    """Preview direct signal sharing, formation targets and possible next cells.

    Each input is supplied by GameSession from a positioned R35 NPC, its
    verified R37 perception report and its replayed private blackboard.
    A member's known location is null unless it saw/heard the player or
    its *own* blackboard still remembers the last witnessed position.
    """
    require(_ident(squad_id) and type(scene) is str and bool(scene)
            and type(tick) is int and 0 <= tick <= 2**53 - 1
            and type(members) is list
            and 1 <= len(members) <= MAX_SQUAD_MEMBERS,
            "Invalid R37 squad preview metadata or member budget")
    require(type(stage) is dict
            and type(stage.get("width")) is int
            and type(stage.get("height")) is int
            and 1 <= stage["width"] <= 32 and 1 <= stage["height"] <= 32
            and type(stage.get("blocked")) is list
            and all(type(cell) is list and len(cell) == 2
                    and all(type(v) is int for v in cell)
                    and 0 <= cell[0] < stage["width"]
                    and 0 <= cell[1] < stage["height"]
                    for cell in stage["blocked"])
            and len({tuple(cell) for cell in stage["blocked"]})
            == len(stage["blocked"]),
            "Invalid canonical R37 squad grid")
    by_id = {}
    for row in members:
        require(type(row) is dict and set(row) ==
                {"actor_id", "pos", "role", "radio_range", "signal", "known_pos"}
                and _ident(row["actor_id"])
                and row["actor_id"] not in by_id
                and type(row["role"]) is str
                and row["role"] in ROLES
                and type(row["radio_range"]) is int
                and 0 <= row["radio_range"] <= MAX_RADIO_RANGE
                and type(row["signal"]) is str
                and row["signal"] in ("seen", "heard", "memory", "none")
                and _point(row["pos"], stage)
                and (row["known_pos"] is None or _point(row["known_pos"], stage))
                and ((row["signal"] == "none") == (row["known_pos"] is None)),
                "Invalid R37 squad source or target coordinates")
        by_id[row["actor_id"]] = deepcopy(row)
    members = [by_id[key] for key in sorted(by_id)]
    occupied = {tuple(row["pos"]) for row in members}
    # A fresh signal has precedence over remembered sightings, then actor ID.
    active = sorted((row for row in members if row["signal"] in ("seen", "heard")),
                    key=lambda row: (RANK[row["signal"]], row["actor_id"]))
    reports = []
    for row in members:
        personal = row["known_pos"]
        signal = row["signal"]
        shared_from = None
        if signal not in ("seen", "heard"):
            for source in active:
                if source["actor_id"] == row["actor_id"]:
                    continue
                if not source["radio_range"] or not row["radio_range"]:
                    continue
                path = _route(stage, source["pos"], row["pos"])
                if path is None or len(path) - 1 > min(
                        source["radio_range"], row["radio_range"]):
                    continue
                # Explicit direct transmission overrides stale private memory.
                personal = source["known_pos"]
                signal = source["signal"]
                shared_from = source["actor_id"]
                break
        path = None
        intent = "patrol"
        reason = "no_observed_target"
        if personal is not None:
            role = row["role"]
            path = _route(stage, row["pos"], personal)
            if path is None:
                intent, reason = "hold", "target_unreachable"
            else:
                intent, reason = "pursue", "last_known_position"
                if role == "officer":
                    intent, reason = "coordinate", "direct_report" if shared_from else "own_report"
                    path = [list(row["pos"])]
                elif role == "medic":
                    if len(path) - 1 <= 2:
                        alternatives = []
                        for dx, dy in DIRECTIONS:
                            cell = [row["pos"][0] + dx, row["pos"][1] + dy]
                            if not _point(cell, stage) or tuple(cell) in occupied:
                                continue
                            away = _route(stage, cell, personal)
                            if away is None:
                                continue
                            alternatives.append((-len(away), cell[1], cell[0], cell))
                        if alternatives:
                            escape = min(alternatives)[-1]
                            path = _route(stage, row["pos"], escape)
                            intent, reason = "retreat", "medic_at_risk"
                        else:
                            intent, reason = "hold", "no_safe_retreat"
                            path = [list(row["pos"])]
                    else:
                        intent, reason = "hold", "medic_support"
                        path = [list(row["pos"])]
                elif role in ("vanguard", "protector"):
                    protected = next((
                        ally for ally in members
                        if ally["actor_id"] != row["actor_id"]
                        and ally["role"] in ("medic", "archer")), None)
                    if protected is not None:
                        guard = _nearest_adjacent(
                            stage, row["pos"], protected["pos"], occupied)
                        if guard is not None:
                            path = guard
                            intent, reason = "protect", "cover_support"
                elif role == "flanker":
                    axis = (personal[0]-row["pos"][0], personal[1]-row["pos"][1])
                    flank = _nearest_adjacent(
                        stage, row["pos"], personal, occupied, direction=axis)
                    if flank is not None:
                        path = flank
                        intent, reason = "flank", "reachable_side_cell"
                elif role == "archer":
                    if len(path) - 1 > 1:
                        path = [list(row["pos"])]
                        intent, reason = "cover", "maintain_distance"
                elif role == "scout":
                    intent, reason = "investigate", "squad_report"
        reports.append({
            "actor_id": row["actor_id"], "role": row["role"],
            "source_signal": row["signal"],
            "received_signal": signal if shared_from else "none",
            "shared_from": shared_from,
            "known_pos": deepcopy(personal),
            "intent": intent, "reason": reason,
            "route": deepcopy(path),
            "next_step": path[1] if path is not None and len(path) > 1 else None,
            "reachable": path is not None,
        })
    result = {"version": 1, "squad_id": squad_id, "scene": scene,
              "tick": tick, "members": reports,
              "fresh_sources": [row["actor_id"] for row in active]}
    result["digest"] = sha256(json.dumps(
        result, ensure_ascii=True, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    return result


__all__ = ["ROLES", "validate_squad", "coordinate_squad"]

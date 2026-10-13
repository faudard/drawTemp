"""3.7.24B — continuous, checkpointed traversal of the authored mission world.

Mission.next_missions supplies all roads. A route can use only unlocked or
completed missions; no second unlock graph or tactical grid is introduced.
One journey's position is saved in the existing Campaign.story_flags.
"""
from collections import deque

from .model import require

STEPS_PER_EDGE = 8
AT, GOAL, VIA, STEP = ("world_walk_at", "world_walk_goal",
                       "world_walk_via", "world_walk_step")


def _locations(world):
    return {node["mission"]: (node["x"], node["y"]) for node in world["nodes"]}


def _roads(content, locations, allowed):
    roads = {mid: set() for mid in allowed}
    for source in allowed:
        for target in content.missions[source].next_missions:
            if target in roads:
                # A previously traversed road is usable in both directions.
                roads[source].add(target)
                roads[target].add(source)
    return roads


def _route(roads, source, destination):
    """Shortest accessible route, with deterministic tie-breaking."""
    if source not in roads or destination not in roads:
        return []
    queue = deque([source])
    parents = {source: None}
    while queue:
        current = queue.popleft()
        if current == destination:
            path = []
            while current is not None:
                path.append(current)
                current = parents[current]
            return list(reversed(path))
        for neighbor in sorted(roads[current]):
            if neighbor not in parents:
                parents[neighbor] = current
                queue.append(neighbor)
    return []


class WorldJourney:
    """A headless, bounded world-space cursor for one campaign slot."""

    def __init__(self, world, content, campaign):
        self.world = world
        self.content = content
        self.start = campaign["start_mission"]
        self.positions = _locations(world) if world else {}

    def state(self, progress):
        if self.start not in self.positions:
            # Partial world maps can legitimately omit another campaign.
            return None
        allowed = (set(progress.unlocked) | set(progress.completed)) & set(self.positions)
        roads = _roads(self.content, self.positions, allowed)
        flags = progress.story_flags
        at = flags.get(AT, self.start)
        goal = flags.get(GOAL, "")
        via = flags.get(VIA, "")
        step = flags.get(STEP, 0)
        require(type(at) is str and at in allowed, "Invalid saved world location")
        require(type(goal) is str and (not goal or goal in allowed),
                "Invalid saved world destination")
        require(type(via) is str and (not via or via in roads[at]),
                "Invalid saved world road")
        require(type(step) is int and 0 <= step < STEPS_PER_EDGE,
                "Invalid saved world travel progress")
        require((bool(via) and bool(goal) and step > 0) or
                (not via and step == 0), "Inconsistent saved world travel")
        route = _route(roads, at, goal) if goal else []
        require(not goal or (goal != at and route), "Disconnected saved world route")
        if via:
            # The current leg must be part of an accessible route to the goal.
            require(_route(roads, via, goal), "Saved world road cannot reach destination")
        x, y = self.positions[at]
        if via:
            nx, ny = self.positions[via]
            x = round(x + (nx - x) * step / STEPS_PER_EDGE)
            y = round(y + (ny - y) * step / STEPS_PER_EDGE)
        return {"at": at, "goal": goal, "via": via, "step": step,
                "position": (x, y), "traveling": bool(goal),
                "route": ([at, via] + _route(roads, via, goal)[1:]
                          if via else route),
                "reachable": sorted(mid for mid in allowed
                                    if _route(roads, at, mid))}

    def destination(self, progress, mission_id):
        state = self.state(progress)
        require(state is not None, "No world journey for this campaign")
        require(not state["traveling"], "Finish the current journey first")
        require(mission_id in state["reachable"] and mission_id != state["at"],
                "This world destination is not accessible")
        progress.story_flags[GOAL] = mission_id
        progress.story_flags[VIA] = ""
        progress.story_flags[STEP] = 0
        return self.state(progress)

    def advance(self, progress):
        state = self.state(progress)
        require(state is not None and state["traveling"], "No journey in progress")
        via = state["via"] or state["route"][1]
        step = state["step"] + 1
        if step == STEPS_PER_EDGE:
            progress.story_flags[AT] = via
            progress.story_flags[VIA] = ""
            progress.story_flags[STEP] = 0
            if via == state["goal"]:
                progress.story_flags[GOAL] = ""
        else:
            progress.story_flags[VIA] = via
            progress.story_flags[STEP] = step
        return self.state(progress)

    def can_enter(self, progress, mission_id):
        state = self.state(progress)
        return (state is not None and not state["traveling"]
                and state["at"] == mission_id
                and mission_id in progress.unlocked
                and mission_id not in progress.completed)

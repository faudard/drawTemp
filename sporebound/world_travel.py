"""Persistent world-road travel backed by the canonical mission graph.

Road encounters reuse StoryBook. A route decision can continue, backtrack
physically to the previous junction or pick another unlocked destination.
All state lives in the existing bounded Campaign.story_flags checkpoint.
"""
from collections import deque

from .model import require
from .narrative import matches

STEPS_PER_EDGE = 8
AT, GOAL, VIA, STEP = ("world_walk_at", "world_walk_goal",
                       "world_walk_via", "world_walk_step")
REVERSE = "world_walk_reverse"
PENDING = "world_walk_event"


def _locations(world):
    return {node["mission"]: (node["x"], node["y"]) for node in world["nodes"]}


def _roads(content, locations, allowed):
    roads = {mid: set() for mid in allowed}
    for source in allowed:
        for target in content.missions[source].next_missions:
            if target in roads:
                roads[source].add(target)
                roads[target].add(source)
    return roads


def _route(roads, source, destination):
    """Shortest path using only unlocked/completed, visible authored roads."""
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
    """Headless, replay-safe road cursor. No new campaign or battle schema."""

    def __init__(self, world, content, campaign):
        self.world = world
        self.content = content
        self.start = campaign["start_mission"]
        self.positions = _locations(world) if world else {}

    def _graph(self, progress):
        allowed = (set(progress.unlocked) | set(progress.completed)) & set(self.positions)
        return _roads(self.content, self.positions, allowed)

    def _event_on_leg(self, event, at, via, step):
        if (event["from"], event["to"]) == (at, via):
            return step == event.get("step", STEPS_PER_EDGE // 2)
        if (event["from"], event["to"]) == (via, at):
            return step == STEPS_PER_EDGE - event.get(
                "step", STEPS_PER_EDGE // 2)
        return False

    def state(self, progress):
        if self.start not in self.positions:
            return None
        roads = self._graph(progress)
        flags = progress.story_flags
        for event in self.world.get("events", []):
            once = flags.get("world_evt_" + event["id"], False)
            require(type(once) is bool, "Invalid saved world event state")
        at = flags.get(AT, self.start)
        goal = flags.get(GOAL, "")
        via = flags.get(VIA, "")
        step = flags.get(STEP, 0)
        reverse = flags.get(REVERSE, False)
        pending = flags.get(PENDING, "")
        require(type(at) is str and at in roads, "Invalid saved world location")
        require(type(goal) is str and (not goal or goal in roads),
                "Invalid saved world destination")
        require(type(via) is str and (not via or via in roads[at]),
                "Invalid saved world road")
        require(type(step) is int and 0 <= step < STEPS_PER_EDGE,
                "Invalid saved world travel progress")
        require(type(reverse) is bool and (not reverse or bool(via)),
                "Invalid world return direction")
        require(type(pending) is str, "Invalid pending road event")
        require((bool(via) and bool(goal) and step > 0) or
                (not via and step == 0 and not reverse),
                "Inconsistent saved world travel")
        route = _route(roads, at, goal) if goal else []
        require(not goal or reverse or (goal != at and route),
                "Disconnected saved world route")
        if via:
            require(_route(roads, at, goal) if reverse else
                    _route(roads, via, goal),
                    "Saved world road cannot reach destination")
        if pending:
            event = next((row for row in self.world.get("events", [])
                          if row["id"] == pending), None)
            require(event is not None and via and not reverse and
                    self._event_on_leg(event, at, via, step) and
                    flags.get("world_evt_" + pending) is True and
                    progress.story_pending == event["scene"],
                    "Invalid pending world event checkpoint")
        x, y = self.positions[at]
        if via:
            nx, ny = self.positions[via]
            x = round(x + (nx - x) * step / STEPS_PER_EDGE)
            y = round(y + (ny - y) * step / STEPS_PER_EDGE)
        return {"at": at, "goal": goal, "via": via, "step": step,
                "position": (x, y), "traveling": bool(goal),
                "reversing": reverse, "pending_event": pending,
                "route": ([via, at] + route[1:] if reverse else
                          [at, via] + _route(roads, via, goal)[1:]
                          if via else route),
                "reachable": sorted(mid for mid in roads
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
        progress.story_flags.pop(REVERSE, None)
        return self.state(progress)

    def advance(self, progress):
        state = self.state(progress)
        require(state is not None and state["traveling"] and
                not state["pending_event"], "No travel step available")
        if state["reversing"]:
            step = state["step"] - 1
            progress.story_flags[STEP] = step
            if step == 0:
                progress.story_flags[VIA] = ""
                progress.story_flags.pop(REVERSE, None)
                if state["goal"] == state["at"]:
                    progress.story_flags[GOAL] = ""
            return self.state(progress)
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

    def event_at(self, progress):
        """Select the first eligible event at this physical location."""
        state = self.state(progress)
        if (state is None or not state["via"] or state["reversing"]
                or state["pending_event"]):
            return None
        for event in self.world.get("events", []):
            if not self._event_on_leg(event, state["at"],
                                      state["via"], state["step"]):
                continue
            if progress.story_flags.get("world_evt_" + event["id"], False):
                continue
            if "when" in event and not matches(event["when"], progress):
                continue
            return event
        return None

    def redirect(self, progress, event, choice_id):
        """Apply an authored choice after StoryBook effects succeed.

        Return/reroute travel traverses the remaining distance *backwards* to
        the departure junction, then takes the new canonical route.
        """
        state = self.state(progress)
        require(state is not None and state["pending_event"] == event["id"],
                "No matching pending road choice")
        action = event.get("routes", {}).get(choice_id, {"kind": "continue"})
        kind = action["kind"]
        if kind != "continue":
            target = (state["at"] if kind == "return"
                      else action["mission"])
            roads = self._graph(progress)
            require(target in roads and _route(roads, state["at"], target),
                    "Chosen detour is not unlocked or accessible")
            progress.story_flags[GOAL] = target
            progress.story_flags[REVERSE] = True
        progress.story_flags.pop(PENDING, None)
        return self.state(progress)

    def can_enter(self, progress, mission_id):
        state = self.state(progress)
        return (state is not None and not state["traveling"]
                and state["at"] == mission_id
                and mission_id in progress.unlocked
                and mission_id not in progress.completed)

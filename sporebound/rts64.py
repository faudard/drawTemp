"""R64.A experimental headless RTS squads over the R25 fixed-tick journal.

Opt-in only: no GameSession/Battle/CT rules or legacy save formats are changed.
Grid coordinates and combat intervals are integer tick values, never frame time.
This module intentionally does not claim Studio/Player integration or RTS scale.
"""
from collections import deque
from copy import deepcopy

from .fixed_clock import FixedTickJournal, _digest
from .model import require

MAX_UNITS = 128
MAX_GROUP = 32
MAX_CELLS = 16384
ATTACK_INTERVAL = 10
STALL_WARNING = 8
RULES = frozenset({"hold_fire", "return_fire", "fire_at_will"})
FORMATIONS = frozenset({"line", "column", "wedge"})
DIRECTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0))


def _cell(value):
    return (type(value) in (list, tuple) and len(value) == 2
            and all(type(v) is int for v in value))


def _distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _offset(index, count, formation):
    if formation == "line":
        return index - (count - 1) // 2, 0
    if formation == "column":
        return 0, index
    if index == 0:
        return 0, 0
    rank = (index + 1) // 2
    return (-rank if index % 2 else rank), rank


class RTSWorld:
    """Bounded deterministic prototype: group orders, pathfinding and engagement.

    Only explicit commands can change orders. Movement is serialized in one
    integer tick and each destination is reserved before another unit moves.
    A blocked unit replans every tick; persistent stalls are reported, never
    silently teleported. Project authoring and UI bindings are future R64.B.
    """

    def __init__(self, width, height, units, *, walls=(), rate=60, seed=1):
        require(type(width) is int and type(height) is int
                and 1 <= width <= 128 and 1 <= height <= 128
                and width * height <= MAX_CELLS, "Invalid RTS map dimensions")
        require(type(walls) in (list, tuple, set),
                "RTS walls must be a collection")
        self.width, self.height = width, height
        wall_set = set()
        for cell in walls:
            require(_cell(cell), "Invalid RTS wall")
            p = tuple(cell)
            require(self._within(p), "RTS wall outside map")
            require(p not in wall_set, "Duplicate RTS wall")
            wall_set.add(p)
        self.walls = frozenset(wall_set)
        require(type(units) in (list, tuple) and 0 < len(units) <= MAX_UNITS,
                "Invalid RTS unit count")
        actors, positions = {}, set()
        for row in units:
            require(type(row) is dict
                    and set(row) in ({"id", "team", "pos"},
                                     {"id", "team", "pos", "hp"}),
                    "RTS unit needs id/team/pos and optional hp")
            uid, team, pos = row["id"], row["team"], row["pos"]
            hp = row.get("hp", 3)
            require(type(uid) is str and 0 < len(uid) <= 64
                    and all(c.isalnum() or c in "_-" for c in uid)
                    and uid not in actors, "Invalid or duplicate RTS unit id")
            require(type(team) is str and 0 < len(team) <= 32
                    and all(c.isalnum() or c in "_-" for c in team),
                    "Invalid RTS team")
            require(_cell(pos) and self._walkable(tuple(pos))
                    and tuple(pos) not in positions,
                    "RTS units overlap or occupy blocked/outside cells")
            require(type(hp) is int and 1 <= hp <= 100, "Invalid RTS health")
            positions.add(tuple(pos))
            actors[uid] = {"id": uid, "team": team, "pos": list(pos),
                           "hp": hp, "goal": None, "rules": "hold_fire",
                           "last_hit": -1, "stalled": 0}
        initial = {"width": width, "height": height,
                   "walls": [list(p) for p in sorted(wall_set)],
                   "units": [deepcopy(actors[k]) for k in sorted(actors)]}
        self.scenario_digest = _digest(initial)
        self._state = {"tick": 0, "scenario": self.scenario_digest,
                       "units": [actors[k] for k in sorted(actors)],
                       "actions": [], "stalled_units": []}
        self.clock = FixedTickJournal(rate=rate, seed=seed)

    def _within(self, p):
        return 0 <= p[0] < self.width and 0 <= p[1] < self.height

    def _walkable(self, p):
        return self._within(p) and p not in self.walls

    def snapshot(self):
        return deepcopy(self._state)

    def submit(self, tick, source, command):
        """Queue a move_group, stop_group or set_engagement for a future tick."""
        return self.clock.submit(tick, source, command)

    def step(self):
        return self.clock.step(self._advance)

    def recording(self):
        return self.clock.recording()

    @classmethod
    def replay(cls, width, height, units, recording, *, walls=()):
        """Validate every tick against a fresh scenario and R25 checksums."""
        world = cls(width, height, units, walls=walls,
                    rate=recording["rate"], seed=recording["seed"])
        world.clock = FixedTickJournal.replay(recording, world._advance)
        return world

    @staticmethod
    def _members(command, actors):
        ids = command.get("units")
        require(type(ids) is list and 0 < len(ids) <= MAX_GROUP
                and all(type(k) is str for k in ids)
                and len(set(ids)) == len(ids), "Invalid RTS unit selection")
        require(all(k in actors and actors[k]["hp"] > 0 for k in ids),
                "Order contains unknown or defeated units")
        teams = {actors[k]["team"] for k in ids}
        require(len(teams) == 1, "RTS group orders cannot mix teams")
        return [actors[k] for k in sorted(ids)]

    def _nearest_free(self, desired, forbidden):
        cells = ((x, y) for y in range(self.height) for x in range(self.width)
                 if (x, y) not in self.walls and (x, y) not in forbidden)
        return min(cells, key=lambda p: (_distance(p, desired), p[1], p[0]),
                   default=None)

    def _apply(self, actors, command):
        require(type(command) is dict and type(command.get("kind")) is str,
                "Invalid RTS command")
        kind = command["kind"]
        require(kind in {"move_group", "stop_group", "set_engagement"},
                "Unknown RTS command")
        allowed = ({"kind", "units", "target", "formation", "rules"}
                   if kind == "move_group" else
                   {"kind", "units", "rules"} if kind == "set_engagement"
                   else {"kind", "units"})
        require(not set(command) - allowed, "Unexpected RTS command field")
        members = self._members(command, actors)
        if kind == "stop_group":
            for actor in members:
                actor["goal"], actor["stalled"] = None, 0
            return
        if kind == "set_engagement":
            rules = command.get("rules")
            require(type(rules) is str and rules in RULES,
                    "Invalid RTS engagement rules")
            for actor in members:
                actor["rules"] = rules
            return
        target = command.get("target")
        formation = command.get("formation", "line")
        rules = command.get("rules")
        require(_cell(target) and self._walkable(tuple(target)),
                "Invalid RTS move target")
        require(type(formation) is str and formation in FORMATIONS,
                "Invalid RTS formation")
        require(rules is None or (type(rules) is str and rules in RULES),
                "Invalid RTS engagement rules")
        member_ids = {row["id"] for row in members}
        forbidden = {tuple(a["pos"]) for a in actors.values()
                     if a["hp"] > 0 and a["id"] not in member_ids}
        forbidden.update(tuple(a["goal"]) for a in actors.values()
                         if a["hp"] > 0 and a["id"] not in member_ids
                         and a["goal"] is not None)
        selected = {}
        for index, actor in enumerate(members):
            dx, dy = _offset(index, len(members), formation)
            desired = (target[0] + dx, target[1] + dy)
            slot = self._nearest_free(desired, forbidden)
            require(slot is not None, "Not enough RTS formation slots")
            forbidden.add(slot)
            selected[actor["id"]] = slot
        for actor in members:
            actor["goal"] = list(selected[actor["id"]])
            actor["stalled"] = 0
            if rules is not None:
                actor["rules"] = rules

    def _next_step(self, start, goal, occupied):
        """Deterministic four-neighbor BFS, replanned against live reservations."""
        start, goal = tuple(start), tuple(goal)
        if start == goal:
            return start
        if goal in occupied:
            return None
        visited = {start: None}
        queue = deque([start])
        while queue:
            p = queue.popleft()
            for dx, dy in DIRECTIONS:
                nxt = (p[0] + dx, p[1] + dy)
                if (nxt in visited or nxt in occupied
                        or not self._walkable(nxt)):
                    continue
                visited[nxt] = p
                if nxt == goal:
                    while visited[nxt] != start:
                        nxt = visited[nxt]
                    return nxt
                queue.append(nxt)
        return None

    def _advance(self, tick, events):
        # Work entirely on detached data; invalid orders never partially commit.
        actors = {a["id"]: a for a in deepcopy(self._state["units"])}
        for event in events:
            self._apply(actors, event["command"])
        actions = []
        occupied = {tuple(a["pos"]) for a in actors.values() if a["hp"] > 0}
        moving = [a for a in actors.values() if a["hp"] > 0
                  and a["goal"] is not None and a["goal"] != a["pos"]]
        # Leading units advance first, allowing their trailing allies to take
        # just-vacated cells. Ties rotate by tick, eliminating permanent ID bias.
        moving.sort(key=lambda a: (_distance(a["pos"], a["goal"]),
                                   (sorted(actors).index(a["id"]) + tick)
                                   % len(actors), a["id"]))
        for actor in moving:
            src = tuple(actor["pos"])
            occupied.remove(src)
            nxt = self._next_step(src, actor["goal"], occupied)
            if nxt is None:
                actor["stalled"] += 1
            else:
                actor["pos"] = list(nxt)
                actor["stalled"] = 0
                if nxt != src:
                    actions.append({"kind": "move", "unit": actor["id"],
                                    "from": list(src), "to": list(nxt)})
            occupied.add(tuple(actor["pos"]))
        for actor in actors.values():
            if actor["goal"] == actor["pos"]:
                actor["goal"], actor["stalled"] = None, 0
        # Simple, deliberately bounded adjacent-unit engagement. Simultaneous
        # damage prevents source ordering from deciding who gets to fire.
        if tick % ATTACK_INTERVAL == 0:
            damage = {}
            living = [a for a in actors.values() if a["hp"] > 0]
            for attacker in sorted(living, key=lambda a: a["id"]):
                if attacker["rules"] == "hold_fire":
                    continue
                if (attacker["rules"] == "return_fire"
                        and not 0 <= tick - attacker["last_hit"] <=
                        2 * ATTACK_INTERVAL):
                    continue
                nearby = [a for a in living if a["team"] != attacker["team"]
                          and _distance(a["pos"], attacker["pos"]) == 1]
                if not nearby:
                    continue
                victim = min(nearby, key=lambda a: (a["hp"], a["id"]))
                damage[victim["id"]] = damage.get(victim["id"], 0) + 1
                actions.append({"kind": "attack", "unit": attacker["id"],
                                "target": victim["id"], "damage": 1})
            for uid, amount in damage.items():
                victim = actors[uid]
                victim["hp"] = max(0, victim["hp"] - amount)
                victim["last_hit"] = tick
                if not victim["hp"]:
                    victim["goal"], victim["stalled"] = None, 0
        state = {"tick": tick, "scenario": self.scenario_digest,
                 "units": [actors[k] for k in sorted(actors)],
                 "actions": actions,
                 "stalled_units": sorted(a["id"] for a in actors.values()
                                         if a["stalled"] >= STALL_WARNING)}
        self._state = deepcopy(state)
        return state


__all__ = ["RTSWorld", "MAX_UNITS", "MAX_GROUP", "RULES", "FORMATIONS"]

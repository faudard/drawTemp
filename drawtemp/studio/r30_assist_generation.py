"""R30.G deterministic, opt-in terrain and lever/door starter templates.

The game document remains Content v1 / GameProject v1; a single
AuthoringSession owns both validation and Undo. No model downloads, API calls,
generated scripts or implicit modifications. No claim of puzzle solvability
beyond reachability of the switch in the *current* tactical board.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from random import Random
import re

from drawtemp.sdk.authoring import AuthoringSession, AuthoringPlan
from sporebound.terrain_schema import SURFACES

MODES = ("clearing", "trail", "lever-door")
_SAFE_SURFACES = ("dirt", "sand", "stone", "cobble")
_NAMESPACE = re.compile(r"[a-z][a-z0-9_]{0,11}\Z")
MAX_CELLS = 256


class AssistError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class GeneratedCell:
    x: int
    y: int
    before: str
    after: str


@dataclass(frozen=True)
class AssistPreview:
    revision: int
    mission_id: str
    mode: str
    seed: int
    rectangle: tuple[int, int, int, int]
    tiles: tuple[GeneratedCell, ...]
    object_ids: tuple[str, ...]
    protected_count: int
    switch_reachable: bool | None

    def to_dict(self):
        return {
            "revision": self.revision, "mission": self.mission_id,
            "mode": self.mode, "seed": self.seed,
            "rectangle": list(self.rectangle),
            "tiles": [vars(cell).copy() for cell in self.tiles],
            "object_ids": list(self.object_ids),
            "protected_count": self.protected_count,
            "switch_reachable": self.switch_reachable,
            "applied": False, "gameplay_certified": False,
        }


def _mission(content, mission_id):
    if not isinstance(mission_id, str):
        raise AssistError("invalid_mission", "Expected a real mission id")
    row = next((m for m in content["missions"] if m["id"] == mission_id), None)
    if row is None:
        raise AssistError("unknown_mission", "Unknown mission: " + mission_id)
    return row


def _rectangle(mission, rectangle):
    if not isinstance(rectangle, (list, tuple)) or len(rectangle) != 4:
        raise AssistError("invalid_rectangle", "Expected (x,y,width,height)")
    x, y, width, height = rectangle
    if any(type(item) is not int for item in rectangle):
        raise AssistError("invalid_rectangle", "Booleans and floats are not map coordinates")
    if (x < 0 or y < 0 or not 1 <= width <= 16 or
            not 1 <= height <= 16 or width * height > MAX_CELLS or
            x + width > mission["board"]["width"] or
            y + height > mission["board"]["height"]):
        raise AssistError("invalid_rectangle", "Bounded rectangle outside the mission")
    return (x, y, width, height)


def _collect_positions(data):
    """Conservative semantic footprint; never repaint authored entities or goals."""
    reserved = set()

    def point(raw):
        if (isinstance(raw, (list, tuple)) and len(raw) == 2 and
                all(type(v) is int for v in raw)):
            reserved.add(tuple(raw))

    def footprint(raw):
        if (isinstance(raw, (list, tuple)) and len(raw) == 2 and
                all(type(v) is int and 1 <= v <= 32 for v in raw)):
            return raw
        return (1, 1)

    for unit in data.get("units", []):
        pos = unit.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            w, h = footprint(unit.get("footprint"))
            for dy in range(h):
                for dx in range(w):
                    point((pos[0] + dx, pos[1] + dy))
    for obj in data.get("objects", []):
        point(obj.get("pos"))
        for cell in obj.get("cells", []):
            point(cell)
    for cell in data.get("goal", []):
        point(cell)
    point(data.get("relic"))
    for zone in data.get("deployment", []):
        for cell in zone.get("cells", []):
            point(cell)
    for item in data.get("triggers", []):
        point(item.get("pos"))
        for cell in item.get("cells", []):
            point(cell)
    # Stored 2.5D or group metadata must never be silently reauthored.
    for record in data.get("structures", []):
        point(record.get("pos"))
        for cell in record.get("cells", []):
            point(cell)
    for record in data.get("level_links", []):
        point(record.get("pos"))
        point(record.get("source"))
        point(record.get("destination"))
    for record in data.get("editor_groups", []):
        point(record.get("pos"))
    return reserved


def _walkable(mission, forbidden):
    board = mission["board"]
    width, height = board["width"], board["height"]
    tiles = {tuple(tile["pos"]): tile for tile in board["tiles"]}
    doors = {tuple(obj["pos"]) for obj in mission.get("objects", [])
             if obj["kind"] == "door"}
    reachable, todo = set(), deque()
    for unit in mission["units"]:
        if unit.get("team") == "player" and unit.get("hp", 0) > 0:
            loc = tuple(unit["pos"])
            if loc not in reachable:
                todo.append(loc)
                reachable.add(loc)
    while todo:
        x, y = todo.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cell = (x + dx, y + dy)
            if (cell in reachable or cell in forbidden or cell in doors or
                    not 0 <= cell[0] < width or not 0 <= cell[1] < height or
                    tiles.get(cell, {}).get("blocked", False)):
                continue
            reachable.add(cell)
            todo.append(cell)
    return reachable


def _generate(content, mission_id, rectangle, mode, seed, namespace):
    if not isinstance(mode, str) or mode not in MODES:
        raise AssistError("invalid_mode", "Unknown assisted generator")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise AssistError("invalid_seed", "Seed must be uint32")
    if not isinstance(namespace, str) or not _NAMESPACE.fullmatch(namespace):
        raise AssistError("invalid_namespace", "Expected 1..12 safe lower-case chars")
    updated = deepcopy(content)
    mission = _mission(updated, mission_id)
    x, y, width, height = _rectangle(mission, rectangle)
    allowed = [(a, b) for b in range(y, y + height)
               for a in range(x, x + width)]
    protected = _collect_positions(mission)
    explicit = {tuple(tile["pos"]): tile for tile in mission["board"]["tiles"]}
    # Only truly empty, default terrain cells can be changed. Never replace an
    # authored tile or move/clone an object, unit, trigger, goal or deployment.
    candidates = [loc for loc in allowed
                  if loc not in protected and loc not in explicit]
    if not candidates:
        raise AssistError("no_safe_cells", "No unoccupied, unauthored cells in selection")
    rng = Random(seed)
    painted = []
    new_ids = []
    reachable = None
    if mode in ("clearing", "trail"):
        cells = candidates if mode == "clearing" else _trail(candidates, rng)
        if not cells:
            raise AssistError("no_safe_cells", "Could not generate a safe connected trail")
        for loc in cells:
            surface = rng.choice(_SAFE_SURFACES)
            if surface not in SURFACES:
                raise AssistError("invalid_surface", "Unsupported canonical terrain")
            mission["board"]["tiles"].append(
                {"pos": list(loc), "surface": surface, "blocked": False})
            painted.append(GeneratedCell(*loc, "grass", surface))
        mission["board"]["tiles"].sort(key=lambda tile: (
            tile["pos"][1], tile["pos"][0]))
    else:
        existing = {obj["id"] for obj in mission.get("objects", [])}
        door_id = "r30g_" + namespace + "_door"
        switch_id = "r30g_" + namespace + "_switch"
        if {door_id, switch_id} & existing:
            raise AssistError("duplicate_object", "Existing puzzle ids; change namespace")
        # The reachable switch must be accessible *without crossing the new
        # gate* or an old closed door. No promise the gate blocks all routes.
        reachable_map = _walkable(mission, set())
        possible = [
            (switch, door) for switch in candidates for door in candidates
            if switch != door and switch in reachable_map and
            (abs(switch[0] - door[0]) + abs(switch[1] - door[1])) == 1
        ]
        if not possible:
            raise AssistError("unreachable_switch",
                              "No reachable switch + adjacent gate in safe selection")
        switch, door = rng.choice(sorted(possible))
        mission.setdefault("objects", []).extend([
            {"id": door_id, "kind": "door", "pos": list(door)},
            {"id": switch_id, "kind": "switch", "pos": list(switch),
             "link": door_id},
        ])
        new_ids = [door_id, switch_id]
        reachable = True
    return updated, tuple(painted), tuple(new_ids), len(set(allowed) & protected), reachable


def _trail(candidates, rng):
    """Generate only a four-connected path, never teleport across obstacles."""
    active = set(candidates)
    start = rng.choice(sorted(active))
    wanted = min(len(active), 12)
    path, visited = [start], {start}
    while len(path) < wanted:
        x, y = path[-1]
        neighbors = [(x + dx, y + dy) for dx, dy in (
            (1, 0), (-1, 0), (0, 1), (0, -1))]
        choices = [p for p in neighbors if p in active and p not in visited]
        if not choices:
            break
        nxt = rng.choice(sorted(choices))
        path.append(nxt)
        visited.add(nxt)
    return tuple(path)


class AssistController:
    """Preview and apply a single validated Content edit with built-in Undo."""

    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise AssistError("invalid_session", "Use the owning Studio session")
        self.session = session
        self.invalidate()

    def preview(self, mission_id, *, rectangle, mode="clearing", seed=0,
                namespace="sample"):
        self.invalidate()
        before = self.session.snapshot().to_dict()
        candidate, cells, objects, protected_count, reachable = _generate(
            before["content"], mission_id, rectangle, mode, seed, namespace)
        plan = self.session.preview_pair(
            lambda _content, project: (candidate, project),
            kind="r30g-assisted-generation", mission_id=mission_id,
            views=("workspace", "inspector", "renderer", "minimap"),
        )
        report = AssistPreview(
            before["revision"], mission_id, mode, seed, tuple(rectangle),
            cells, objects, protected_count, reachable,
        )
        self._plan = plan
        self._preview = report
        return report

    def apply(self, preview: AssistPreview):
        if self._preview is not preview or self._plan is None:
            raise AssistError("stale_preview", "Preview again after changing generation options")
        plan = self._plan
        self.invalidate()
        return self.session.apply(plan)

    def invalidate(self):
        self._plan: AuthoringPlan | None = None
        self._preview: AssistPreview | None = None

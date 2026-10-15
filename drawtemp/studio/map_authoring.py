"""R5 Qt Map Studio controller: canonical Content/GameProject editing only.

Every gesture is one R1 AuthoringSession transaction; previews carry its
monotonic revision and cannot commit after an intervening edit/undo.
No independent map schema, history, file writer, or tactical rules live here.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass

from drawtemp.core import RuleError
from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from sporebound.authoring import add_blank_mission, set_mission_properties, add_unit
from sporebound.iso_structures import place_structure
from sporebound.map_authoring import (
    cells_in_rectangle, copy_terrain, paste_terrain, move_unit, selected_cells,
)
from sporebound.map_builder4 import smart_brush_cells
from sporebound.terrain_schema import SURFACES, FEATURES
from .map_layers import LayerWorkspace


BRUSHES = ("grass", "dirt", "sand", "stone", "cobble", "water", "bridge")
TOOLS = ("pencil", "rectangle", "line", "fill", "picker", "erase", "goal",
         "wall", "cover", "hazard", "height+", "height-", "Maison", "Pont", "Tour")
SURFACE_PALETTE = tuple(name for name in BRUSHES if name in SURFACES)


def _mission(content, mission_id):
    mission = next((m for m in content["missions"] if m["id"] == mission_id), None)
    if mission is None:
        raise RuleError("Unknown map: " + str(mission_id))
    return mission


def _cell(mission, raw):
    if (not isinstance(raw, (tuple, list)) or len(raw) != 2
            or any(type(v) is not int for v in raw)):
        raise RuleError("Expected integer map coordinates")
    x, y = raw
    if not (0 <= x < mission["board"]["width"] and
            0 <= y < mission["board"]["height"]):
        raise RuleError("Cell outside map: " + str(raw))
    return (x, y)


def _line(a, b):
    """Integer Bresenham line, endpoints included."""
    x0, y0 = a
    x1, y1 = b
    dx, dy = abs(x1-x0), -abs(y1-y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    error = dx + dy
    output = []
    while True:
        output.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return tuple(output)
        twice = 2*error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


def _paint(data, mission_id, cells, brush):
    """Sparse board projection. R1 validates the entire resulting pair."""
    mission = _mission(data, mission_id)
    cells = selected_cells(data, mission_id, list(cells))
    tiles = {tuple(t["pos"]): deepcopy(t) for t in mission["board"]["tiles"]}
    goals = {tuple(cell) for cell in mission.get("goal", ())}
    for cell in cells:
        old = tiles.get(cell, {"pos": list(cell)})
        tile = dict(old)
        surface = brush.removeprefix("surface:")
        if brush == "erase":
            tile = {"pos": list(cell)}
            goals.discard(cell)
        elif brush == "goal":
            goals.add(cell)
        elif brush.startswith("surface:"):
            if surface not in SURFACES:
                raise RuleError("Unknown surface: " + surface)
            tile["surface"] = surface
            if surface == "water" or old.get("feature") == "stone_wall":
                tile["blocked"] = True
            elif surface == "bridge" or old.get("surface") == "water":
                tile["blocked"] = False
        elif brush.startswith("feature:"):
            feature = brush.partition(":")[2]
            if feature not in FEATURES:
                raise RuleError("Unknown feature: " + feature)
            tile["feature"] = feature
            if feature == "stone_wall":
                tile["blocked"] = True
            elif old.get("feature") == "stone_wall":
                tile["blocked"] = old.get("surface") == "water"
        elif brush == "wall":
            tile["blocked"] = True
        elif brush == "cover":
            tile["cover"] = 20
        elif brush == "hazard":
            tile["hazard"] = 4
        elif brush == "height+":
            tile["height"] = min(99, old.get("height", 0) + 1)
        elif brush == "height-":
            tile["height"] = max(0, old.get("height", 0) - 1)
        else:
            raise RuleError("Unknown map brush: " + brush)
        if len(tile) > 1:
            tiles[cell] = tile
        else:
            tiles.pop(cell, None)
    mission["board"]["tiles"] = [tiles[cell] for cell in sorted(tiles, key=lambda c: (c[1], c[0]))]
    mission["goal"] = [list(cell) for cell in sorted(goals, key=lambda c: (c[1], c[0]))]
    return data


@dataclass(frozen=True)
class GesturePreview:
    revision: int
    mission_id: str
    cells: tuple[tuple[int, int], ...]
    brush: str


class MapStudio:
    """Headless R5 orchestration shared by GUI tools and deterministic tests."""

    def __init__(self, authoring: AuthoringSession, mission_id: str | None = None):
        self.authoring = authoring
        ids = self.map_ids()
        self.mission_id = mission_id or ids[0]
        if self.mission_id not in ids:
            raise RuleError("Unknown map")
        self.clipboard = None
        self.layers = LayerWorkspace()

    @classmethod
    def reference(cls):
        from drawtemp.sdk.reference import reference_project
        return cls(AuthoringSession.new(*reference_project()))

    def snapshot(self):
        return self.authoring.snapshot().to_dict()

    def map_ids(self):
        return tuple(m["id"] for m in self.snapshot()["content"]["missions"])

    def select_map(self, mission_id):
        if mission_id not in self.map_ids():
            raise RuleError("Unknown map")
        self.mission_id = mission_id

    def mission(self):
        return _mission(self.snapshot()["content"], self.mission_id)

    def _change(self, transformation, kind="map-edit", *, mission_id=None):
        # Both documents are validated before history mutation.
        def guarded(content, project):
            before = deepcopy(content)
            after = transformation(content)
            self.layers.assert_editable(before, after)
            return after, project

        plan = self.authoring.preview_pair(
            guarded, kind=kind, mission_id=mission_id)
        return self.authoring.apply(plan)

    def create(self, mission_id, name, width=12, height=12):
        result = self._change(
            lambda content: add_blank_mission(content, mission_id, name, width, height),
            kind="map-create")
        self.mission_id = mission_id
        return result

    def duplicate(self, new_id, name):
        current = self.mission_id
        def transform(content):
            src = _mission(content, current)
            if any(m["id"] == new_id for m in content["missions"]):
                raise RuleError("Map identifier already in use")
            # Preserve authored objects; the new mission has independent copies.
            copy = deepcopy(src)
            copy.update(id=new_id, name=name, next_missions=[])
            content["missions"].append(copy)
            return content
        result = self._change(transform, kind="map-duplicate")
        self.mission_id = new_id
        return result

    def rename(self, name):
        mid = self.mission_id
        def transform(content):
            mission = _mission(content, mid)
            return set_mission_properties(
                content, mid, name=name, objective=mission["objective"],
                reward=mission["reward"], next_missions=mission["next_missions"])
        return self._change(transform, kind="map-rename", mission_id=mid)

    def set_objective(self, objective):
        mid = self.mission_id
        def transform(content):
            mission = _mission(content, mid)
            return set_mission_properties(
                content, mid, name=mission["name"], objective=objective,
                reward=mission["reward"], next_missions=mission["next_missions"])
        return self._change(transform, kind="map-objective", mission_id=mid)

    def preview(self, cells, brush):
        selected = selected_cells(self.snapshot()["content"], self.mission_id, list(cells))
        if not selected:
            raise RuleError("Empty gesture")
        return GesturePreview(self.authoring.revision, self.mission_id, selected, brush)

    def commit(self, preview):
        if (not isinstance(preview, GesturePreview) or
                preview.revision != self.authoring.revision or
                preview.mission_id != self.mission_id):
            raise AuthoringError("stale_revision", "map-commit", "Map or revision changed")
        return self._change(
            lambda content: _paint(content, self.mission_id, preview.cells, preview.brush),
            kind="map-paint", mission_id=self.mission_id)

    def paint(self, cells, brush="surface:grass"):
        return self.commit(self.preview(cells, brush))

    def rectangle_cells(self, a, b):
        return cells_in_rectangle(self.snapshot()["content"], self.mission_id, a, b)

    def rectangle(self, a, b, brush):
        return self.paint(cells_in_rectangle(self.snapshot()["content"], self.mission_id, a, b),
                          brush)

    def line(self, a, b, brush):
        return self.paint(_line(a, b), brush)

    def flood(self, start, brush):
        mission = self.mission()
        start = _cell(mission, start)
        if not brush.startswith("surface:"):
            raise RuleError("Flood requires a surface")
        tiles = {tuple(t["pos"]): t for t in mission["board"]["tiles"]}
        source = tiles.get(start, {}).get("surface", "grass")
        target = brush.split(":", 1)[1]
        if source == target:
            return None
        width, height = mission["board"]["width"], mission["board"]["height"]
        seen = {start}
        pending = deque([start])
        while pending:
            x, y = pending.popleft()
            for cell in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                xx, yy = cell
                if (cell not in seen and 0 <= xx < width and 0 <= yy < height
                        and tiles.get(cell, {}).get("surface", "grass") == source):
                    seen.add(cell)
                    pending.append(cell)
        return self.paint(seen, brush)

    def smart(self, anchors, brush, *, radius=1, shape="diamond"):
        cells = smart_brush_cells(self.snapshot()["content"], self.mission_id,
                                  anchors, radius=radius, shape=shape)
        return self.paint(cells, brush)

    def sample(self, cell):
        mission = self.mission()
        cell = _cell(mission, cell)
        tiles = {tuple(t["pos"]): t for t in mission["board"]["tiles"]}
        return tiles.get(cell, {}).get("surface", "grass")

    def copy(self, cells):
        self.clipboard = copy_terrain(self.snapshot()["content"], self.mission_id, cells)
        return self.clipboard

    def paste(self, anchor):
        if self.clipboard is None:
            raise RuleError("Copy terrain before pasting")
        return self._change(
            lambda content: paste_terrain(content, self.mission_id,
                                          self.clipboard, anchor),
            kind="map-paste", mission_id=self.mission_id)

    def structure(self, name, anchor):
        if name not in ("Maison", "Pont", "Tour", "Ruines", "Escalier", "Rempart"):
            raise RuleError("Unknown structure")
        return self._change(lambda content: place_structure(
            content, self.mission_id, name, anchor), kind="map-structure",
            mission_id=self.mission_id)

    def move_actor(self, unit_id, cell):
        return self._change(lambda content: move_unit(
            content, self.mission_id, unit_id, cell), kind="map-actor",
            mission_id=self.mission_id)

    def add_actor(self, unit_id, name, team, cell):
        return self._change(lambda content: add_unit(
            content, self.mission_id, unit_id, name, team, cell),
            kind="map-actor-add", mission_id=self.mission_id)

    def diagnostics(self):
        """Supplement canonical validation with bounded reachability warnings."""
        mission = self.mission()
        width, height = mission["board"]["width"], mission["board"]["height"]
        tiles = {tuple(t["pos"]): t for t in mission["board"]["tiles"]}
        blocked = {cell for cell, tile in tiles.items() if tile.get("blocked", False)}
        positions = [tuple(unit["pos"]) for unit in mission["units"]
                     if unit["team"] == "player"]
        seen = set(positions)
        pending = deque(positions)
        while pending:
            x, y = pending.popleft()
            for cell in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                xx, yy = cell
                if (0 <= xx < width and 0 <= yy < height and cell not in blocked
                        and cell not in seen):
                    seen.add(cell)
                    pending.append(cell)
        warnings = []
        for cell in mission.get("goal", []):
            if tuple(cell) not in seen:
                warnings.append("Unreachable goal at " + str(tuple(cell)))
        for unit in mission["units"]:
            if tuple(unit["pos"]) in blocked:
                warnings.append("Actor on blocked tile: " + unit["id"])
        if not positions:
            warnings.append("No player spawn")
        return tuple(warnings)

    def playtest(self, *, max_steps=100):
        """Run a bounded *detached* headless playtest of the selected map.

        No changes to campaign progression, authored documents or global RNG.
        The interactive Qt Player is intentionally deferred to R12.
        """
        from drawtemp.core import Content, GameProject
        from drawtemp.sdk.simulation import Simulation
        documents = self.snapshot()
        content = Content.from_dict(documents["content"])
        project_data = deepcopy(documents["project"])
        project_data["campaigns"][0]["start_mission"] = self.mission_id
        project = GameProject.from_dict(project_data, content)
        campaign_id = project_data["campaigns"][0]["id"]
        playtest = Simulation.new(content, project, campaign_id, seed=17)
        scene = playtest.snapshot().scene
        if scene:
            choices = scene.get("choices", ())
            if choices:
                playtest.choose_story_option(choices[0]["id"])
        playtest.start_mission(self.mission_id)
        initial = playtest.snapshot()
        ending = playtest.simulate(max_steps=max_steps)
        return {
            "mission": self.mission_id, "seed": 17,
            "initial_mode": initial.mode, "final_mode": ending.mode,
            "result": ending.battle.get("result") if ending.battle else None,
            "remaining_steps_limit": max_steps,
        }

    def _repair_selection(self):
        # Undo of a just-created mission must not leave a dangling UI selection.
        if self.mission_id not in self.map_ids():
            self.mission_id = self.map_ids()[0]

    def undo(self):
        transition = self.authoring.undo()
        self._repair_selection()
        return transition

    def redo(self):
        transition = self.authoring.redo()
        self._repair_selection()
        return transition

    def save(self):
        # Check the sidecar *before* committing the two canonical documents.
        if self.layers.path is not None:
            self.layers.verify_disk()
        paths = self.authoring.save()
        self.layers.save()
        return paths

    def save_as(self, path):
        self.layers.verify_new_destination(path)
        paths = self.authoring.save_as(path)
        self.layers.save(path)
        return paths

    @classmethod
    def open(cls, content_path):
        result = cls(AuthoringSession.open(content_path))
        result.layers = LayerWorkspace(content_path=content_path)
        return result

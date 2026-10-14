"""R6: transactional P2D construction over the *existing* Content model.

No independent building schema, terrain renderer or Qt dependency lives here.
All changes go through AuthoringSession's revisioned preview/apply/history and
the historical, validated structure/interior/appearance transforms.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Optional

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.simulation import thaw
from sporebound.building_visuals import (
    BUILDINGS, FACADES, ROOFS, building_appearance, exterior_wall_cells,
    edit_building_appearance, set_building_window,
)
from sporebound.interior_levels import (
    FLOOR_FEATURES, FLOOR_SURFACES, MAX_INTERIOR_LEVEL,
    add_interior_floor, delete_interior_floor, edit_interior_tile,
)
from sporebound.iso_structures import (
    STRUCTURE_NAMES, door_slots, edit_structure, place_structure, remove_structure,
    structure_footprint, structure_template,
)
from sporebound.model import RuleError

CONSTRUCTION_VIEWS = ("renderer", "minimap", "inspector", "workspace")
PARTS = frozenset(("building", "roof", "facade", "window", "door", "floor"))


@dataclass(frozen=True)
class ConstructionPick:
    """R3 renderer hit: a persistent structure identity AND an actual world cell."""

    structure_id: str
    anchor: tuple[int, int]
    cell: tuple[int, int]
    part: str


@dataclass(frozen=True)
class BuildingInspector:
    """Detached, presentation-ready view of a canonical authored structure."""

    structure_id: str
    name: str
    anchor: tuple[int, int]
    footprint: tuple[tuple[int, int], ...]
    entry: Optional[tuple[int, int]]
    turns: int
    door_slot: int
    facade: Optional[str]
    roof: Optional[str]
    windows: tuple[tuple[int, int], ...]
    levels: tuple[int, ...]
    selected_part: str
    active_level: int


def catalog():
    """Existing, version-compatible presets; no shadow prefab format."""
    return tuple({
        "name": name,
        "size": (structure_template(name).width, structure_template(name).height),
        "door_slots": len(door_slots(name)),
        "interior": name in ("Maison", "Tour", "Ruines"),
        "appearance": name in BUILDINGS,
    } for name in STRUCTURE_NAMES)


def _mission(data, mission_id):
    return next(m for m in data["missions"] if m["id"] == mission_id)


def _record(data, mission_id, structure_id):
    mission = _mission(data, mission_id)
    return next((row for row in mission.get("structures", ())
                 if row["id"] == structure_id), None)


def _geometry(record):
    clip = structure_template(record["name"], record["turns"],
                              door_slot=record["door_slot"])
    anchor = tuple(record["anchor"])
    cells = structure_footprint(clip, anchor)
    entry = next(((anchor[0]+xy[0], anchor[1]+xy[1])
                  for xy, tile in zip(clip.offsets, clip.terrain)
                  if tile.get("surface") == "cobble" and not tile.get("blocked")),
                 None)
    return cells, entry


class ConstructionWorkspace:
    """Stateful R6 workspace facade, sharing R1/R5's authoring transaction.

    The renderer supplies a hit with structure ID, part and world cell; the
    SDK validates this information against current canonical geometry. It does
    NOT infer hits from pixels (R3 must provide the hit test).
    """

    def __init__(self, authoring: AuthoringSession, mission_id: str):
        if not isinstance(authoring, AuthoringSession):
            raise TypeError("ConstructionWorkspace expects AuthoringSession")
        self.authoring = authoring
        self.mission_id = mission_id
        self._pick = None
        self._selection_revision = None
        self._level = 0
        self._cutaway = False
        if mission_id not in {m["id"] for m in self._content()["missions"]}:
            raise AuthoringError("unknown_mission", "construction", mission_id)

    def _content(self):
        return thaw(self.authoring.snapshot().content)

    @property
    def pick(self):
        return self._pick

    @property
    def active_level(self):
        return self._level

    @property
    def cutaway(self):
        return self._cutaway

    def set_cutaway(self, enabled: bool):
        if type(enabled) is not bool:
            raise ValueError("Cutaway must be a boolean")
        self._cutaway = enabled

    def set_level(self, level: int):
        if type(level) is not int or not 0 <= level <= MAX_INTERIOR_LEVEL:
            raise ValueError("Unknown floor level")
        if level > 0 and self._pick is not None:
            if level not in self.inspect().levels:
                raise ValueError("Create this interior floor first")
        self._level = level

    def clear_selection(self):
        self._pick = None
        self._selection_revision = None
        self._level = 0

    def select(self, hit: ConstructionPick | None):
        """Reject a stale or spoofed pixel hit before any edit is possible."""
        if hit is None:
            self.clear_selection()
            return None
        if not isinstance(hit, ConstructionPick) or hit.part not in PARTS:
            raise AuthoringError("invalid_pick", "select", "Unknown building part")
        data = self._content()
        record = _record(data, self.mission_id, hit.structure_id)
        if record is None or tuple(record["anchor"]) != hit.anchor:
            raise AuthoringError("stale_pick", "select", "Building changed since picking")
        cells, entry = _geometry(record)
        if (type(hit.cell) is not tuple or len(hit.cell) != 2 or
                any(type(x) is not int for x in hit.cell) or hit.cell not in cells):
            raise AuthoringError("invalid_pick", "select", "Pick lies outside this building")
        if hit.part == "door" and hit.cell != entry:
            raise AuthoringError("invalid_pick", "select", "Not a door")
        x0, y0 = hit.anchor
        walls = {(x0+x, y0+y) for x, y in exterior_wall_cells(record)} if record["name"] in BUILDINGS else set()
        if hit.part in ("facade", "window") and hit.cell not in walls:
            raise AuthoringError("invalid_pick", "select", "Not an exterior wall")
        if hit.part == "window":
            visual = building_appearance(record)
            if (hit.cell[0]-x0, hit.cell[1]-y0) not in {tuple(c) for c in visual["windows"]}:
                raise AuthoringError("invalid_pick", "select", "No window at this wall")
        self._pick = hit
        self._selection_revision = self.authoring.revision
        self._level = 0
        return self.inspect()

    def _selected(self):
        hit = self._pick
        if hit is None:
            raise AuthoringError("no_selection", "construction", "Select a building first")
        if self._selection_revision != self.authoring.revision:
            raise AuthoringError("stale_pick", "construction", "Select the building again")
        record = _record(self._content(), self.mission_id, hit.structure_id)
        if record is None or tuple(record["anchor"]) != hit.anchor:
            raise AuthoringError("stale_pick", "construction", "Building no longer exists")
        return record

    def inspect(self):
        record = self._selected()
        data = self._content()
        cells, entry = _geometry(record)
        visual = building_appearance(record) if record["name"] in BUILDINGS else None
        levels = tuple(sorted(row["level"] for row in _mission(data, self.mission_id)
                              .get("interior_floors", ())
                              if row["structure_id"] == record["id"]))
        anchor = tuple(record["anchor"])
        return BuildingInspector(
            record["id"], record["name"], anchor, tuple(cells), entry,
            record["turns"], record["door_slot"],
            visual["facade"] if visual else None,
            visual["roof"] if visual else None,
            tuple((anchor[0]+x, anchor[1]+y) for x, y in visual["windows"])
            if visual else (),
            levels, self._pick.part, self._level,
        )

    def list_buildings(self):
        """Safe immutable summaries, ordered by canonical mission records."""
        return tuple((row["id"], row["name"], tuple(row["anchor"]))
                     for row in _mission(self._content(), self.mission_id)
                     .get("structures", ()))

    def _preview(self, kind, transform):
        return self.authoring.preview_pair(
            lambda content, project: (transform(content), project),
            kind="construction:" + kind, mission_id=self.mission_id,
            views=CONSTRUCTION_VIEWS,
        )

    def preview_place(self, name, anchor, *, turns=0, door_slot=0):
        if name not in STRUCTURE_NAMES:
            raise ValueError("Unknown structure preset")
        return self._preview("place", lambda content: place_structure(
            content, self.mission_id, name, anchor, turns, door_slot=door_slot))

    def preview_move(self, anchor):
        record = self._selected()
        return self._preview("move", lambda content: edit_structure(
            content, self.mission_id, tuple(record["anchor"]), anchor=anchor))

    def preview_duplicate(self, anchor):
        record = self._selected()
        return self._preview("duplicate", lambda content: edit_structure(
            content, self.mission_id, tuple(record["anchor"]),
            anchor=anchor, duplicate=True))

    def preview_rotate(self, turns):
        record = self._selected()
        return self._preview("rotate", lambda content: edit_structure(
            content, self.mission_id, tuple(record["anchor"]), quarter_turns=turns))

    def preview_door(self, door_slot):
        record = self._selected()
        return self._preview("door", lambda content: edit_structure(
            content, self.mission_id, tuple(record["anchor"]), door_slot=door_slot))

    def preview_remove(self):
        record = self._selected()
        return self._preview("remove", lambda content: remove_structure(
            content, self.mission_id, tuple(record["anchor"])))

    def preview_material(self, *, facade=None, roof=None):
        record = self._selected()
        if record["name"] not in BUILDINGS:
            raise AuthoringError("unsupported_part", "material",
                                 "This structure has no editable facade or roof")
        return self._preview("material", lambda content: edit_building_appearance(
            content, self.mission_id, record["id"], facade=facade, roof=roof))

    def preview_window(self, cell, *, present=True):
        record = self._selected()
        return self._preview("window", lambda content: set_building_window(
            content, self.mission_id, record["id"], cell, present=present))

    def preview_floor_add(self, level):
        record = self._selected()
        return self._preview("floor-add", lambda content: add_interior_floor(
            content, self.mission_id, record["id"], level))

    def preview_floor_remove(self, level):
        record = self._selected()
        return self._preview("floor-remove", lambda content: delete_interior_floor(
            content, self.mission_id, record["id"], level))

    def preview_floor_tile(self, level, cell, *, surface=None, feature=None,
                           present=True):
        record = self._selected()
        return self._preview("floor-tile", lambda content: edit_interior_tile(
            content, self.mission_id, record["id"], level, cell,
            surface=surface, feature=feature, present=present))

    def apply(self, plan):
        """Commit a single validated gesture and rebind selection by stable ID."""
        before = {sid for sid, _, _ in self.list_buildings()}
        hit = self._pick
        result = self.authoring.apply(plan)
        self._refresh(hit, before, result.kind)
        return result

    def undo(self):
        transition = self.authoring.undo()
        self._refresh(self._pick, set(), "undo")
        return transition

    def redo(self):
        transition = self.authoring.redo()
        self._refresh(self._pick, set(), "redo")
        return transition

    def _refresh(self, hit, previous_ids, kind):
        records = {row["id"]: row for row in _mission(
            self._content(), self.mission_id).get("structures", ())}
        if kind == "construction:place":
            created = sorted(set(records) - previous_ids)
            if created:
                row = records[created[0]]
                hit = ConstructionPick(row["id"], tuple(row["anchor"]),
                                       tuple(row["anchor"]), "building")
        if hit and hit.structure_id in records:
            row = records[hit.structure_id]
            anchor = tuple(row["anchor"])
            candidate = ConstructionPick(hit.structure_id, anchor, anchor, "building")
            self._pick = candidate
            self._selection_revision = self.authoring.revision
            if self._level not in tuple(
                floor["level"] for floor in _mission(self._content(), self.mission_id)
                .get("interior_floors", ())
                if floor["structure_id"] == hit.structure_id):
                self._level = 0
        else:
            self.clear_selection()

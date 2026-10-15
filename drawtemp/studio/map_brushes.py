"""R5.4 smart-map brush previews over canonical R1 authoring transactions.

Footprints, neighbour invalidation and AutoBlend are delegated to the existing
headless map-builder/terrain modules. Preview never changes Content, RNG or
history; commit uses the exact validated plan (no recomputing a stale stroke).
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from drawtemp.core import RuleError
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.sdk.simulation import thaw
from drawtemp.assets.terrain import map_material
from sporebound.map_builder4 import smart_brush_cells
from sporebound.map_authoring import _mission
from sporebound.model import Board, Tile
from sporebound.terrain_autoblend import terrain_dependents, _reserved_cells
from sporebound.terrain_schema import SURFACES, FEATURES


@dataclass(frozen=True)
class BrushNeighbour:
    x: int
    y: int
    surface: str
    edges: tuple
    painted: bool


@dataclass(frozen=True)
class SmartBrushPreview:
    mission_id: str
    source_revision: int
    brush: str
    radius: int
    shape: str
    cells: tuple
    neighbours: tuple[BrushNeighbour, ...]
    plan: object


def _board(raw):
    board = raw["board"]
    return Board(
        board["width"], board["height"],
        {tuple(tile["pos"]): Tile(**{k: value for k, value in tile.items()
                                      if k != "pos"}) for tile in board["tiles"]},
    )


def _paintable_cells(mission, cells, brush):
    """Smart brush preserves existing gameplay references and authored work.

    Water/bridge are protected from generic brushes, but an explicit bridge
    brush can bridge water. The older direct pencil remains available when a
    user intentionally wants to replace terrain by hand.
    """
    protected = _reserved_cells(mission)
    tiles = {tuple(row["pos"]): row for row in mission["board"]["tiles"]}
    result = []
    for cell in cells:
        if cell in protected:
            continue
        old = tiles.get(cell, {})
        if brush.startswith("surface:"):
            old_surface = old.get("surface", "grass")
            if old.get("feature") or old.get("hazard", 0) or old.get("cover", 0) or old.get("height", 0):
                continue
            if old_surface in ("water", "bridge") and brush != "surface:bridge":
                continue
            if old_surface == "bridge" and brush == "surface:bridge":
                continue
        elif brush.startswith("feature:"):
            if old.get("feature") or old.get("blocked") or old.get("surface") in ("water", "bridge"):
                continue
        result.append(cell)
    return tuple(result)


def preview_smart(studio, anchors, brush, *, radius=1, shape="diamond"):
    """Return validated detached preview + affected 4-neighbour AutoBlend."""
    if not isinstance(brush, str) or not (
        brush.startswith("surface:") and brush[8:] in SURFACES
        or brush.startswith("feature:") and brush[8:] in FEATURES - {""}
    ):
        raise RuleError("Unknown smart brush")
    snapshot = studio.snapshot()
    mission_id = studio.mission_id
    footprint = smart_brush_cells(snapshot["content"], mission_id, anchors,
                                  radius=radius, shape=shape)
    cells = _paintable_cells(_mission(snapshot["content"], mission_id), footprint, brush)
    if not cells:
        return None

    def guarded(content, project):
        before = thaw(content)
        # _paint modifies only the validated Content dictionary supplied by R1.
        from drawtemp.studio.map_authoring import _paint
        updated = _paint(content, mission_id, cells, brush)
        studio.layers.assert_editable(before, updated)
        return updated, project

    plan = studio.authoring.preview_pair(guarded, kind="map-smart-brush",
                                         mission_id=mission_id)
    staged = thaw(plan.content)
    if staged == snapshot["content"]:
        return None
    board = _board(_mission(staged, mission_id))
    touched = frozenset(cells)
    neighbours = []
    for x, y in sorted(terrain_dependents(board, cells), key=lambda c: (c[1], c[0])):
        material = map_material(board, x, y)
        neighbours.append(BrushNeighbour(x, y, material.name, material.edges,
                                         (x, y) in touched))
    return SmartBrushPreview(mission_id, plan.source_revision, brush, radius,
                             shape, tuple(cells), tuple(neighbours), plan)


def commit_smart(studio, preview):
    if not isinstance(preview, SmartBrushPreview):
        raise RuleError("Expected smart brush preview")
    if studio.mission_id != preview.mission_id or studio.authoring.revision != preview.source_revision:
        raise AuthoringError("stale_revision", "map-smart-brush",
                             "Map selection or source revision changed")
    return studio.authoring.apply(preview.plan)

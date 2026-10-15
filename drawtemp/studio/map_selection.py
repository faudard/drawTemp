"""R5.7 selection geometry + transactional map transformations.

This module deliberately reuses the existing terrain clipboard and transform
contract. No alternative Content schema, history or Qt dependency is introduced.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.core import RuleError
from drawtemp.sdk.authoring import AuthoringError
from sporebound.map_authoring import (
    _mission, copy_terrain, selected_cells, TerrainClipboard,
)
from sporebound.map_transform import (
    _validate_clipboard, group_entities, transform_terrain,
)
from sporebound.iso_structures import structure_template, structure_footprint
from sporebound.model import require

OPERATIONS = ("move", "duplicate", "paste", "rotate_cw", "rotate_ccw",
              "mirror_x", "mirror_y")
MAX_SELECTION = 4096


def _sorted(cells):
    return tuple(sorted(cells, key=lambda pos: (pos[1], pos[0])))


def rectangle_selection(data, mission_id, first, last):
    from sporebound.map_authoring import cells_in_rectangle
    cells = cells_in_rectangle(data, mission_id, first, last)
    require(len(cells) <= MAX_SELECTION, "Selection exceeds 4096 cells")
    return cells


def _bresenham(a, b):
    from drawtemp.studio.map_authoring import _line
    return _line(a, b)


def _on_segment(point, a, b):
    px, py = point
    ax, ay = a
    bx, by = b
    return ((px-ax)*(by-ay) == (py-ay)*(bx-ax)
            and min(ax, bx) <= px <= max(ax, bx)
            and min(ay, by) <= py <= max(ay, by))


def lasso_selection(data, mission_id, vertices):
    """Rasterize a freehand closed polygon over tile centres, including edges.

    Degenerate one- and two-point gestures select a cell or a continuous line.
    Works headlessly with integer cells and does not rely on screen pixels.
    """
    require(isinstance(vertices, (list, tuple)) and bool(vertices),
            "Draw a lasso on the map")
    mission = _mission(data, mission_id)
    points = selected_cells(data, mission_id, vertices)
    require(len(vertices) <= 16384, "Lasso path exceeds 16384 points")
    # Preserve gesture ordering: selected_cells only validates and sorts.
    checked = set(points)
    path = []
    for raw in vertices:
        cell = tuple(raw)
        require(cell in checked, "Invalid lasso vertex")
        if not path or path[-1] != cell:
            path.append(cell)
    if len(path) < 3 or len(set(path)) < 3:
        result = set()
        for a, b in zip(path, path[1:]):
            result.update(_bresenham(a, b))
        if not result:
            result = set(path)
        return _sorted(result)
    minx = min(x for x, _ in path)
    maxx = max(x for x, _ in path)
    miny = min(y for _, y in path)
    maxy = max(y for _, y in path)
    require((maxx-minx+1)*(maxy-miny+1) <= 65536,
            "Lasso bounding box too large")
    segments = list(zip(path, path[1:] + path[:1]))
    chosen = set()
    for y in range(miny, maxy+1):
        for x in range(minx, maxx+1):
            point = (x, y)
            if any(_on_segment(point, a, b) for a, b in segments):
                chosen.add(point)
                continue
            inside = False
            for (ax, ay), (bx, by) in segments:
                if (ay > y) != (by > y):
                    if x < ax + (y-ay) * (bx-ax)/(by-ay):
                        inside = not inside
            if inside:
                chosen.add(point)
    require(len(chosen) <= MAX_SELECTION, "Selection exceeds 4096 cells")
    return _sorted(chosen)


def union_selection(data, mission_id, current, added):
    """Additive selection; a disjoint union is allowed, duplicates are removed."""
    if not current:
        return selected_cells(data, mission_id, list(added))
    result = selected_cells(data, mission_id, list(current) + list(added))
    require(len(result) <= MAX_SELECTION, "Selection exceeds 4096 cells")
    return result


@dataclass(frozen=True)
class RegionStamp:
    """Detached terrain/goal clipboard. Entity identities are never duplicated."""
    clip: TerrainClipboard
    origin_mission: str


@dataclass(frozen=True)
class TransformPreview:
    source_revision: int
    mission_id: str
    operation: str
    anchor: tuple[int, int]
    source_cells: tuple
    target_cells: tuple
    preview_cells: tuple  # tuples (x,y,terrain data, is_goal)
    moved_units: tuple[str, ...]
    moved_objects: tuple[str, ...]
    plan: object


def _reserved(mission):
    structures = set()
    for building in mission.get("structures", ()):
        stamp = structure_template(building["name"], building.get("turns", 0),
                                   door_slot=building.get("door_slot", 0))
        structures.update(structure_footprint(stamp, building["anchor"]))
    protected = set(structures)
    protected.update(tuple(z) for z in mission.get("goal", ()) if False)
    relic = mission.get("relic")
    if relic is not None:
        protected.add(tuple(relic))
    for deployment in mission.get("deployment", ()):
        protected.update(tuple(point) for point in deployment["cells"])
    for edge in mission.get("level_links", ()):
        for key in ("from", "to"):
            protected.add(tuple(edge[key][1:]))
    for floor in mission.get("interior_floors", ()):
        # Floor footprints remain attached to an authored structure.
        building = next((s for s in mission.get("structures", ())
                         if s["id"] == floor["structure_id"]), None)
        if building:
            stamp = structure_template(building["name"], building.get("turns", 0),
                                       door_slot=building.get("door_slot", 0))
            protected.update(structure_footprint(stamp, building["anchor"]))
    return protected


def _occupied(mission):
    units = {}
    for actor in mission["units"]:
        x, y = actor["pos"]
        w, h = actor.get("footprint", (1, 1))
        units[actor["id"]] = {(x+i, y+j) for j in range(h) for i in range(w)}
    objects = {obj["id"]: {tuple(obj["pos"])} for obj in mission.get("objects", ())}
    return units, objects


def copy_region(data, mission_id, cells):
    selected = selected_cells(data, mission_id, list(cells))
    require(len(selected) <= MAX_SELECTION, "Selection exceeds 4096 cells")
    mission = _mission(data, mission_id)
    active = set(selected)
    require(not active.intersection(_reserved(mission)),
            "Selection intersects a structure, deployment, stair or relic")
    units, objects = _occupied(mission)
    require(not any(active & occupied for occupied in (*units.values(), *objects.values())),
            "Copying units or interactive objects would duplicate stable IDs")
    return RegionStamp(_validate_clipboard(copy_terrain(data, mission_id, selected)),
                       mission_id)


def prepare_transform(studio, cells=(), *, operation="move", anchor=None,
                      stamp=None, include_entities=True):
    """Dry-run entire Content+GameProject and expose the *same* R1 plan to commit.

    Rotation/mirroring deliberately apply in place unless another anchor is
    explicitly supplied. Paste and duplicate preserve originals.
    """
    require(operation in OPERATIONS, "Unknown selection transform")
    require(type(include_entities) is bool, "Invalid entity movement policy")
    snapshot = studio.snapshot()
    data = snapshot["content"]
    mission_id = studio.mission_id
    mission = _mission(data, mission_id)
    if operation == "paste":
        require(isinstance(stamp, RegionStamp), "Copy a region before pasting")
        source = ()
        clip = _validate_clipboard(stamp.clip)
    else:
        source = selected_cells(data, mission_id, list(cells))
        require(len(source) <= MAX_SELECTION, "Selection exceeds 4096 cells")
        clip = _validate_clipboard(copy_terrain(data, mission_id, source))
    x0 = min(x for x, _ in source) if source else 0
    y0 = min(y for _, y in source) if source else 0
    default_anchor = (x0, y0)
    if anchor is None:
        require(operation != "paste", "Choose a destination for paste")
        anchor = default_anchor
    require(isinstance(anchor, (tuple, list)) and len(anchor) == 2
            and all(type(v) is int for v in anchor), "Invalid transform anchor")
    anchor = tuple(anchor)

    if operation in ("rotate_cw", "rotate_ccw", "mirror_x", "mirror_y"):
        clip = transform_terrain(clip, operation)
    destination = tuple((anchor[0]+dx, anchor[1]+dy) for dx, dy in clip.offsets)
    width, height = mission["board"]["width"], mission["board"]["height"]
    require(len(set(destination)) == len(destination)
            and all(0 <= x < width and 0 <= y < height for x, y in destination),
            "Transformation exceeds the map bounds")
    origin, target = set(source), set(destination)
    protected = _reserved(mission)
    require(not (origin | target) & protected,
            "Structure, floor, deployment, stair or relic must be edited in its own workspace")
    existing_units, existing_objects = _occupied(mission)
    source_units = tuple(uid for uid, area in existing_units.items() if area & origin)
    source_objects = tuple(oid for oid, area in existing_objects.items() if area & origin)
    if source_units or source_objects:
        require(operation == "move" and include_entities,
                "Actors/objects can only be moved, never implicitly cloned or rotated")
        require(all(existing_units[uid] <= origin for uid in source_units),
                "Select the full footprint of every actor")
    moved_units = source_units if operation == "move" else ()
    moved_objects = source_objects if operation == "move" else ()
    for uid, area in existing_units.items():
        if uid not in moved_units:
            require(not (target & area), "Destination overlaps another actor")
    for oid, area in existing_objects.items():
        if oid not in moved_objects:
            require(not (target & area), "Destination overlaps an interactive object")

    # Non-selected authoring data must not be overwritten without consent.
    authored = {tuple(t["pos"]): t for t in mission["board"]["tiles"]}
    preserved = target - origin if operation not in ("paste", "duplicate") else target
    require(not any(pos in authored for pos in preserved),
            "Destination contains authored tiles; choose a clear location")
    old_goals = {tuple(point) for point in mission.get("goal", ())}
    require(not (old_goals & preserved),
            "Destination contains an existing mission objective")
    require(operation != "move" or anchor != default_anchor,
            "Choose a different destination to move the region")

    goals = set(clip.goals)
    preview_cells = tuple((x, y, deepcopy(tile), offset in goals)
                          for (x, y), offset, tile in
                          zip(destination, clip.offsets, clip.terrain))
    duplicate = operation in ("duplicate", "paste")

    def apply(content, project):
        before = deepcopy(content)
        current = _mission(content, mission_id)
        old_tiles = {tuple(t["pos"]): deepcopy(t)
                     for t in current["board"]["tiles"]}
        old_objectives = {tuple(point) for point in current.get("goal", ())}
        if not duplicate:
            for point in source:
                old_tiles.pop(point, None)
                old_objectives.discard(point)
        for point, offset, tile in zip(destination, clip.offsets, clip.terrain):
            if tile:
                old_tiles[point] = {"pos": list(point), **deepcopy(tile)}
            else:
                old_tiles.pop(point, None)
            if offset in goals:
                old_objectives.add(point)
            else:
                old_objectives.discard(point)
        current["board"]["tiles"] = [old_tiles[point] for point in _sorted(old_tiles)]
        current["goal"] = [list(point) for point in _sorted(old_objectives)]
        if moved_units or moved_objects:
            delta_x, delta_y = anchor[0]-default_anchor[0], anchor[1]-default_anchor[1]
            for actor in current["units"]:
                if actor["id"] in moved_units:
                    actor["pos"] = [actor["pos"][0]+delta_x, actor["pos"][1]+delta_y]
            for obj in current["objects"]:
                if obj["id"] in moved_objects:
                    obj["pos"] = [obj["pos"][0]+delta_x, obj["pos"][1]+delta_y]
                    if obj["kind"] == "defense":
                        obj["cells"] = [[x+delta_x, y+delta_y] for x, y in obj["cells"]]
        studio.layers.assert_editable(before, content)
        return content, project

    authoring_plan = studio.authoring.preview_pair(
        apply, kind="map-selection-" + operation, mission_id=mission_id)
    return TransformPreview(snapshot["revision"], mission_id, operation, anchor,
                            source, destination, preview_cells,
                            moved_units, moved_objects, authoring_plan)


def commit_transform(studio, preview):
    if not isinstance(preview, TransformPreview):
        raise RuleError("Expected a valid selection preview")
    if preview.mission_id != studio.mission_id or preview.source_revision != studio.authoring.revision:
        raise AuthoringError("stale_revision", "map-selection",
                             "The mission or map revision changed; refresh the preview")
    return studio.authoring.apply(preview.plan)

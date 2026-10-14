"""B1.2: read-only visual picking of existing isometric building components.

A hit is resolved from the *rendered* Canvas item tags. The result carries the
canonical structure ID and a real tile coordinate; no alternate map model or
authoring path is introduced. This module is headless and unit-testable.
"""
from dataclasses import dataclass

from .building_visuals import exterior_wall_cells


@dataclass(frozen=True)
class BuildingPartPick:
    structure_id: str
    anchor: tuple
    cell: tuple
    part: str  # roof, facade, window, door, building


_PARTS = (
    ('architecture_window', 'window'),
    ('architecture_door', 'door'),
    ('architecture_roof', 'roof'),
    ('architecture_ridge', 'roof'),
    ('architecture_cutaway', 'roof'),
    ('architecture_facade', 'facade'),
    ('architecture_sprite', 'building'),
    ('architecture_scenery_sprite', 'building'),
)


def _instance_from_tags(tags, instances):
    prefix = 'architecture_instance_'
    for tag in tags:
        if not tag.startswith(prefix):
            continue
        value = tag[len(prefix):]
        if not value.isdecimal():
            continue
        index = int(value)
        if index < len(instances):
            return instances[index]
    return None


def _wall_candidates(instance):
    if instance.name not in ('Maison', 'Tour'):
        return ()
    record = {'name': instance.name, 'turns': instance.turns,
              'door_slot': instance.door_slot}
    x0, y0 = instance.anchor
    return tuple((x0 + x, y0 + y) for x, y in exterior_wall_cells(record))


def _nearest_wall(geo, instance, px, py, *, only_windows=False):
    candidates = _wall_candidates(instance)
    if only_windows:
        x0, y0 = instance.anchor
        existing = {
            (x0 + dx, y0 + dy)
            for dx, dy in (instance.appearance or {}).get('windows', ())
        }
        candidates = tuple(c for c in candidates if c in existing)
    if not candidates:
        return instance.anchor

    def distance(cell):
        x, y = geo.center(cell)
        # Match the window glyph placement in iso_architecture.draw_architecture.
        y = y - 2 * geo.step - geo.cell_size * .26
        return (x - px) ** 2 + (y - py) ** 2

    return min(candidates, key=distance)


def _on_roof(geo, instance, px, py):
    # Matches the four roof corners, including the high roof silhouettes.
    from .iso_architecture import architecture_outline
    roof, _ = architecture_outline(geo, instance)
    inside = False
    x0, y0 = roof[-1]
    for x1, y1 in roof:
        if (y1 > py) != (y0 > py):
            cross = (x0 - x1) * (py - y1) / (y0 - y1) + x1
            if px < cross:
                inside = not inside
        x0, y0 = x1, y1
    return inside


def _on_door(geo, instance, px, py):
    """Approximate the actual doorway glyph when an atlas is a single PNG."""
    if instance.entry is None:
        return False
    dx, dy = instance.entry
    x = geo.origin_x + (dx - dy) * geo.half_width
    y = geo.origin_y + (dx + dy) * geo.half_height
    return (abs(px - x) <= geo.cell_size * .16 and
            y - geo.cell_size * .4 <= py <= y + geo.cell_size * .06)


def pick_building_part(canvas, geo, px, py, *, fallback_cell=None):
    """Pick a real building component at Canvas coordinates.

    Canvas painter order determines which visible architecture item wins.
    The fallback handles a ground-tile click where no architecture overlay was
    drawn (e.g. roof cutaway or a structure without a PNG). No mutations occur.
    """
    instances = tuple(getattr(geo, 'architecture_instances', ()) or ())
    if not instances:
        return None
    for item in reversed(canvas.find_overlapping(px, py, px, py)):
        tags = set(canvas.gettags(item))
        if 'architecture' not in tags:
            continue
        instance = _instance_from_tags(tags, instances)
        if instance is None:
            continue
        part = next((kind for tag, kind in _PARTS if tag in tags), None)
        if part is None:
            continue
        if part == 'building':
            # A projected roof's bounding diamond may overlap the doorway.
            # Prefer the smaller, intentional door hotspot over the broad
            # roof polygon when a single atlas PNG contains both.
            if _on_door(geo, instance, px, py):
                part = 'door'
            elif _on_roof(geo, instance, px, py):
                part = 'roof'
            else:
                part = 'facade'
        if part == 'window':
            cell = _nearest_wall(geo, instance, px, py, only_windows=True)
        elif part == 'facade':
            cell = _nearest_wall(geo, instance, px, py)
        elif part == 'door':
            cell = instance.entry or instance.anchor
        else:
            cell = instance.anchor
        return BuildingPartPick(instance.id, instance.anchor, cell, part)

    if fallback_cell is not None:
        for instance in reversed(instances):
            if fallback_cell not in instance.cells:
                continue
            if fallback_cell == instance.entry:
                part = 'door'
            elif fallback_cell in _wall_candidates(instance):
                part = 'facade'
            else:
                part = 'building'
            return BuildingPartPick(instance.id, instance.anchor,
                                    fallback_cell, part)
    return None

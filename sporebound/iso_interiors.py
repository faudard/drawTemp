"""Read-only interior projection for the shared isometric Studio/Player scene.

A mission has ONE tactical tile per (x, y). This module makes existing floors,
entrances and furniture legible in cutaway mode; it deliberately does not
introduce extra collision planes, simulated floors, or serialization fields.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class InteriorPlan:
    """Interior footprint inferred from current tactical tiles, not a prefab."""
    floors: frozenset
    walls: frozenset
    doors: frozenset
    furnishings: tuple


def interior_plan(board, building):
    """Inspect current cells, including edits made after placing a structure.

    Persistent architecture supplies the visual footprint, but tactical tiles
    remain authoritative: a newly painted wall is NOT a walkable floor.
    Legacy inferred architecture is supported by the same path.
    """
    floors, walls, furnishings = set(), set(), []
    for cell in building.cells:
        tile = board.tile(cell)
        if tile.blocked:
            walls.add(cell)
        else:
            floors.add(cell)
            if tile.feature and tile.feature not in {'stairs'}:
                furnishings.append((cell, tile.feature))
    doors = frozenset((building.entry,)) if building.entry in floors else frozenset()
    return InteriorPlan(frozenset(floors), frozenset(walls), doors,
                        tuple(sorted(furnishings)))


def draw_interior(canvas, geo, plan, instance_tag):
    """Draw thin, non-opaque guides above terrain and below actors.

    Never use solid polygons here: they could hide the underlying edited
    surface, a pickup, or a selectable tactical cell. The existing tile/prop
    rendering remains responsible for furniture and terrain appearance.
    """
    tags = ('architecture', 'architecture_interior', instance_tag)
    for cell in sorted(plan.floors, key=lambda c: (sum(c), c[0])):
        corners = geo.polygon(cell)
        canvas.create_polygon(*(v for point in corners for v in point),
                              fill='', outline='#d9c39b', width=1,
                              dash=(3, 3), tags=tags)
    for cell in sorted(plan.doors):
        cx, cy = geo.center(cell)
        radius = max(4, geo.cell_size // 9)
        canvas.create_oval(cx-radius, cy-radius // 2,
                           cx+radius, cy+radius // 2,
                           fill='', outline='#e9bb69', width=2,
                           tags=tags + ('architecture_entry',))


def draw_stacked_floors(canvas, geo, building, floors, selected_level, instance_tag):
    """Draw visual upper decks, leaving the tactical board untouched.

    The selected level is filled to make authored openings and material visible.
    Other levels are wireframes so they cannot mask the active working plane.
    """
    from .interior_levels import floor_absolute_cells, projected_floor_polygon
    from .iso_map import SURFACE_COLORS

    for floor in sorted(floors, key=lambda value: value['level']):
        level = floor['level']
        focused = level == selected_level
        tags = ('architecture', 'architecture_upper_floor',
                'architecture_floor_' + str(level), instance_tag)
        for (cell, tile) in floor_absolute_cells(building, floor):
            corners = projected_floor_polygon(geo, cell, level)
            canvas.create_polygon(
                *(value for point in corners for value in point),
                fill=SURFACE_COLORS[tile['surface']] if focused else '',
                outline='#e6bc68' if focused else '#8c8e9b',
                width=2 if focused else 1, tags=tags)
            if focused and tile['feature']:
                cx = sum(point[0] for point in corners) / 4
                cy = sum(point[1] for point in corners) / 4
                canvas.create_text(cx, cy, text=tile['feature'][:5],
                                   fill='#293441', font=('TkDefaultFont', 8),
                                   tags=tags + ('architecture_floor_prop',))
        # Label only a non-empty floor: empty decks are still valid (holes).
        if floor['tiles'] and focused:
            first = min(floor['tiles'], key=lambda t: (t['pos'][1], t['pos'][0]))
            x, y = building.anchor
            px = x + first['pos'][0]
            py = y + first['pos'][1]
            cx, cy = geo.center((px, py))
            canvas.create_text(cx, cy - level*3*geo.step - geo.half_height,
                               text='N' + str(level), fill='#674b23',
                               tags=tags + ('architecture_floor_label',))

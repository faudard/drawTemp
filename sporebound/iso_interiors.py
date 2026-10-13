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

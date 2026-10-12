"""Presentation-only architectural overlays inferred from intact structure stamps.

Recognise the 3.7.12 multi-cell terrain plans instead of persisting an extra
building object. Reopening old Content files remains byte-schema compatible.
Detection and placement pivot computation are pure/headless; Tk is not imported.
"""
from dataclasses import dataclass

from .iso_structures import structure_template, door_slots
from .model import RuleError, require


PIVOTS = ('Coin', 'Centre', 'Porte')
ARCHITECTURE_NAMES = ('Maison', 'Tour', 'Ruines')
# Only appearance tokens are matched; an edited wall, floor or entrance
# intentionally invalidates the derived facade until the stamp is reapplied.
MATCH_KEYS = ('surface', 'feature', 'height', 'blocked', 'cost', 'cover', 'hazard')


def placement_origin(clip, clicked, pivot='Coin'):
    """Map cursor cell to stamp's top-left anchor, using a selectable pivot."""
    require(pivot in PIVOTS, 'Unknown structure pivot')
    require(isinstance(clicked, (tuple, list)) and len(clicked) == 2 and
            all(type(n) is int for n in clicked),
            'Choose a valid structure cursor cell')
    if pivot == 'Centre':
        offset = ((clip.width - 1)//2, (clip.height - 1)//2)
    elif pivot == 'Porte':
        entries = [offset for offset, tile in zip(clip.offsets, clip.terrain)
                   if tile.get('surface') == 'cobble' and not tile.get('blocked')]
        require(len(entries) == 1,
                'This preset has no door; choose the Coin or Centre pivot')
        offset = entries[0]
    else:
        offset = (0, 0)
    return clicked[0]-offset[0], clicked[1]-offset[1]


@dataclass(frozen=True)
class ArchitectureInstance:
    name: str
    anchor: tuple
    turns: int
    door_slot: int
    width: int
    height: int
    cells: frozenset
    entry: tuple | None


def _same_tile(current, expected):
    defaults = dict(surface='grass', feature='', height=0, blocked=False,
                    cost=1, cover=0, hazard=0)
    return all(getattr(current, key) == expected.get(key, defaults[key])
               for key in MATCH_KEYS)


def architecture_instances(board):
    """Recognise complete, intact building stamps without changing saved data.

    Source candidates are explicit wall tiles; no scanning of every sparse
    board cell for every template. Overlapping matches resolve deterministically
    to the largest, then row-major instance.
    """
    anchors = [cell for cell, tile in board.tiles.items()
               if tile.feature == 'stone_wall']
    candidates = []
    for name in ARCHITECTURE_NAMES:
        for turns in range(4):
            for door_slot in range(len(door_slots(name))):
                clip = structure_template(name, turns, door_slot=door_slot)
                # A rotated plan need not begin with a wall in its top-left
                # cell. Derive each candidate's origin from one known wall
                # offset to recognise every orientation without full scanning.
                wall = next(((dx, dy) for (dx, dy), spec
                             in zip(clip.offsets, clip.terrain)
                             if spec.get('feature') == 'stone_wall'), None)
                if wall is None:
                    continue
                for wx, wy in anchors:
                    x, y = wx-wall[0], wy-wall[1]
                    if (x < 0 or y < 0 or x + clip.width > board.width
                            or y + clip.height > board.height):
                        continue
                    cells = tuple((x+dx, y+dy) for dx, dy in clip.offsets)
                    if not all(_same_tile(board.tile(cell), spec)
                               for cell, spec in zip(cells, clip.terrain)):
                        continue
                    entry = next(((x+dx, y+dy) for (dx, dy), spec
                                  in zip(clip.offsets, clip.terrain)
                                  if spec.get('surface') == 'cobble'
                                  and not spec.get('blocked')), None)
                    candidates.append(ArchitectureInstance(
                        name, (x, y), turns, door_slot, clip.width, clip.height,
                        frozenset(cells), entry))
    # Matching rotated symmetric stamps produce duplicates; choose one stable
    # representation and never paint two roofs over the same ground cells.
    claimed, result = set(), []
    for candidate in sorted(candidates,
                            key=lambda v: (-len(v.cells), v.anchor[1],
                                           v.anchor[0], v.name, v.turns, v.door_slot)):
        if not candidate.cells.intersection(claimed):
            result.append(candidate)
            claimed.update(candidate.cells)
    return tuple(result)


def roof_cutaway(instance, selected_cell, units):
    """Make interior editing and actors visible rather than hiding them below roof."""
    if selected_cell in instance.cells:
        return True
    for actor in units:
        if not getattr(actor, 'alive', True):
            continue
        x, y = actor.pos
        width, height = actor.footprint
        if any((x+dx, y+dy) in instance.cells
               for dy in range(height) for dx in range(width)):
            return True
    return False


def architecture_outline(geo, instance, wall_level=2):
    """Return a four-corner isometric roof and apex without Tk or 3D imports."""
    x, y = instance.anchor
    w, h = instance.width, instance.height
    hw, hh = geo.half_width, geo.half_height
    level = wall_level * geo.step
    def center(ix, iy):
        return (geo.origin_x + (ix-iy)*hw,
                geo.origin_y + (ix+iy)*hh - level)
    nx, ny = center(x, y)
    ex, ey = center(x+w-1, y)
    sx, sy = center(x+w-1, y+h-1)
    wx, wy = center(x, y+h-1)
    roof = ((nx, ny-hh), (ex+hw, ey), (sx, sy+hh), (wx-hw, wy))
    peak = ((roof[0][0]+roof[2][0])/2,
            (roof[1][1]+roof[3][1])/2 - geo.cell_size*.85)
    return roof, peak


def draw_architecture(canvas, geo, board, units, selected_cell, layers,
                      atlas=None):
    """Paint hand-authored sprite overlays with deterministic vector fallback.

    Cutaway remains a vector outline: opaque sprites may never hide occupants.
    Existing layer flags continue to work independently.
    """
    if not (layers.get('Bâtiments', True) or layers.get('Toitures', True)):
        return ()
    instances = architecture_instances(board)
    for building in instances:
        outline, peak = architecture_outline(geo, building)
        north, east, south, west = outline
        cutaway = roof_cutaway(building, selected_cell, units)
        use_sprite = ((layers.get('Bâtiments', True)
                       and (building.name == 'Ruines' or layers.get('Toitures', True)))
                      and not cutaway and atlas is not None)
        if use_sprite:
            photo = atlas.sprite(building.name, building.turns, geo.cell_size)
            if photo is not None:
                from .iso_building_atlas import building_sprite_top_left
                x, y = building_sprite_top_left(geo, building)
                canvas.create_image(x, y, image=photo, anchor='nw',
                                    tags=('architecture', 'architecture_sprite'))
                # The sprite includes both stone facades and a roof.
                continue
        if layers.get('Bâtiments', True):
            # Faces on the two foreground sides. Separate faces preserve
            # painter order; this remains a decorative visual layer only.
            depth = max(8, geo.step * 2)
            for a, b, tone in ((east, south, '#a89a85'),
                               (south, west, '#c0ad90')):
                canvas.create_polygon(a[0], a[1], b[0], b[1],
                                      b[0], b[1]+depth, a[0], a[1]+depth,
                                      fill=tone if not cutaway else '',
                                      outline='#66594e', width=2,
                                      tags=('architecture', 'architecture_facade'))
            if building.entry:
                # Door is an editable floor token (cobble), not a new entity.
                dx, dy = building.entry
                door_x = geo.origin_x + (dx-dy)*geo.half_width
                door_y = geo.origin_y + (dx+dy)*geo.half_height
                if not cutaway:
                    canvas.create_rectangle(door_x-geo.cell_size*.13,
                                            door_y-geo.cell_size*.34,
                                            door_x+geo.cell_size*.13,
                                            door_y+geo.cell_size*.03,
                                            fill='#684b37', outline='#dfc196',
                                            width=2,
                                            tags=('architecture', 'architecture_door'))
                    canvas.create_oval(door_x+geo.cell_size*.07,
                                       door_y-geo.cell_size*.16,
                                       door_x+geo.cell_size*.10,
                                       door_y-geo.cell_size*.13,
                                       fill='#edcb69', outline='',
                                       tags=('architecture', 'architecture_door'))
        if layers.get('Toitures', True) and building.name != 'Ruines':
            if cutaway:
                canvas.create_polygon(*_flat(outline), fill='', outline='#b66e5c',
                                      dash=(5, 4), width=2,
                                      tags=('architecture', 'architecture_cutaway'))
            else:
                tones = (('#a85749', '#c47759', '#b15d4b', '#dd9470')
                         if building.name == 'Maison' else
                         ('#5b6d79', '#8696a1', '#647f88', '#a9b6b9'))
                corners = (north, east, south, west)
                for index in range(4):
                    a, b = corners[index], corners[(index+1) % 4]
                    canvas.create_polygon(*_flat((a, b, peak)),
                                          fill=tones[index], outline='#534c48',
                                          width=2,
                                          tags=('architecture', 'architecture_roof'))
                canvas.create_line(*north, *peak, fill='#f1c49c',
                                   width=2, tags=('architecture', 'architecture_ridge'))
        elif layers.get('Bâtiments', True) and building.name == 'Ruines':
            canvas.create_line(*north, *east, fill='#6d7468',
                               width=3, dash=(4, 3),
                               tags=('architecture', 'architecture_ruin'))
    # Canvas items for selection are emitted by the existing tile pass and
    # must remain visible even when a roof spans several of those cells.
    canvas.tag_raise('selection')
    return instances


def _flat(points):
    return tuple(v for pair in points for v in pair)

"""Authorable stacked interior decks, separate from the 2D tactical board.

These are PRESENTATION-ONLY decks attached to persistent building identities.
Nothing in this module alters Battle, unit positions, line of sight or movement.
The distinction is explicit until a versioned multilevel gameplay contract exists.
"""
from copy import deepcopy

from .iso_structures import structure_template
from .model import Content, RuleError, require

MAX_INTERIOR_LEVEL = 3
FLOOR_SURFACES = frozenset(('stone', 'cobble', 'dirt', 'grass'))
FLOOR_FEATURES = frozenset(('', 'crate', 'lantern', 'pillar', 'stairs'))


def _mission(data, mid):
    require(type(data) is dict and type(data.get('missions')) is list,
            'Invalid content document')
    mission = next((m for m in data['missions'] if m.get('id') == mid), None)
    require(mission is not None, f'Unknown mission: {mid}')
    return mission


def _structure(structures, sid):
    require(type(sid) is str and bool(sid), 'Choose an authored structure')
    structure = next((s for s in structures if s['id'] == sid), None)
    require(structure is not None, f'Unknown structure: {sid}')
    require(structure['name'] in {'Maison', 'Tour', 'Ruines'},
            'Only buildings can have interior floors')
    return structure


def _dimensions(structure):
    clip = structure_template(structure['name'], structure['turns'],
                              door_slot=structure['door_slot'])
    return clip.width, clip.height, clip


def _level(value):
    require(type(value) is int and 1 <= value <= MAX_INTERIOR_LEVEL,
            f'Interior level must be 1..{MAX_INTERIOR_LEVEL}')


def validate_interior_floors(floors, structures):
    """Reject dangling references, invalid cells and ambiguous stacked decks.

    All cell positions are LOCAL to the rotated structure's footprint.
    This makes translations preserve content without changing world positions.
    Rotation changing the footprint must explicitly reconcile upper levels.
    """
    require(type(floors) is list, 'Interior floors must be a list')
    seen = set()
    for floor in floors:
        require(type(floor) is dict and
                set(floor) == {'structure_id', 'level', 'tiles'},
                'Invalid interior floor fields')
        sid, level = floor['structure_id'], floor['level']
        building = _structure(structures, sid)
        _level(level)
        require((sid, level) not in seen, 'Duplicate interior floor')
        seen.add((sid, level))
        width, height, _ = _dimensions(building)
        require(type(floor['tiles']) is list and
                len(floor['tiles']) <= width * height,
                'Invalid interior floor tiles')
        visited = set()
        for tile in floor['tiles']:
            require(type(tile) is dict and
                    set(tile) == {'pos', 'surface', 'feature'},
                    'Invalid interior tile fields')
            pos = tile['pos']
            require(type(pos) in (list, tuple) and len(pos) == 2
                    and all(type(n) is int for n in pos)
                    and 0 <= pos[0] < width and 0 <= pos[1] < height,
                    'Interior tile outside structure')
            require(tuple(pos) not in visited, 'Duplicate interior tile')
            visited.add(tuple(pos))
            require(type(tile['surface']) is str and
                    tile['surface'] in FLOOR_SURFACES,
                    'Invalid interior floor surface')
            require(type(tile['feature']) is str and
                    tile['feature'] in FLOOR_FEATURES,
                    'Invalid interior floor feature')


def _floor(mission, sid, level):
    _level(level)
    floor = next((f for f in mission.get('interior_floors', ())
                  if f['structure_id'] == sid and f['level'] == level), None)
    require(floor is not None, 'Create this interior floor first')
    return floor


def add_interior_floor(data, mid, sid, level=1):
    """Create a walkable-looking upper deck with a hole-free base floor plan.

    The authored plan copies the PRESET walkable cells, not the authoritative
    board. This lets designers add holes and props without mutating battle.
    """
    _level(level)
    updated = deepcopy(data)
    mission = _mission(updated, mid)
    building = _structure(mission.get('structures', ()), sid)
    require(all(not (f['structure_id'] == sid and f['level'] == level)
                for f in mission.get('interior_floors', ())),
            'Interior level already exists')
    _, _, clip = _dimensions(building)
    tiles = [{'pos': [dx, dy], 'surface': 'stone', 'feature': ''}
             for (dx, dy), tile in zip(clip.offsets, clip.terrain)
             if not tile.get('blocked', False)]
    mission.setdefault('interior_floors', []).append(
        {'structure_id': sid, 'level': level, 'tiles': tiles})
    return Content.from_dict(updated).to_dict()


def delete_interior_floor(data, mid, sid, level):
    updated = deepcopy(data)
    mission = _mission(updated, mid)
    _floor(mission, sid, level)
    mission['interior_floors'] = [
        floor for floor in mission['interior_floors']
        if not (floor['structure_id'] == sid and floor['level'] == level)]
    return Content.from_dict(updated).to_dict()


def edit_interior_tile(data, mid, sid, level, cell, *,
                       surface=None, feature=None, present=True):
    """Edit a cell on one floor atomically, with no effect on 2D board tiles.

    'present=False' makes a hole in the authored deck; 'present=True' can
    restore the cell. Features use None for unchanged, '' to erase a prop.
    """
    updated = deepcopy(data)
    mission = _mission(updated, mid)
    building = _structure(mission.get('structures', ()), sid)
    floor = _floor(mission, sid, level)
    w, h, _ = _dimensions(building)
    require(type(cell) in (tuple, list) and len(cell) == 2 and
            all(type(v) is int for v in cell),
            'Expected world cell (x,y)')
    dx, dy = cell[0]-building['anchor'][0], cell[1]-building['anchor'][1]
    require(0 <= dx < w and 0 <= dy < h,
            'Cell must be inside the selected structure')
    require(type(present) is bool, 'present must be boolean')
    require(surface is None or (type(surface) is str
                               and surface in FLOOR_SURFACES),
            'Unsupported interior floor surface')
    require(feature is None or (type(feature) is str
                               and feature in FLOOR_FEATURES),
            'Unsupported interior decoration')
    tiles = floor['tiles']
    item = next((t for t in tiles if t['pos'] == [dx, dy]), None)
    if not present:
        if item is not None:
            tiles.remove(item)
    else:
        if item is None:
            item = {'pos': [dx, dy], 'surface': 'stone', 'feature': ''}
            tiles.append(item)
        if surface is not None:
            item['surface'] = surface
        if feature is not None:
            item['feature'] = feature
    tiles.sort(key=lambda t: (t['pos'][1], t['pos'][0]))
    return Content.from_dict(updated).to_dict()


def floor_absolute_cells(building, floor):
    """World-cell visual annotations; never treated as Battle occupancy."""
    x0, y0 = building.anchor
    return tuple(((x0+row['pos'][0], y0+row['pos'][1]), row)
                 for row in floor['tiles'])


def projected_floor_polygon(geo, cell, level):
    """Project a deck visually above its footprint at a stable 2.5D offset."""
    _level(level)
    offset = level * 3 * geo.step
    return tuple((x, y-offset) for x, y in geo.polygon(cell))


def floor_hit_test(geo, building, floor, px, py):
    """Find an upper-deck cell beneath the pointer, not the ground tile."""
    level = floor['level']
    shift = level * 3 * geo.step
    for cell, _ in sorted(floor_absolute_cells(building, floor),
                          key=lambda item: (sum(item[0]), item[0][0]),
                          reverse=True):
        cx, cy = geo.center(cell)
        if (abs(px-cx)/geo.half_width +
                abs(py-(cy-shift))/geo.half_height <= 1):
            return cell
    return None

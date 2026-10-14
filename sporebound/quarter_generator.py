"""3.7.32E — deterministic, inspectable quarter suggestions.

Suggestions use the *existing* drawtemp_editor_group_prefab v1 schema; the
Player and Content never know a generator was involved. No Tk, no global RNG,
no side effects and no write until the author confirms the placement.
"""
from dataclasses import asdict
from random import Random

from .group_prefabs import (PREFAB_KIND, PREFAB_VERSION, _validate_prefab,
                            place_group_prefab)
from .iso_structures import structure_template
from .model import Tile, require
from .map_authoring import _mission

STYLES = ('Village', 'Marché', 'Fortifié')
SIZES = ((16, 14), (20, 16), (24, 18))


def _tile(**kwargs):
    return asdict(Tile(**kwargs))


def generate_quarter(*, style='Village', size=(16, 14), seed=1):
    """Create one complete prefab with houses, roads, props and a chest.

    All building placements use canonical structure templates, including their
    tactical wall/door tiles. The road and gardens remain independently
    editable in the standard group tree after placement.
    """
    require(style in STYLES, 'Unknown quarter style')
    require(type(size) in (tuple, list) and tuple(size) in SIZES,
            'Choose a supported quarter footprint')
    require(type(seed) is int and 0 <= seed <= 1_000_000,
            'Seed must be an integer from 0 to 1000000')
    width, height = size
    rng = Random(seed)
    road_x = width // 2
    road_y = height // 2
    roads = {(road_x, y) for y in range(height)}
    roads.update((x, road_y) for x in range(width))
    if style == 'Marché':
        roads.update((x, road_y + 1) for x in range(width))
    else:
        # Two short access drives connect the buildings to the main street.
        roads.update((x, 3) for x in range(4, road_x + 1))
        roads.update((x, height-3) for x in range(4, road_x + 1))

    plots = [(1, 1), (width-5, 1), (1, height-4), (width-5, height-4)]
    tower_corner = (seed + (1 if style == 'Fortifié' else 0)) % len(plots)
    building_specs = []
    for i, pos in enumerate(plots):
        name = 'Tour' if i == tower_corner else 'Maison'
        building_specs.append((name, pos, rng.choice((0, 2))))
    if style == 'Fortifié':
        building_specs.extend((
            ('Rempart', (1, 0), 0),
            ('Rempart', (width-6, 0), 0),
            ('Rempart', (1, height-1), 0),
            ('Rempart', (width-6, height-1), 0),
        ))
    tiles = {}
    structures = []
    footprint = set()
    for i, (name, anchor, turns) in enumerate(building_specs):
        clip = structure_template(name, turns)
        for (dx, dy), partial in zip(clip.offsets, clip.terrain):
            pos = (anchor[0] + dx, anchor[1] + dy)
            require(0 <= pos[0] < width and 0 <= pos[1] < height
                    and pos not in footprint,
                    'Generated buildings overlap or leave the quarter')
            footprint.add(pos)
            tiles[pos] = _tile(**partial)
        structures.append({'id': 'quarter_structure_' + str(i+1),
                           'name': name, 'anchor': list(anchor),
                           'turns': turns, 'door_slot': 0})
    roads -= footprint
    for pos in sorted(roads):
        tiles[pos] = _tile(surface='cobble' if style != 'Village' else 'dirt')
    # Leave the future chest position outside any authored building.
    market = (road_x+1, road_y+2)
    require(market not in footprint, 'The public square must remain walkable')
    if market in roads:
        roads.discard(market)
    tiles[market] = _tile(surface='cobble')
    garden = set()
    free = [(x, y) for y in range(1, height-1)
            for x in range(1, width-1)
            if (x, y) not in footprint | roads | {market}]
    rng.shuffle(free)
    for pos in free[:(7 if style == 'Fortifié' else 10)]:
        garden.add(pos)
        tiles[pos] = _tile(feature=rng.choice(('tree', 'bush', 'boulder')),
                           surface='grass')
    road_members = sorted(roads, key=lambda p: (p[1], p[0]))
    garden_members = sorted(garden, key=lambda p: (p[1], p[0]))
    groups = [
        {'id': 'quarter_root', 'name': style + ' — quartier', 'parent': None,
         'cells': [], 'unit_ids': [], 'object_ids': [], 'structure_ids': []},
        {'id': 'quarter_road', 'name': 'Rues et chemins', 'parent': 'quarter_root',
         'cells': [list(p) for p in road_members], 'unit_ids': [],
         'object_ids': [], 'structure_ids': []},
        {'id': 'quarter_buildings', 'name': 'Bâtiments', 'parent': 'quarter_root',
         'cells': [], 'unit_ids': [], 'object_ids': [],
         'structure_ids': [s['id'] for s in structures]},
        {'id': 'quarter_gardens', 'name': 'Jardins et décors', 'parent': 'quarter_root',
         'cells': [list(p) for p in garden_members], 'unit_ids': [],
         'object_ids': [], 'structure_ids': []},
        {'id': 'quarter_market', 'name': 'Coffre de la place', 'parent': 'quarter_root',
         'cells': [list(market)], 'unit_ids': [],
         'object_ids': ['quarter_chest'], 'structure_ids': []},
    ]
    prefab = {
        'kind': PREFAB_KIND, 'version': PREFAB_VERSION,
        'name': style + ' · seed ' + str(seed),
        'size': [width, height], 'groups': groups,
        'tiles': [{'pos': list(p), 'tile': tiles[p]}
                  for p in sorted(tiles, key=lambda p: (p[1], p[0]))],
        'structures': structures, 'interior_floors': [],
        'level_links': [], 'units': [], 'unit_levels': {},
        'objects': [{'id': 'quarter_chest', 'kind': 'chest',
                     'pos': list(market)}],
    }
    return _validate_prefab(prefab)


def suggest_quarters(*, style='Village', size=(16, 14), seed=1):
    require(type(seed) is int and 0 <= seed <= 999_998,
            'Seed must allow three suggestions (0..999998)')
    return tuple(generate_quarter(style=style, size=size, seed=seed + i)
                 for i in range(3))


def preview_quarter(data, mission_id, prefab, anchor):
    """Validate the exact proposed Content; report a deterministic before/after.

    A declined or invalid preview has zero effect on Content and Undo/Redo.
    Nothing is applied until the same GroupPrefabPlaceCommand is executed.
    """
    before = _mission(data, mission_id)
    result = place_group_prefab(data, mission_id, prefab, anchor)
    after = _mission(result, mission_id)
    old_tiles = {tuple(t['pos']): t for t in before['board']['tiles']}
    new_tiles = {tuple(t['pos']): t for t in after['board']['tiles']}
    changed = tuple(sorted((p for p in set(old_tiles) | set(new_tiles)
                            if old_tiles.get(p) != new_tiles.get(p)),
                           key=lambda p: (p[1], p[0])))
    summary = {
        'cells': len(changed),
        'structures': len(after.get('structures', ())) -
                      len(before.get('structures', ())),
        'objects': len(after['objects']) - len(before['objects']),
        'groups': len(after.get('editor_groups', ())) -
                  len(before.get('editor_groups', ())),
        'changed_cells': changed,
    }
    return result, summary

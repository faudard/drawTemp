"""Advanced, headless map editing: terrain transformations, group movement, stamps.

All operations are portable data transformations and do not import Tk, Battle
or presentation libraries. Terrain stamps deliberately omit actors and objects
because their identifiers and relations must not be duplicated implicitly.
"""
from copy import deepcopy
import json
from pathlib import Path

from .map_authoring import TerrainClipboard, _cell, _mission, _transaction, selected_cells
from .model import RuleError, require
from .storage import write_json

STAMP_KIND = 'sporebound_terrain_stamp'
STAMP_VERSION = 1
MAX_STAMP_BYTES = 2 * 1024 * 1024
TERRAIN_KEYS = frozenset({'height', 'cost', 'blocked', 'cover', 'hazard'})


def _validate_clipboard(clip):
    require(isinstance(clip, TerrainClipboard), 'Invalid terrain clipboard')
    w, h = clip.width, clip.height
    require(type(w) is int and type(h) is int and 1 <= w <= 128
            and 1 <= h <= 128, 'Invalid stamp dimensions')
    require(isinstance(clip.offsets, (tuple, list)) and
            0 < len(clip.offsets) <= w*h and len(clip.offsets) == len(clip.terrain),
            'Invalid stamp cells')
    def position(point):
        require(isinstance(point, (tuple, list)) and len(point) == 2
                and all(type(v) is int for v in point)
                and 0 <= point[0] < w and 0 <= point[1] < h,
                'Invalid stamp cell position')
        return tuple(point)
    positions = [position(p) for p in clip.offsets]
    require(len(set(positions)) == len(positions), 'Duplicate stamp cell')
    for tile in clip.terrain:
        require(isinstance(tile, dict) and set(tile) <= TERRAIN_KEYS,
                'Invalid stamp tile properties')
        require(type(tile.get('blocked', False)) is bool,
                'Invalid stamp blocked flag')
        for key, low, high in (('height', 0, 99), ('cost', 1, 99),
                               ('cover', 0, 100), ('hazard', 0, 10000)):
            if key in tile:
                require(type(tile[key]) is int and low <= tile[key] <= high,
                        f'Invalid stamp {key}')
    goals = [position(p) for p in clip.goals]
    require(len(set(goals)) == len(goals) and set(goals) <= set(positions),
            'Stamp goals must be selected cells')
    return clip


def transform_terrain(clip, operation):
    """Rotate clockwise/counterclockwise or mirror; preserve sparse offsets."""
    _validate_clipboard(clip)
    w, h = clip.width, clip.height
    require(operation in ('rotate_cw', 'rotate_ccw', 'mirror_x', 'mirror_y'),
            'Unknown terrain transform')
    if operation == 'rotate_cw':
        mapped, size = lambda x, y: (h-1-y, x), (h, w)
    elif operation == 'rotate_ccw':
        mapped, size = lambda x, y: (y, w-1-x), (h, w)
    elif operation == 'mirror_x':
        mapped, size = lambda x, y: (w-1-x, y), (w, h)
    else:
        mapped, size = lambda x, y: (x, h-1-y), (w, h)
    transformed = [(mapped(*p), deepcopy(t)) for p, t in zip(clip.offsets, clip.terrain)]
    transformed.sort(key=lambda item: (item[0][1], item[0][0]))
    goals = tuple(sorted((mapped(*p) for p in clip.goals),
                         key=lambda p: (p[1], p[0])))
    result = TerrainClipboard(*size,
                              tuple(point for point, _ in transformed),
                              tuple(tile for _, tile in transformed), goals)
    return _validate_clipboard(result)


def group_entities(data, mission_id, cells):
    """Collect IDs of units whose footprint overlaps selected cells and objects at cells."""
    selected = set(selected_cells(data, mission_id, cells))
    mission = _mission(data, mission_id)
    unit_ids = []
    for unit in mission['units']:
        x, y = unit['pos']
        width, height = unit.get('footprint', (1, 1))
        footprint = {(x+dx, y+dy) for dx in range(width) for dy in range(height)}
        if selected & footprint:
            unit_ids.append(unit['id'])
    object_ids = [obj['id'] for obj in mission['objects']
                  if tuple(obj['pos']) in selected]
    return tuple(unit_ids), tuple(object_ids)


def move_group(data, mission_id, unit_ids=(), object_ids=(), *, dx=0, dy=0):
    """Move a selected group atomically, retaining object IDs and references.

    Defenses carry their area-of-effect cells; passage destinations and unit
    patrol routes remain authored absolute positions and do not move.
    """
    require(type(dx) is int and type(dy) is int
            and (dx != 0 or dy != 0), 'Movement needs a nonzero integer offset')
    require(isinstance(unit_ids, (tuple, list)) and
            isinstance(object_ids, (tuple, list)), 'Invalid group IDs')
    require(all(isinstance(uid, str) for uid in (*unit_ids, *object_ids)),
            'Invalid group ID')
    require(bool(unit_ids or object_ids)
            and len(unit_ids) == len(set(unit_ids))
            and len(object_ids) == len(set(object_ids)),
            'Select unique existing entities')
    def change(mission):
        units = {u['id']: u for u in mission['units']}
        objects = {o['id']: o for o in mission['objects']}
        require(set(unit_ids) <= set(units) and set(object_ids) <= set(objects),
                'Group contains an unknown entity')
        for uid in unit_ids:
            unit = units[uid]
            x, y = unit['pos']
            unit['pos'] = _cell(mission, (x+dx, y+dy))
        for oid in object_ids:
            obj = objects[oid]
            x, y = obj['pos']
            obj['pos'] = _cell(mission, (x+dx, y+dy))
            if obj['kind'] == 'defense':
                obj['cells'] = [list(_cell(mission, (x+dx, y+dy)))
                                for x, y in obj['cells']]
    return _transaction(data, mission_id, change)


def stamp_document(clip, name):
    _validate_clipboard(clip)
    require(isinstance(name, str) and 0 < len(name.strip()) <= 100,
            'Give the stamp a name (1..100 characters)')
    result = {'kind': STAMP_KIND, 'version': STAMP_VERSION,
              'name': name.strip(), 'size': [clip.width, clip.height],
              'cells': [{'offset': list(p), 'terrain': deepcopy(tile)}
                        for p, tile in zip(clip.offsets, clip.terrain)],
              'goals': [list(p) for p in clip.goals]}
    require(len(json.dumps(result, ensure_ascii=False).encode('utf-8'))
            <= MAX_STAMP_BYTES, 'Stamp exceeds size limit')
    return result


def parse_stamp(data):
    require(isinstance(data, dict) and set(data) ==
            {'kind', 'version', 'name', 'size', 'cells', 'goals'},
            'Malformed terrain stamp')
    require(data['kind'] == STAMP_KIND and
            type(data['version']) is int and data['version'] == STAMP_VERSION,
            'Unsupported stamp format')
    require(isinstance(data['name'], str) and
            0 < len(data['name'].strip()) <= 100, 'Invalid stamp name')
    require(isinstance(data['size'], list) and len(data['size']) == 2,
            'Invalid stamp size')
    cells = data['cells']
    require(isinstance(cells, list) and
            0 < len(cells) <= 128*128, 'Invalid stamp cells')
    require(all(isinstance(item, dict) and
                set(item) == {'offset', 'terrain'} for item in cells),
            'Malformed stamp cell')
    require(isinstance(data['goals'], list), 'Invalid stamp goals')
    clip = TerrainClipboard(*data['size'],
                            tuple(item['offset'] for item in cells),
                            tuple(item['terrain'] for item in cells),
                            tuple(data['goals']))
    return _validate_clipboard(clip)


def save_stamp(path, clip, name):
    data = stamp_document(clip, name)
    write_json(path, data)
    return Path(path)


def load_stamp(path):
    path = Path(path)
    require(path.stat().st_size <= MAX_STAMP_BYTES,
            'Stamp exceeds size limit')
    try:
        document = json.loads(path.read_text(encoding='utf-8'))
        return parse_stamp(document)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            AttributeError, RecursionError) as exc:
        raise RuleError(f'Invalid terrain stamp: {exc}') from exc

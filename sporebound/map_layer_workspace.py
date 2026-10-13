"""Map Builder 4.0C: editor-only layer visibility, locks and active floor.

A per-content-file sidecar stores *workspace preferences*, never tactical
Content or player saves. No Tk/Battle imports. Strict validation and atomic IO.
"""
from copy import deepcopy
import json
from pathlib import Path

from .model import RuleError, require
from .storage import write_json

KIND = 'sporebound_map_builder_view'
VERSION = 1
MAX_BYTES = 256 * 1024
LAYERS = ('Terrain', 'Relief', 'Décors', 'Bâtiments', 'Toitures',
          'Déploiement', 'Objectifs', 'Objets', 'Unités', 'Étages')
TILE_KEYS = {
    'surface': 'Terrain', 'blocked': 'Terrain', 'cost': 'Terrain',
    'cover': 'Terrain', 'hazard': 'Terrain', 'height': 'Relief',
    'feature': 'Décors',
}
TILE_DEFAULTS = dict(surface='grass', blocked=False, cost=1, cover=0,
                     hazard=0, height=0, feature='')


def default_view():
    return {'visible': {name: True for name in LAYERS},
            'locked': {name: False for name in LAYERS},
            'active_level': 0, 'interiors': False}


def empty_views():
    return {'kind': KIND, 'version': VERSION, 'missions': {}}


def normalize_view(row):
    require(type(row) is dict and set(row) ==
            {'visible', 'locked', 'active_level', 'interiors'},
            'Invalid map view settings')
    for key in ('visible', 'locked'):
        values = row[key]
        require(type(values) is dict and set(values) == set(LAYERS)
                and all(type(v) is bool for v in values.values()),
                'Invalid map layer ' + key)
    require(type(row['active_level']) is int and 0 <= row['active_level'] <= 3,
            'Active map floor must be 0..3')
    require(type(row['interiors']) is bool, 'Invalid interior visibility')
    return deepcopy(row)


def normalize_views(payload):
    require(type(payload) is dict and set(payload) ==
            {'kind', 'version', 'missions'} and
            payload['kind'] == KIND and type(payload['version']) is int
            and payload['version'] == VERSION,
            'Unknown map view sidecar version')
    records = payload['missions']
    require(type(records) is dict and len(records) <= 256,
            'Invalid map view mission count')
    require(all(type(mid) is str and 0 < len(mid) <= 128
                for mid in records), 'Invalid map view mission ID')
    return {'kind': KIND, 'version': VERSION,
            'missions': {mid: normalize_view(v) for mid, v in records.items()}}


def view_sidecar_path(content_path):
    path = Path(content_path)
    return path.with_name(path.name + '.mapbuilder-view.json')


def load_views(content_path):
    path = view_sidecar_path(content_path)
    if not path.exists():
        return empty_views()
    try:
        require(path.stat().st_size <= MAX_BYTES, 'Map view file too large')
        return normalize_views(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise RuleError('Invalid map view sidecar: ' + str(exc)) from exc


def save_views(content_path, payload):
    validated = normalize_views(payload)
    require(len(json.dumps(validated, ensure_ascii=False).encode('utf-8'))
            <= MAX_BYTES, 'Map view settings too large')
    write_json(view_sidecar_path(content_path), validated)


def view_for(payload, mission_id):
    require(type(mission_id) is str and bool(mission_id),
            'Select a valid map mission')
    return deepcopy(payload['missions'].get(mission_id, default_view()))


def update_view(payload, mission_id, *, visible=None, locked=None,
                active_level=None, interiors=None):
    result = normalize_views(payload)
    current = view_for(result, mission_id)
    for field, mapping in (('visible', visible), ('locked', locked)):
        if mapping is not None:
            require(type(mapping) is dict and set(mapping) <= set(LAYERS)
                    and all(type(v) is bool for v in mapping.values()),
                    'Invalid ' + field + ' update')
            current[field].update(mapping)
    if active_level is not None:
        current['active_level'] = active_level
    if interiors is not None:
        current['interiors'] = interiors
    result['missions'][mission_id] = normalize_view(current)
    return normalize_views(result)


def changed_layers(before, after):
    """Diff authoring domains in existing missions, ignoring presentation flags.

    Per-tile comparisons use sparse default values. This allows one layer to
    be locked while editing a different layer of the *same* map cell.
    """
    left = {m['id']: m for m in before['missions']}
    right = {m['id']: m for m in after['missions']}
    result = {}
    for mid in left.keys() & right.keys():
        a, b = left[mid], right[mid]
        changed = set()
        board_a, board_b = a['board'], b['board']
        if ((board_a['width'], board_a['height']) !=
                (board_b['width'], board_b['height'])):
            changed.update(('Terrain', 'Relief', 'Décors'))
        tiles_a = {tuple(t['pos']): t for t in board_a['tiles']}
        tiles_b = {tuple(t['pos']): t for t in board_b['tiles']}
        for cell in tiles_a.keys() | tiles_b.keys():
            old, new = tiles_a.get(cell, {}), tiles_b.get(cell, {})
            for key, layer in TILE_KEYS.items():
                if old.get(key, TILE_DEFAULTS[key]) != new.get(key, TILE_DEFAULTS[key]):
                    changed.add(layer)
        if a.get('structures', []) != b.get('structures', []):
            changed.add('Bâtiments')
            old_structures = {s['id']: s for s in a.get('structures', [])}
            for current in b.get('structures', []):
                prior = old_structures.get(current['id'])
                if (prior is not None and
                        prior.get('appearance', {}).get('roof') !=
                        current.get('appearance', {}).get('roof')):
                    changed.add('Toitures')
        if (a.get('interior_floors', []) != b.get('interior_floors', []) or
                a.get('level_links', []) != b.get('level_links', []) or
                a.get('unit_levels', {}) != b.get('unit_levels', {})):
            changed.add('Étages')
        for key, layer in (('units', 'Unités'), ('objects', 'Objets'),
                           ('deployment', 'Déploiement'),
                           ('goal', 'Objectifs'), ('relic', 'Objectifs')):
            if a.get(key) != b.get(key):
                changed.add(layer)
        if changed:
            result[mid] = frozenset(changed)
    return result


def ensure_unlocked(before, after, views):
    """Reject locked authoring changes *before* Document commits/history.

    Undo/redo does not call this policy: they restore prior validated states.
    """
    normalize_views(views)
    for mid, touched in changed_layers(before, after).items():
        locked = view_for(views, mid)['locked']
        blocked = sorted(name for name in touched if locked[name])
        require(not blocked, 'Calque verrouillé : ' + ', '.join(blocked))

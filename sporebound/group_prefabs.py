"""Portable, versioned editor group prefabs.

A prefab is self-contained authoring data, *not* a runtime Battle object.
Import creates ordinary mission structures, units, objects, tiles, interior
decks and hierarchical editor groups. No parallel rendering or event engine.
"""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from .editor_groups import (_copy_identifier, _validate_document,
                            selected_group_closure, group_display_cells,
                            MAX_GROUPS)
from .iso_structures import (structure_template, structure_footprint,
                             place_structure)
from .map_authoring import _cell, _mission
from .model import Content, RuleError, Tile, require

PREFAB_KIND = 'drawtemp_editor_group_prefab'
PREFAB_VERSION = 1
MAX_PREFAB_BYTES = 2 * 1024 * 1024
MAX_PREFAB_MEMBERS = 16000
_PREFAB_FIELDS = {'kind', 'version', 'name', 'size', 'groups', 'tiles',
                  'structures', 'interior_floors', 'level_links', 'units',
                  'unit_levels', 'objects'}


def _point(point):
    require(type(point) in (tuple, list) and len(point) == 2
            and all(type(v) is int for v in point),
            'Prefab coordinates must be two integers')
    return tuple(point)


def _translate(point, dx, dy):
    x, y = _point(point)
    return [x + dx, y + dy]


def _stamp(clip, anchor):
    return set(structure_footprint(clip, anchor))


def _validate_prefab(prefab):
    """Reject malformed/unbounded files before touching the destination."""
    require(type(prefab) is dict and set(prefab) == _PREFAB_FIELDS,
            'Unknown prefab schema')
    require(prefab['kind'] == PREFAB_KIND and
            type(prefab['version']) is int and
            prefab['version'] == PREFAB_VERSION,
            'Unsupported group prefab version')
    require(type(prefab['name']) is str and
            1 <= len(prefab['name'].strip()) <= 80, 'Invalid prefab name')
    size = prefab['size']
    require(type(size) is list and len(size) == 2 and
            all(type(v) is int and 1 <= v <= 128 for v in size),
            'Prefab dimensions must be 1..128')
    for key in ('groups', 'tiles', 'structures', 'interior_floors',
                'level_links', 'units', 'objects'):
        require(type(prefab[key]) is list, 'Invalid prefab section: ' + key)
    require(type(prefab['unit_levels']) is dict,
            'Invalid prefab actor levels')
    require(1 <= len(prefab['groups']) <= MAX_GROUPS,
            'Invalid prefab group count')
    counts = sum(len(prefab[k]) for k in
                 ('groups', 'tiles', 'structures', 'interior_floors',
                  'level_links', 'units', 'objects'))
    require(counts <= MAX_PREFAB_MEMBERS, 'Prefab too large')
    ids = {key: set() for key in
           ('groups', 'structures', 'units', 'objects', 'level_links')}
    from .editor_groups import _FIELDS
    group_parent = {}
    owned = {'cells': set(), 'unit_ids': set(),
             'object_ids': set(), 'structure_ids': set()}
    for group in prefab['groups']:
        require(type(group) is dict and set(group) == _FIELDS,
                'Invalid prefab group record')
        gid = group['id']
        require(type(gid) is str and bool(re.fullmatch(
                    r'[A-Za-z][A-Za-z0-9_-]{0,63}', gid))
                and gid not in ids['groups'],
                'Invalid or duplicate prefab group id')
        ids['groups'].add(gid)
        require(group['parent'] is None or type(group['parent']) is str,
                'Invalid prefab group parent')
        group_parent[gid] = group['parent']
        require(type(group['name']) is str and
                1 <= len(group['name'].strip()) <= 80,
                'Invalid prefab group name')
        require(type(group['cells']) is list, 'Invalid prefab group cells')
        for cell in group['cells']:
            pos = _point(cell)
            require(0 <= pos[0] < size[0] and 0 <= pos[1] < size[1]
                    and pos not in owned['cells'],
                    'Overlapping prefab tiles')
            owned['cells'].add(pos)
        for key in ('unit_ids', 'object_ids', 'structure_ids'):
            require(type(group[key]) is list,
                    'Invalid prefab membership')
            for val in group[key]:
                require(type(val) is str and val not in owned[key],
                        'Duplicate prefab membership')
                owned[key].add(val)
    for gid, parent in group_parent.items():
        seen = {gid}
        while parent is not None:
            require(parent in group_parent and parent not in seen,
                    'Prefab group hierarchy contains unknown/cyclic parent')
            seen.add(parent)
            parent = group_parent[parent]
    for key in ('structures', 'units', 'objects', 'level_links'):
        for item in prefab[key]:
            require(type(item) is dict and type(item.get('id')) is str
                    and item['id'] not in ids[key],
                    'Invalid or duplicate prefab ' + key)
            ids[key].add(item['id'])
    for field, section in (('structure_ids', 'structures'),
                           ('unit_ids', 'units'), ('object_ids', 'objects')):
        require(owned[field] == ids[section],
                'Prefab has orphaned or missing group members: ' + field)
    require(set(prefab['unit_levels']) <= ids['units'],
            'Prefab levels refer to missing actors')
    require(all(type(level) is int and 1 <= level <= 3 for level in
                prefab['unit_levels'].values()),
            'Invalid prefab actor floor')
    for unit in prefab['units']:
        pos = _point(unit.get('pos'))
        require(0 <= pos[0] < size[0] and 0 <= pos[1] < size[1],
                'Prefab actor outside its bounds')
        for tag in unit.get('tags', ()):
            require(type(tag) is str, 'Invalid prefab actor tag')
            if tag.startswith('formation:escort:'):
                require(tag[len('formation:escort:'):] in ids['units'],
                        'Prefab escort refers to a missing actor')
    for obj in prefab['objects']:
        pos = _point(obj.get('pos'))
        require(0 <= pos[0] < size[0] and 0 <= pos[1] < size[1],
                'Prefab object outside its bounds')
        if obj.get('link'):
            require(type(obj['link']) is str and
                    obj['link'] in ids['objects'],
                    'Prefab object refers to missing linked member')
        if obj.get('kind') == 'passage':
            _point(obj.get('destination'))
    for deck in prefab['interior_floors']:
        require(type(deck) is dict and
                deck.get('structure_id') in ids['structures'],
                'Prefab floor refers to an unknown building')
    for edge in prefab['level_links']:
        for side in ('from', 'to'):
            end = edge.get(side)
            require(type(end) is list and len(end) == 3 and
                    all(type(n) is int for n in end) and
                    0 <= end[0] <= 3,
                    'Invalid prefab floor connector')
            _point(end[1:])
    require(not prefab['unit_levels'] or prefab['level_links'],
            'Upper-floor prefab requires its staircase')
    for item in prefab['tiles']:
        require(type(item) is dict and set(item) == {'pos', 'tile'},
                'Invalid prefab tile')
        p = _point(item['pos'])
        require(0 <= p[0] < size[0] and 0 <= p[1] < size[1],
                'Prefab terrain outside its bounds')
        require(item['tile'] is None or
                (type(item['tile']) is dict and
                 set(item['tile']) == set(asdict(Tile()))),
                'Invalid prefab terrain payload')
    require(len({_point(item['pos']) for item in prefab['tiles']}) ==
            len(prefab['tiles']), 'Duplicate prefab terrain')
    return prefab


def capture_group_prefab(data, mission_id, group_ids, name):
    """Extract selected roots with local coordinates; never writes to mission."""
    Content.from_dict(data)
    mission = _mission(data, mission_id)
    roots, selected = selected_group_closure(mission, group_ids)
    included = {'unit_ids': set(), 'object_ids': set(),
                'structure_ids': set()}
    free_cells = set()
    for group in selected:
        free_cells.update(map(tuple, group['cells']))
        for field in included:
            included[field].update(group[field])
    footprint = set()
    for gid in roots:
        footprint.update(group_display_cells(mission, gid))
    require(bool(footprint), 'Cannot export a prefab with no map members')
    x0 = min(p[0] for p in footprint)
    y0 = min(p[1] for p in footprint)
    width = max(p[0] for p in footprint) - x0 + 1
    height = max(p[1] for p in footprint) - y0 + 1
    require(type(name) is str and 1 <= len(name.strip()) <= 80,
            'Prefab needs a name')

    structs = [s for s in mission.get('structures', ())
               if s['id'] in included['structure_ids']]
    structure_cells = set()
    for s in structs:
        clip = structure_template(s['name'], s['turns'],
                                  door_slot=s['door_slot'])
        structure_cells.update(_stamp(clip, s['anchor']))
    all_cells = sorted(free_cells | structure_cells,
                       key=lambda p: (p[1], p[0]))
    original_tiles = {tuple(t['pos']): t for t in mission['board']['tiles']}
    terrain = [{'pos': _translate(pos, -x0, -y0),
                'tile': (deepcopy({k: v for k, v in original_tiles[pos].items()
                                   if k != 'pos'})
                         if pos in original_tiles else None)}
               for pos in all_cells]

    units = []
    for source in mission['units']:
        if source['id'] not in included['unit_ids']:
            continue
        clone = deepcopy(source)
        clone['pos'] = _translate(clone['pos'], -x0, -y0)
        clone['patrol_route'] = [_translate(c, -x0, -y0)
                                 for c in source.get('patrol_route', ())]
        for tag in clone.get('tags', ()):
            if tag.startswith('formation:escort:'):
                require(tag[len('formation:escort:'):] in included['unit_ids'],
                        'Select the escorted actor in the prefab too')
        units.append(clone)

    objects = []
    for source in mission['objects']:
        if source['id'] not in included['object_ids']:
            continue
        clone = deepcopy(source)
        clone['pos'] = _translate(clone['pos'], -x0, -y0)
        if clone.get('link'):
            require(clone['link'] in included['object_ids'],
                    'Include linked doors with their levers and siege engines')
        if clone['kind'] == 'defense':
            clone['cells'] = [_translate(c, -x0, -y0)
                              for c in clone['cells']]
        if clone['kind'] == 'passage':
            # Passage destination is relative in a reusable prefab.
            clone['destination'] = _translate(
                clone['destination'], -x0, -y0)
        objects.append(clone)

    decks = [deepcopy(f) for f in mission.get('interior_floors', ())
             if f['structure_id'] in included['structure_ids']]
    connectors = []
    for link in mission.get('level_links', ()):
        ends = [tuple(link[key][1:]) for key in ('from', 'to')]
        if all(pos in structure_cells for pos in ends):
            clone = deepcopy(link)
            for key in ('from', 'to'):
                clone[key] = [link[key][0], *_translate(link[key][1:],
                                                         -x0, -y0)]
            connectors.append(clone)
    levels = {uid: lvl for uid, lvl in mission.get('unit_levels', {}).items()
              if uid in included['unit_ids']}
    require(not levels or bool(connectors),
            'Upper-floor prefabs require their building and staircase')
    prefab = {
        'kind': PREFAB_KIND, 'version': PREFAB_VERSION,
        'name': name.strip(), 'size': [width, height],
        'groups': [{**deepcopy(g),
                    'parent': g['parent'] if g['parent'] in
                    {s['id'] for s in selected} else None,
                    'cells': [_translate(c, -x0, -y0) for c in g['cells']]}
                   for g in selected],
        'tiles': terrain,
        'structures': [{key: deepcopy(val) for key, val in s.items()
                        if key != 'underlay' and key != 'anchor'}
                       | {'anchor': _translate(s['anchor'], -x0, -y0)}
                       for s in structs],
        'interior_floors': decks, 'level_links': connectors,
        'units': units, 'unit_levels': levels, 'objects': objects,
    }
    return _validate_prefab(prefab)


def prefab_display_cells(prefab, anchor):
    """All occupied/local preview cells, including 1x1 and wide actors."""
    _validate_prefab(prefab)
    dx, dy = _point(anchor)
    points = {_point(item['pos']) for item in prefab['tiles']}
    for unit in prefab['units']:
        x, y = _point(unit['pos'])
        w, h = unit.get('footprint', (1, 1))
        points.update((x+ix, y+iy) for ix in range(w) for iy in range(h))
    for obj in prefab['objects']:
        points.add(_point(obj['pos']))
    return {(x+dx, y+dy) for x, y in points}


def place_group_prefab(data, mission_id, prefab, anchor):
    """Instantiate onto another mission, with validated IDs and fresh underlays."""
    _validate_prefab(prefab)
    Content.from_dict(data)
    _point(anchor)
    mission_before = _mission(data, mission_id)
    require(len(mission_before.get('editor_groups', ())) +
            len(prefab['groups']) <= MAX_GROUPS,
            'Too many groups to place prefab')
    dx, dy = anchor
    def world(cell):
        return _cell(mission_before, _translate(cell, dx, dy))

    # Validate the destination before the first write. Source terrain might be
    # sparse and a building must also respect the entire stamped footprint.
    structures = set()
    for row in mission_before.get('structures', ()):
        clip = structure_template(row['name'], row['turns'],
                                  door_slot=row['door_slot'])
        structures.update(_stamp(clip, row['anchor']))
    planned_structures = set()
    for row in prefab['structures']:
        clip = structure_template(row['name'], row['turns'],
                                  door_slot=row['door_slot'])
        cells = _stamp(clip, world(row['anchor']))
        require(not cells.intersection(structures | planned_structures),
                'Prefab collides with a building')
        planned_structures.update(cells)
    tiles = {tuple(row['pos']): row for row in mission_before['board']['tiles']}
    from .model import Tile
    default = asdict(Tile())
    local_tiles = set()
    for item in prefab['tiles']:
        point = tuple(world(item['pos']))
        require(point not in structures, 'Prefab terrain overlaps a building')
        local_tiles.add(point)
    for point in local_tiles | planned_structures:
        existing = tiles.get(point)
        require(existing is None or
                {k: v for k, v in existing.items() if k != 'pos'} == default,
                'Prefab would overwrite existing terrain at ' + str(point))
    blocked = {tuple(p) for zone in mission_before.get('deployment', ())
               for p in zone.get('cells', ())}
    blocked.update(tuple(p) for p in mission_before.get('goal', ()))
    if mission_before.get('relic') is not None:
        blocked.add(tuple(mission_before['relic']))
    require(not (local_tiles | planned_structures).intersection(blocked),
            'Prefab overlaps a mission objective or deployment zone')
    occupied_actors = set()
    for actor in mission_before['units']:
        x, y = _point(actor['pos'])
        w, h = actor.get('footprint', (1, 1))
        floor = mission_before.get('unit_levels', {}).get(actor['id'], 0)
        occupied_actors.update((floor, x+ix, y+iy)
                               for ix in range(w) for iy in range(h))
    copied_actors = set()
    for unit in prefab['units']:
        x, y = world(unit['pos'])
        w, h = unit.get('footprint', (1, 1))
        floor = prefab['unit_levels'].get(unit['id'], 0)
        footprint = {(floor, x+ix, y+iy)
                     for ix in range(w) for iy in range(h)}
        require(not footprint.intersection(occupied_actors | copied_actors),
                'Prefab actor overlaps another actor on the same floor')
        for _, tx, ty in footprint:
            _cell(mission_before, (tx, ty))
        copied_actors.update(footprint)
        for pos in unit.get('patrol_route', ()):
            world(pos)
    occupied_objects = {tuple(item['pos']) for item in
                        mission_before['objects']}
    new_objects = set()
    for obj in prefab['objects']:
        point = tuple(world(obj['pos']))
        require(point not in occupied_objects and point not in new_objects,
                'Prefab object overlaps another interactive object')
        new_objects.add(point)
        if obj['kind'] == 'passage':
            world(obj['destination'])
        if obj['kind'] == 'defense':
            for point in obj['cells']:
                world(point)
    for row in prefab['level_links']:
        for key in ('from', 'to'):
            world(row[key][1:])

    result = deepcopy(data)
    mission = _mission(result, mission_id)
    new_structures = {}
    for row in prefab['structures']:
        result = place_structure(
            result, mission_id, row['name'], world(row['anchor']),
            row['turns'], door_slot=row['door_slot'])
        mission = _mission(result, mission_id)
        new_structures[row['id']] = mission['structures'][-1]['id']
    for floor in prefab['interior_floors']:
        require(floor['structure_id'] in new_structures,
                'Prefab floor references an absent structure')
        clone = deepcopy(floor)
        clone['structure_id'] = new_structures[floor['structure_id']]
        mission.setdefault('interior_floors', []).append(clone)
    written = {tuple(t['pos']): t for t in mission['board']['tiles']}
    for tile in prefab['tiles']:
        pos = tuple(world(tile['pos']))
        if tile['tile'] is None:
            require(pos not in planned_structures,
                    'A structure prefab cannot erase its own stamped ground')
            written.pop(pos, None)
        else:
            written[pos] = {'pos': list(pos), **deepcopy(tile['tile'])}
    mission['board']['tiles'] = list(written.values())

    actor_names = {u['id'] for u in mission['units']}
    object_names = {o['id'] for o in mission['objects']}
    group_names = {g['id'] for g in mission.get('editor_groups', ())}
    link_names = {s['id'] for s in mission.get('level_links', ())}
    actor_map = {u['id']: _copy_identifier(u['id'], actor_names, 'unit')
                 for u in prefab['units']}
    object_map = {o['id']: _copy_identifier(o['id'], object_names, 'obj')
                  for o in prefab['objects']}
    group_map = {g['id']: _copy_identifier(g['id'], group_names, 'group')
                 for g in prefab['groups']}
    for unit in prefab['units']:
        clone = deepcopy(unit)
        clone['id'] = actor_map[unit['id']]
        clone['pos'] = world(unit['pos'])
        clone['patrol_route'] = [world(p) for p in
                                 unit.get('patrol_route', ())]
        clone['tags'] = [
            'formation:escort:' + actor_map[
                tag[len('formation:escort:'):]]
            if tag.startswith('formation:escort:') else tag
            for tag in clone.get('tags', ())
        ]
        mission['units'].append(clone)
    for old, level in prefab['unit_levels'].items():
        mission.setdefault('unit_levels', {})[actor_map[old]] = level
    for obj in prefab['objects']:
        clone = deepcopy(obj)
        clone['id'] = object_map[obj['id']]
        clone['pos'] = world(obj['pos'])
        if clone.get('link'):
            require(clone['link'] in object_map, 'Prefab needs its linked door')
            clone['link'] = object_map[clone['link']]
        if clone['kind'] == 'defense':
            clone['cells'] = [world(c) for c in clone['cells']]
        if clone['kind'] == 'passage':
            clone['destination'] = world(clone['destination'])
        mission['objects'].append(clone)
    for edge in prefab['level_links']:
        clone = deepcopy(edge)
        clone['id'] = _copy_identifier(edge['id'], link_names, 'stair')
        for key in ('from', 'to'):
            clone[key] = [edge[key][0], *world(edge[key][1:])]
        mission.setdefault('level_links', []).append(clone)
    for group in prefab['groups']:
        clone = deepcopy(group)
        clone['id'] = group_map[group['id']]
        clone['parent'] = (group_map[group['parent']]
                           if group['parent'] is not None else None)
        clone['cells'] = [world(c) for c in group['cells']]
        clone['unit_ids'] = [actor_map[r] for r in group['unit_ids']]
        clone['object_ids'] = [object_map[r] for r in group['object_ids']]
        clone['structure_ids'] = [new_structures[r] for r in
                                  group['structure_ids']]
        mission.setdefault('editor_groups', []).append(clone)
    return _validate_document(result)


def save_group_prefab(prefab, path, *, overwrite=False):
    """Atomically write a bounded JSON prefab, refusing implicit overwrite."""
    _validate_prefab(prefab)
    raw = json.dumps(prefab, indent=2, ensure_ascii=False, sort_keys=True)
    require(len(raw.encode('utf-8')) <= MAX_PREFAB_BYTES,
            'Prefab JSON exceeds the size limit')
    path = Path(path)
    require(path.suffix.lower() == '.json', 'Prefab filename needs .json')
    require(not path.exists() or overwrite, 'Prefab already exists')
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = None
    try:
        with NamedTemporaryFile('w', encoding='utf-8', dir=str(path.parent),
                                suffix='.tmp', delete=False) as temp:
            candidate = Path(temp.name)
            temp.write(raw + '\n')
        os.replace(candidate, path)
    finally:
        if candidate is not None:
            candidate.unlink(missing_ok=True)
    return path


def load_group_prefab(path):
    path = Path(path)
    require(path.is_file() and path.stat().st_size <= MAX_PREFAB_BYTES,
            'Prefab is absent or too large')
    try:
        return _validate_prefab(json.loads(path.read_text(encoding='utf-8')))
    except (ValueError, UnicodeError, TypeError) as exc:
        raise RuleError('Invalid group prefab JSON: ' + str(exc)) from exc


def list_group_prefabs(folder):
    """Local library; content is validated on selection, not on enumeration."""
    folder = Path(folder)
    if not folder.is_dir():
        return ()
    return tuple(sorted(
        (p for p in folder.glob('*.json') if p.is_file()),
        key=lambda p: p.name.casefold()))


def prefab_file_slug(name):
    require(type(name) is str and bool(name.strip()), 'Name the prefab')
    slug = re.sub(r'[^a-zA-Z0-9_-]+', '_', name.strip()).strip('_')
    require(bool(slug), 'Use letters or digits for a prefab filename')
    return slug[:64] + '.json'

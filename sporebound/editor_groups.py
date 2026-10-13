"""Hierarchical, persistent *editor-only* groups for map cells and objects.

Groups are mission metadata, not gameplay entities. A group owns its direct
members; a parent also moves every descendant. No tile or entity can be owned
by two groups. Existing structure, entity and terrain authoring remain the
single source of truth.
"""
from copy import deepcopy

from .model import Content, RuleError, require
from .map_authoring import _mission, _cell, selected_cells
from .iso_structures import structure_footprint, structure_template

MAX_GROUPS = 512
_FIELDS = {'id', 'name', 'parent', 'cells', 'unit_ids', 'object_ids', 'structure_ids'}
_MEMBER_FIELDS = ('unit_ids', 'object_ids', 'structure_ids')


def validate_editor_groups(mission):
    """Validate references, ownership, coordinates, parent cycles and schema."""
    groups = mission.editor_groups
    require(type(groups) is list and len(groups) <= MAX_GROUPS,
            'Invalid editor groups')
    ids = set()
    used = {'cells': set(), **{field: set() for field in _MEMBER_FIELDS}}
    structure_ids = {item['id'] for item in mission.structures}
    structure_tiles = set()
    for item in mission.structures:
        clip = structure_template(item['name'], item['turns'],
                                  door_slot=item['door_slot'])
        structure_tiles.update(structure_footprint(clip, item['anchor']))
    valid_refs = {
        'unit_ids': {u.id for u in mission.units},
        'object_ids': {o['id'] for o in mission.objects},
        'structure_ids': structure_ids,
    }
    for group in groups:
        require(type(group) is dict and set(group) == _FIELDS,
                'Invalid editor group fields')
        gid, name = group['id'], group['name']
        require(type(gid) is str and 1 <= len(gid) <= 64 and gid.isascii()
                and gid[0].isalpha()
                and all(c.isalnum() or c in '_-' for c in gid)
                and gid not in ids, 'Invalid or duplicate editor group id')
        require(type(name) is str and 1 <= len(name.strip()) <= 80,
                'Editor group requires a name')
        require(group['parent'] is None or type(group['parent']) is str,
                'Invalid group parent')
        ids.add(gid)
        cells = group['cells']
        require(type(cells) is list, 'Invalid group cells')
        local = set()
        for point in cells:
            require(type(point) is list and len(point) == 2 and
                    all(type(n) is int for n in point),
                    'Invalid group cell')
            cell = tuple(point)
            require(mission.board.contains(cell) and cell not in structure_tiles
                    and cell not in local and cell not in used['cells'],
                    'Group cell overlaps another group or an authored structure')
            local.add(cell)
        used['cells'].update(local)
        for field in _MEMBER_FIELDS:
            refs = group[field]
            require(type(refs) is list and
                    all(type(ref) is str for ref in refs) and
                    len(refs) == len(set(refs)) and
                    set(refs) <= valid_refs[field] and
                    not set(refs).intersection(used[field]),
                    'Invalid or duplicate group members: ' + field)
            used[field].update(refs)
    parents = {item['id']: item['parent'] for item in groups}
    for gid, parent in parents.items():
        require(parent is None or parent in parents, 'Unknown group parent')
        seen = {gid}
        while parent is not None:
            require(parent not in seen, 'Cycle in editor group hierarchy')
            seen.add(parent)
            parent = parents[parent]


def _groups(data, mission_id):
    return _mission(data, mission_id).setdefault('editor_groups', [])


def _group(groups, group_id):
    result = next((row for row in groups if row['id'] == group_id), None)
    require(result is not None, 'Unknown editor group: ' + str(group_id))
    return result


def _validate_document(data):
    from .tactical_rpg3 import authored_rules_for_document
    return Content.from_dict(data, rules=authored_rules_for_document(data)).to_dict()


def group_selection(data, mission_id, cells):
    """Collect selectable pieces; a complete persistent building is one piece.

    The actual stamped tiles beneath structures are deliberately not stored as
    free-standing tile members, avoiding a second owner of the same terrain.
    """
    mission = _mission(data, mission_id)
    selected = set(selected_cells(data, mission_id, cells))
    covered = set()
    structure_ids = []
    for item in mission.get('structures', ()):
        clip = structure_template(item['name'], item['turns'],
                                  door_slot=item['door_slot'])
        footprint = set(structure_footprint(clip, item['anchor']))
        covered.update(footprint)
        if footprint <= selected:
            structure_ids.append(item['id'])
    free_cells = sorted(selected - covered, key=lambda c: (c[1], c[0]))
    unit_ids = []
    for unit in mission['units']:
        x, y = unit['pos']
        width, height = unit.get('footprint', (1, 1))
        footprint = {(x+dx, y+dy) for dx in range(width)
                     for dy in range(height)}
        if selected & footprint:
            unit_ids.append(unit['id'])
    object_ids = [o['id'] for o in mission['objects']
                  if tuple(o['pos']) in selected]
    return {
        'cells': [list(c) for c in free_cells],
        'unit_ids': unit_ids,
        'object_ids': object_ids,
        'structure_ids': structure_ids,
    }


def create_editor_group(data, mission_id, name, *, parent=None, cells=()):
    """Create an empty or selection-backed group in one undoable document edit."""
    updated = deepcopy(data)
    groups = _groups(updated, mission_id)
    require(len(groups) < MAX_GROUPS, 'Maximum editor group count reached')
    if parent is not None:
        _group(groups, parent)
    existing = {g['id'] for g in groups}
    index = 1
    while 'group_' + str(index) in existing:
        index += 1
    members = group_selection(updated, mission_id, cells) if cells else {
        'cells': [], 'unit_ids': [], 'object_ids': [], 'structure_ids': []}
    groups.append({'id': 'group_' + str(index), 'name': name,
                   'parent': parent, **members})
    return _validate_document(updated)


def add_selection_to_group(data, mission_id, group_id, cells):
    updated = deepcopy(data)
    group = _group(_groups(updated, mission_id), group_id)
    selected = group_selection(updated, mission_id, cells)
    for field, values in selected.items():
        if field == 'cells':
            existing = {tuple(c) for c in group[field]}
            group[field].extend(c for c in values if tuple(c) not in existing)
        else:
            group[field].extend(value for value in values
                                if value not in group[field])
    return _validate_document(updated)


def rename_editor_group(data, mission_id, group_id, name):
    updated = deepcopy(data)
    _group(_groups(updated, mission_id), group_id)['name'] = name
    return _validate_document(updated)


def reparent_editor_group(data, mission_id, group_id, parent):
    updated = deepcopy(data)
    groups = _groups(updated, mission_id)
    if parent is not None:
        _group(groups, parent)
    _group(groups, group_id)['parent'] = parent
    return _validate_document(updated)


def delete_editor_group(data, mission_id, group_id):
    """Ungroup without deleting a tile, actor, structure or child group."""
    updated = deepcopy(data)
    groups = _groups(updated, mission_id)
    group = _group(groups, group_id)
    groups.remove(group)
    for child in groups:
        if child['parent'] == group_id:
            child['parent'] = group['parent']
    return _validate_document(updated)


def descendant_groups(mission, group_id):
    """Return the chosen group and all children (stable order)."""
    groups = mission.get('editor_groups', [])
    _group(groups, group_id)
    included = {group_id}
    while True:
        children = {g['id'] for g in groups if g['parent'] in included}
        if children <= included:
            break
        included.update(children)
    return tuple(g for g in groups if g['id'] in included)


def group_display_cells(mission, group_id):
    """Every group member represented on the map, for Treeview selection."""
    result = set()
    for group in descendant_groups(mission, group_id):
        result.update(tuple(c) for c in group['cells'])
        for item in mission['units']:
            if item['id'] in group['unit_ids']:
                x, y = item['pos']
                w, h = item.get('footprint', (1, 1))
                result.update((x+dx, y+dy) for dx in range(w)
                              for dy in range(h))
        for item in mission['objects']:
            if item['id'] in group['object_ids']:
                result.add(tuple(item['pos']))
        for item in mission.get('structures', ()):
            if item['id'] in group['structure_ids']:
                clip = structure_template(item['name'], item['turns'],
                                          door_slot=item['door_slot'])
                result.update(structure_footprint(clip, item['anchor']))
    return result


def move_editor_group(data, mission_id, group_id, dx, dy):
    """Translate a complete hierarchy with one Content validation/undo entry.

    Move the canonical structures and entities through their existing
    authoring APIs. Decor/terrain cells move as a sparse patch: external
    non-default tiles and structural footprints are never overwritten silently.
    """
    require(type(dx) is int and type(dy) is int and (dx or dy),
            'Group movement needs a nonzero integer offset')
    original = _mission(data, mission_id)
    groups = descendant_groups(original, group_id)
    members = {key: set() for key in ('unit_ids', 'object_ids', 'structure_ids')}
    cells = set()
    for group in groups:
        cells.update(tuple(c) for c in group['cells'])
        for field in members:
            members[field].update(group[field])
    require(bool(cells or any(members.values())),
            'Cannot move an empty group')
    board = original['board']
    width, height = board['width'], board['height']
    targets = {(x+dx, y+dy) for x, y in cells}
    for pos in targets:
        _cell(original, pos)
    original_tiles = {tuple(t['pos']): deepcopy(t) for t in board['tiles']}
    from .model import Tile
    from dataclasses import asdict
    default = asdict(Tile())
    for pos in targets - cells:
        existing = original_tiles.get(pos)
        require(existing is None or
                {k: v for k, v in existing.items() if k != 'pos'} == default,
                'Group movement would overwrite external terrain at ' + str(pos))
    moving_structure_cells = set()
    fixed_structure_cells = set()
    for item in original.get('structures', []):
        clip = structure_template(item['name'], item['turns'],
                                  door_slot=item['door_slot'])
        footprint = set(structure_footprint(clip, item['anchor']))
        if item['id'] in members['structure_ids']:
            moving_structure_cells.update(footprint)
        else:
            fixed_structure_cells.update(footprint)
    moved_structure_cells = {(x+dx, y+dy) for x, y in moving_structure_cells}
    require(not targets.intersection(moving_structure_cells | fixed_structure_cells |
                                     moved_structure_cells),
            'Grouped terrain overlaps a building footprint')
    require(not moved_structure_cells.intersection(cells),
            'A moved building overlaps grouped terrain')
    result = deepcopy(data)
    if moving_structure_cells:
        from .structure_groups import transform_structure_group
        # The existing structure transaction validates intermediate states while
        # the old records are detached. Suspend editor-only group references
        # during that transaction, then restore them before final validation.
        held_groups = _mission(result, mission_id).pop('editor_groups', [])
        result = transform_structure_group(result, mission_id,
                                           tuple(moving_structure_cells), dx, dy)
        _mission(result, mission_id)['editor_groups'] = held_groups
    if members['unit_ids'] or members['object_ids']:
        from .map_transform import move_group
        result = move_group(result, mission_id,
                            tuple(sorted(members['unit_ids'])),
                            tuple(sorted(members['object_ids'])),
                            dx=dx, dy=dy)
    mission = _mission(result, mission_id)
    if cells:
        current = {tuple(t['pos']): t for t in mission['board']['tiles']}
        for cell in cells:
            current.pop(cell, None)
        for (x, y) in cells:
            tile = original_tiles.get((x, y))
            if tile is not None:
                tile['pos'] = [x+dx, y+dy]
                current[(x+dx, y+dy)] = tile
        mission['board']['tiles'] = list(current.values())
    changed_ids = {g['id'] for g in groups}
    for group in mission['editor_groups']:
        if group['id'] in changed_ids:
            group['cells'] = [[x+dx, y+dy] for x, y in group['cells']]
    return _validate_document(result)

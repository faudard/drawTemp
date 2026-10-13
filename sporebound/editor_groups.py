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



def remove_selection_from_group(data, mission_id, group_id, cells):
    """Unlink selected items without deleting the underlying map content."""
    updated = deepcopy(data)
    group = _group(_groups(updated, mission_id), group_id)
    selected = group_selection(updated, mission_id, cells)
    for field, values in selected.items():
        discard = {tuple(c) for c in values} if field == 'cells' else set(values)
        group[field] = [value for value in group[field]
                        if (tuple(value) if field == 'cells' else value)
                        not in discard]
    return _validate_document(updated)


def transfer_selection_to_group(data, mission_id, group_id, cells):
    """Move direct ownership to the chosen group (one transaction)."""
    updated = deepcopy(data)
    groups = _groups(updated, mission_id)
    target = _group(groups, group_id)
    selected = group_selection(updated, mission_id, cells)
    for group in groups:
        if group is target:
            continue
        for field, values in selected.items():
            discard = ({tuple(c) for c in values} if field == 'cells'
                       else set(values))
            group[field] = [value for value in group[field]
                            if (tuple(value) if field == 'cells' else value)
                            not in discard]
    for field, values in selected.items():
        present = ({tuple(c) for c in target[field]} if field == 'cells'
                   else set(target[field]))
        target[field].extend(value for value in values
                             if (tuple(value) if field == 'cells' else value)
                             not in present)
    return _validate_document(updated)



def check_tree_drop(mission, source_group_id, item_kind, *,
                    member=None, target_group_id=None):
    """Cheap drag-hover validation; never mutate a mission or an editor view.

    Group changes parentage; cells transfers a batch of free tiles;
    cell transfers one free tile; the *_ids kinds transfer one entity.
    A None target means root: group -> unparent, member -> unlink.
    """
    groups = mission.get('editor_groups', [])
    source = _group(groups, source_group_id)
    require(item_kind in ('group', 'cells', 'cell', *_MEMBER_FIELDS),
            'Unsupported group tree item')
    if target_group_id is not None:
        _group(groups, target_group_id)
    if item_kind == 'group':
        require(target_group_id != source_group_id, 'Cannot parent a group to itself')
        require(source['parent'] != target_group_id,
                'Group already has that parent')
        parent_ids = {group['id'] for group in descendant_groups(
            mission, source_group_id)}
        require(target_group_id not in parent_ids,
                'Cannot move a group into one of its descendants')
    else:
        require(target_group_id != source_group_id,
                'Item already belongs to that group')
        if item_kind == 'cells':
            require(bool(source['cells']), 'The group has no free cells')
        elif item_kind == 'cell':
            require(isinstance(member, (list, tuple)) and len(member) == 2
                    and all(type(n) is int for n in member)
                    and list(member) in source['cells'],
                    'Cell does not belong to source group')
        else:
            require(type(member) is str and member in source[item_kind],
                    'Entity does not belong to source group')
    return True


def drop_group_tree_item(data, mission_id, source_group_id, item_kind, *,
                         member=None, target_group_id=None):
    """One validated ownership edit; never moves game entities or tiles.

    Dragging a group keeps its descendants and their references intact.
    Dragging an entity or a tile transfers membership, not map position.
    """
    current = _mission(data, mission_id)
    check_tree_drop(current, source_group_id, item_kind, member=member,
                    target_group_id=target_group_id)
    updated = deepcopy(data)
    groups = _groups(updated, mission_id)
    source = _group(groups, source_group_id)
    if item_kind == 'group':
        source['parent'] = target_group_id
    elif item_kind == 'cells':
        payload = source['cells']
        source['cells'] = []
        if target_group_id is not None:
            _group(groups, target_group_id)['cells'].extend(payload)
    elif item_kind == 'cell':
        payload = list(member)
        source['cells'].remove(payload)
        if target_group_id is not None:
            _group(groups, target_group_id)['cells'].append(payload)
    else:
        source[item_kind].remove(member)
        if target_group_id is not None:
            _group(groups, target_group_id)[item_kind].append(member)
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


def selected_group_roots(mission, group_ids):
    """Canonicalize multi-selection: an included ancestor absorbs descendants."""
    require(isinstance(group_ids, (tuple, list)) and bool(group_ids)
            and all(type(gid) is str for gid in group_ids),
            'Select at least one editor group')
    require(len(group_ids) == len(set(group_ids)),
            'Duplicate editor group in selection')
    groups = mission.get('editor_groups', [])
    for gid in group_ids:
        _group(groups, gid)
    included = set(group_ids)
    parents = {g['id']: g['parent'] for g in groups}
    result = []
    for gid in group_ids:
        ancestor = parents[gid]
        while ancestor is not None and ancestor not in included:
            ancestor = parents[ancestor]
        if ancestor is None:
            result.append(gid)
    return tuple(result)


def selected_group_closure(mission, group_ids):
    roots = selected_group_roots(mission, group_ids)
    wanted = set()
    for gid in roots:
        wanted.update(g['id'] for g in descendant_groups(mission, gid))
    return roots, tuple(g for g in mission.get('editor_groups', ())
                        if g['id'] in wanted)


def move_editor_group(data, mission_id, group_id, dx, dy):
    """Backward-compatible one-group entry point."""
    return move_editor_groups(data, mission_id, (group_id,), dx, dy)


def move_editor_groups(data, mission_id, group_ids, dx, dy):
    """Translate a complete hierarchy with one Content validation/undo entry.

    Move the canonical structures and entities through their existing
    authoring APIs. Decor/terrain cells move as a sparse patch: external
    non-default tiles and structural footprints are never overwritten silently.
    """
    require(type(dx) is int and type(dy) is int and (dx or dy),
            'Group movement needs a nonzero integer offset')
    original = _mission(data, mission_id)
    _, groups = selected_group_closure(original, group_ids)
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
    staged = _mission(result, mission_id)
    # Groups and selected free tiles are suspended for the WHOLE operation.
    # Otherwise moving a building onto a just-vacated adjacent group tile
    # would corrupt the new stamp or falsely invalidate an intermediate state.
    held_groups = staged.pop('editor_groups', [])
    if cells:
        staged['board']['tiles'] = [
            tile for tile in staged['board']['tiles']
            if tuple(tile['pos']) not in cells]
    if moving_structure_cells:
        from .structure_groups import transform_structure_group
        result = transform_structure_group(result, mission_id,
                                           tuple(moving_structure_cells), dx, dy)
    if members['unit_ids'] or members['object_ids']:
        from .map_transform import move_group
        result = move_group(result, mission_id,
                            tuple(sorted(members['unit_ids'])),
                            tuple(sorted(members['object_ids'])),
                            dx=dx, dy=dy)
    mission = _mission(result, mission_id)
    if cells:
        current = {tuple(t['pos']): t for t in mission['board']['tiles']}
        for (x, y) in cells:
            tile = original_tiles.get((x, y))
            if tile is not None:
                copied = deepcopy(tile)
                copied['pos'] = [x+dx, y+dy]
                current[(x+dx, y+dy)] = copied
        mission['board']['tiles'] = list(current.values())
    mission['editor_groups'] = held_groups
    changed_ids = {g['id'] for g in groups}
    for group in mission['editor_groups']:
        if group['id'] in changed_ids:
            group['cells'] = [[x+dx, y+dy] for x, y in group['cells']]
    return _validate_document(result)


def _copy_identifier(original, taken, prefix):
    """Stable, legal Content ID; deterministic even after repeated duplicates."""
    import re
    root = re.sub(r'[^A-Za-z0-9_-]', '_', str(original))
    if not root or not root[0].isalpha():
        root = prefix + '_' + root
    root = root[:48] + '_copy'
    number = 1
    while True:
        suffix = '' if number == 1 else '_' + str(number)
        name = root[:64-len(suffix)] + suffix
        if name not in taken:
            taken.add(name)
            return name
        number += 1


def duplicate_editor_groups(data, mission_id, group_ids, dx, dy):
    """Copy a subtree/forest as regular authoring data in one validated edit.

    Terrain tiles, authored structures with independent underlays, interior
    decks, entities and *internal* ID links are cloned. The copied hierarchy
    receives new IDs. Mission events, objectives and externally anchored
    passage destinations intentionally remain unchanged.
    """
    require(type(dx) is int and type(dy) is int and (dx or dy),
            'Duplicating groups requires a nonzero integer offset')
    original = _mission(data, mission_id)
    roots, selected = selected_group_closure(original, group_ids)
    require(len(original.get('editor_groups', ())) + len(selected) <= MAX_GROUPS,
            'Too many groups after duplication')
    members = {key: set() for key in _MEMBER_FIELDS}
    free_cells = set()
    for group in selected:
        free_cells.update(tuple(cell) for cell in group['cells'])
        for field in members:
            members[field].update(group[field])
    require(bool(free_cells or any(members.values())),
            'Select at least one non-empty group to duplicate')

    width = original['board']['width']
    height = original['board']['height']
    def shift(cell):
        return _cell(original, (cell[0] + dx, cell[1] + dy))

    old_tiles = {tuple(t['pos']): t for t in original['board']['tiles']}
    old_structures = {s['id']: s for s in original.get('structures', ())}
    from dataclasses import asdict
    from .model import Tile
    default = asdict(Tile())
    existing_structures = set()
    for s in old_structures.values():
        clip = structure_template(s['name'], s['turns'],
                                  door_slot=s['door_slot'])
        existing_structures.update(structure_footprint(clip, s['anchor']))
    new_structure_cells = set()
    for sid in members['structure_ids']:
        structure = old_structures[sid]
        clip = structure_template(structure['name'], structure['turns'],
                                  door_slot=structure['door_slot'])
        cells = {shift(cell) for cell in
                 structure_footprint(clip, structure['anchor'])}
        require(not cells.intersection(existing_structures |
                                       new_structure_cells),
                'Copied structures overlap an existing building')
        new_structure_cells.update(cells)
    new_free_cells = {shift(cell) for cell in free_cells}
    require(not new_free_cells.intersection(existing_structures |
                                            new_structure_cells),
            'Copied terrain overlaps an authored building')
    # A copy never consumes another author's map tile, even when the
    # destination partly overlaps source cells.
    for cell in new_free_cells | new_structure_cells:
        raw = old_tiles.get(cell)
        require(raw is None or
                {k: v for k, v in raw.items() if k != 'pos'} == default,
                'Copied group would overwrite terrain at ' + str(cell))
    # Guard objectives and mission-specific anchors before stamping terrain.
    blocked_references = {tuple(c) for c in original.get('goal', ())}
    if original.get('relic') is not None:
        blocked_references.add(tuple(original['relic']))
    blocked_references.update(
        tuple(c) for zone in original.get('deployment', ())
        for c in zone.get('cells', ()))
    require(not (new_free_cells | new_structure_cells).intersection(
                blocked_references), 'Copied group intersects a mission anchor')

    updated = deepcopy(data)
    mission = _mission(updated, mission_id)
    # Structural authoring owns underlay captures and actual bridge/wall tiles.
    # All destination footprints are prechecked before the first placement.
    structure_map = {}
    from .iso_structures import place_structure
    for structure in original.get('structures', ()):
        if structure['id'] not in members['structure_ids']:
            continue
        copied = place_structure(
            updated, mission_id, structure['name'], shift(structure['anchor']),
            structure['turns'], door_slot=structure['door_slot'])
        updated = copied
        mission = _mission(updated, mission_id)
        structure_map[structure['id']] = mission['structures'][-1]['id']

    # These are local-to-structure coordinates, so only remap identity.
    for floor in original.get('interior_floors', ()):
        if floor['structure_id'] in structure_map:
            clone = deepcopy(floor)
            clone['structure_id'] = structure_map[floor['structure_id']]
            mission.setdefault('interior_floors', []).append(clone)

    tiles = {tuple(t['pos']): deepcopy(t) for t in mission['board']['tiles']}
    # A structure may have been repainted after placement. Preserve those
    # authored per-tile edits instead of reverting its new copy to the preset.
    # Its fresh underlay remains the destination's pre-placement terrain.
    for sid in members['structure_ids']:
        structure = old_structures[sid]
        clip = structure_template(structure['name'], structure['turns'],
                                  door_slot=structure['door_slot'])
        for point in structure_footprint(clip, structure['anchor']):
            target = shift(point)
            original_tile = old_tiles.get(point)
            if original_tile is None:
                tiles.pop(target, None)
            else:
                copied_tile = deepcopy(original_tile)
                copied_tile['pos'] = list(target)
                tiles[target] = copied_tile
    for cell in sorted(free_cells, key=lambda p: (p[1], p[0])):
        target = shift(cell)
        original_tile = old_tiles.get(cell)
        if original_tile is None:
            tiles.pop(target, None)
        else:
            copied_tile = deepcopy(original_tile)
            copied_tile['pos'] = list(target)
            tiles[target] = copied_tile
    mission['board']['tiles'] = list(tiles.values())

    unit_names = {u['id'] for u in mission['units']}
    object_names = {o['id'] for o in mission['objects']}
    unit_map = {}
    object_map = {}
    for u in original['units']:
        if u['id'] in members['unit_ids']:
            unit_map[u['id']] = _copy_identifier(u['id'], unit_names, 'unit')
    for obj in original['objects']:
        if obj['id'] in members['object_ids']:
            object_map[obj['id']] = _copy_identifier(obj['id'], object_names,
                                                     'object')
    for source in original['units']:
        if source['id'] not in unit_map:
            continue
        clone = deepcopy(source)
        clone['id'] = unit_map[source['id']]
        clone['pos'] = list(shift(source['pos']))
        clone['patrol_route'] = [list(shift(p)) for p in
                                 source.get('patrol_route', ())]
        tags = []
        for tag in clone.get('tags', ()):
            if type(tag) is str and tag.startswith('formation:escort:'):
                uid = tag[len('formation:escort:'):]
                tag = 'formation:escort:' + unit_map.get(uid, uid)
            tags.append(tag)
        clone['tags'] = tags
        mission['units'].append(clone)
        if source['id'] in original.get('unit_levels', {}):
            require(bool(structure_map),
                    'Copy the associated building for an upper-floor actor')
            mission.setdefault('unit_levels', {})[clone['id']] = (
                original['unit_levels'][source['id']])

    for source in original['objects']:
        if source['id'] not in object_map:
            continue
        clone = deepcopy(source)
        clone['id'] = object_map[source['id']]
        clone['pos'] = list(shift(source['pos']))
        if 'link' in clone:
            clone['link'] = object_map.get(clone['link'], clone['link'])
        if clone['kind'] == 'defense':
            clone['cells'] = [list(shift(c)) for c in clone['cells']]
        # Passage destination is an intentional absolute point, not a relative
        # offset; retain it just like the existing map group authoring.
        mission['objects'].append(clone)

    # Copy only connectors whose endpoints both belong to selected buildings.
    # Cross-boundary links remain external and are never silently rewritten.
    link_names = {link['id'] for link in mission.get('level_links', ())}
    source_structure_cells = set()
    for sid in members['structure_ids']:
        item = old_structures[sid]
        clip = structure_template(item['name'], item['turns'],
                                  door_slot=item['door_slot'])
        source_structure_cells.update(structure_footprint(
            clip, item['anchor']))
    copied_connector_count = 0
    for edge in original.get('level_links', ()):
        a, b = edge['from'], edge['to']
        if (tuple(a[1:]) in source_structure_cells and
                tuple(b[1:]) in source_structure_cells and
                (a[0] > 0 or b[0] > 0)):
            clone = deepcopy(edge)
            clone['id'] = _copy_identifier(edge['id'], link_names, 'link')
            clone['from'] = [a[0], *shift(a[1:])]
            clone['to'] = [b[0], *shift(b[1:])]
            mission.setdefault('level_links', []).append(clone)
            copied_connector_count += 1
    if any(uid in original.get('unit_levels', {}) for uid in unit_map):
        require(copied_connector_count > 0,
                'Cannot duplicate upper-floor actors without their connectors')

    group_names = {g['id'] for g in original.get('editor_groups', ())}
    group_map = {}
    for group in selected:
        group_map[group['id']] = _copy_identifier(group['id'], group_names,
                                                   'group')
    for group in selected:
        clone = deepcopy(group)
        clone['id'] = group_map[group['id']]
        clone['name'] = group['name'][:72] + ' (copie)'
        clone['parent'] = group_map.get(group['parent'], group['parent'])
        clone['cells'] = [list(shift(cell)) for cell in group['cells']]
        clone['unit_ids'] = [unit_map[uid] for uid in group['unit_ids']]
        clone['object_ids'] = [object_map[oid] for oid in group['object_ids']]
        clone['structure_ids'] = [structure_map[sid] for sid in
                                  group['structure_ids']]
        mission.setdefault('editor_groups', []).append(clone)
    return _validate_document(updated)

"""Headless structure presets and optional authoring-only identities.

Tactical terrain remains the source of truth. New placements remember their
visual identity, whereas old maps without records are still recognised.
"""
from copy import deepcopy

from .map_authoring import _cell, _mission, paste_terrain, TerrainClipboard
from .map_transform import _validate_clipboard, transform_terrain
from .model import Content, RuleError, require


# Fixed, inspectable terrain plans; coordinates are relative to the top-left
# anchor. A period is floor; W=wall; D=entrance; R=ruin; B=bridge.
# 0..3 is a walkable stair at the specified elevation.
_STRUCTURE_PLANS = {
    'Maison': ('WWWW', 'W..W', 'WD.W'),
    'Tour': ('WWW', 'W2W', 'WDW'),
    'Rempart': ('WWWWW',),
    'Escalier': ('00', '11', '22', '33'),
    'Pont': ('BBB', 'BBB'),
    'Ruines': ('W.WW', 'R..R', 'W.DW'),
}
STRUCTURE_NAMES = tuple(_STRUCTURE_PLANS)
# The alternative door uses an existing walkable floor cell; nothing new
# enters Content, navigation or the serialized tile schema.
STRUCTURE_DOOR_SLOTS = {
    'Maison': ((1, 2), (2, 2)),
    'Ruines': ((2, 2), (1, 2)),
}


def door_slots(name):
    return STRUCTURE_DOOR_SLOTS.get(name, ((0, 0),))




def _tile_for_token(token):
    if token == 'W':
        return {'surface': 'stone', 'feature': 'stone_wall',
                'blocked': True, 'height': 2}
    if token == 'D':
        return {'surface': 'cobble', 'blocked': False, 'feature': ''}
    if token == '.':
        return {'surface': 'stone', 'blocked': False, 'feature': ''}
    if token == 'R':
        return {'surface': 'stone', 'blocked': False, 'feature': 'ruin'}
    if token == 'B':
        return {'surface': 'bridge', 'blocked': False, 'feature': ''}
    if token in '0123':
        return {'surface': 'stone', 'blocked': False,
                'feature': 'stairs', 'height': int(token)}
    raise RuleError('Structure inconnue ou invalide')


def structure_template(name, quarter_turns=0, *, door_slot=0):
    """Return a fresh TerrainClipboard suitable for preview, rotation or paste."""
    require(isinstance(name, str) and name in _STRUCTURE_PLANS,
            'Unknown structure preset')
    require(type(quarter_turns) is int and 0 <= quarter_turns <= 3,
            'Rotation must be 0, 1, 2 or 3 quarter turns')
    require(type(door_slot) is int and 0 <= door_slot < len(door_slots(name)),
            'Invalid structure door slot')
    rows = _STRUCTURE_PLANS[name]
    width, height = len(rows[0]), len(rows)
    require(all(len(row) == width for row in rows),
            'Inconsistent structure dimensions')
    offsets = tuple((x, y) for y in range(height) for x in range(width))
    default_entry = door_slots(name)[0] if name in STRUCTURE_DOOR_SLOTS else None
    alternate_entry = door_slots(name)[door_slot] if default_entry else None
    def token(x, y):
        current = rows[y][x]
        if default_entry is not None and door_slot:
            if (x, y) == default_entry:
                return '.'
            if (x, y) == alternate_entry:
                return 'D'
        return current
    terrain = tuple(_tile_for_token(token(x, y)) for x, y in offsets)
    clip = _validate_clipboard(TerrainClipboard(width, height, offsets, terrain, ()))
    for _ in range(quarter_turns):
        clip = transform_terrain(clip, 'rotate_cw')
    return clip


def structure_footprint(clip, anchor):
    """Unclipped absolute positions, to support a visible red invalid preview."""
    _validate_clipboard(clip)
    require(isinstance(anchor, (list, tuple)) and len(anchor) == 2 and
            all(type(value) is int for value in anchor),
            'Choose a structure anchor cell')
    x0, y0 = anchor
    return tuple((x0+dx, y0+dy) for dx, dy in clip.offsets)


def validate_structure_placement(data, mission_id, clip, anchor):
    """Guard tactical references and boundaries before overwriting terrain.

    Occupied units (including multi-cell units), interactive objects, mission
    goals and relic positions are not disposable scenery. Invalid placements
    never remove them. Existing terrain/props may intentionally be replaced.
    """
    mission = _mission(data, mission_id)
    destination = structure_footprint(clip, anchor)
    for cell in destination:
        _cell(mission, cell)
    selected = set(destination)
    occupied = set()
    for unit in mission.get('units', ()):
        x, y = unit['pos']
        width, height = unit.get('footprint', (1, 1))
        occupied.update((x+dx, y+dy) for dy in range(height)
                        for dx in range(width))
    require(not selected.intersection(occupied),
            'Structure overlaps an existing unit footprint')
    require(not selected.intersection(tuple(obj['pos']) for obj in mission.get('objects', ())),
            'Structure overlaps an interactive object')
    require(not selected.intersection(tuple(goal) for goal in mission.get('goal', ())),
            'Structure would overwrite an authored mission goal')
    relic = mission.get('relic')
    if relic is not None:
        require(tuple(relic) not in selected,
                'Structure overlaps a mission relic')
    # Overwriting recorded footprints would leave contradictory identities.
    for existing in mission.get('structures', ()):
        prior = structure_template(existing['name'], existing['turns'],
                                   door_slot=existing['door_slot'])
        require(not selected.intersection(structure_footprint(
                    prior, existing['anchor'])),
                'Structure overlaps an existing authored structure')
    blocked = {cell for cell, tile in zip(destination, clip.terrain)
               if tile.get('blocked', False)}
    zones = {tuple(cell) for zone in mission.get('deployment', ())
             for cell in zone.get('cells', ())}
    require(not blocked.intersection(zones),
            'Structure wall would block an authored deployment zone')
    return destination


def place_structure(data, mission_id, name, anchor, quarter_turns=0, *, door_slot=0):
    """Paste tiles and store an optional, stable visual identity atomically."""
    clip = structure_template(name, quarter_turns, door_slot=door_slot)
    footprint = validate_structure_placement(data, mission_id, clip, anchor)
    from .structure_underlay import capture_underlay
    underlay = capture_underlay(_mission(data, mission_id), footprint)
    updated = paste_terrain(data, mission_id, clip, anchor)
    mission = _mission(updated, mission_id)
    structures = mission.setdefault('structures', [])
    names = {record['id'] for record in structures}
    index = 1
    while 'structure_' + str(index) in names:
        index += 1
    structures.append({'id': 'structure_' + str(index), 'name': name,
                       'anchor': list(anchor), 'turns': quarter_turns,
                       'door_slot': door_slot, 'underlay': underlay})
    return Content.from_dict(updated).to_dict()


def remove_structure(data, mission_id, cell):
    """Remove a persistent OR legacy building and its tiles in one edit.

    A normal paint brush never removes an identity. Use this explicit
    operation to delete the visual instance together with its footprint.
    """
    from .iso_architecture import architecture_instances
    target = _cell(_mission(data, mission_id), cell)
    content = Content.from_dict(data)
    mission_obj = content.missions[mission_id]
    instance = next((item for item in architecture_instances(
        mission_obj.board, mission_obj.structures) if target in item.cells), None)
    require(instance is not None, 'No structure at selected cell')
    updated = deepcopy(data)
    mission = _mission(updated, mission_id)
    from .structure_underlay import restore_footprint
    restore_footprint(mission, instance)
    if instance.id and mission.get('interior_floors'):
        mission['interior_floors'] = [
            floor for floor in mission['interior_floors']
            if floor['structure_id'] != instance.id]
    return Content.from_dict(updated).to_dict()


def structure_at(data, mission_id, cell):
    """Find an authored or inferred legacy structure covering a clicked cell."""
    from .iso_architecture import architecture_instances, _stored_instance
    mission_row = _mission(data, mission_id)
    target = _cell(mission_row, cell)
    # Most structures now have persistent records. Avoid parsing the entire
    # campaign on every hover/click just to resolve one stored footprint.
    for record in mission_row.get('structures', ()):
        clip = structure_template(record['name'], record['turns'],
                                  door_slot=record['door_slot'])
        if target in structure_footprint(clip, record['anchor']):
            return _stored_instance(record)
    # Older documents have only terrain stamps and require legacy inference.
    mission = Content.from_dict(data).missions[mission_id]
    instance = next((item for item in architecture_instances(
        mission.board, mission.structures) if target in item.cells), None)
    require(instance is not None, 'No structure at selected cell')
    return instance


def _structure_edit_plan(data, mission_id, cell, *, anchor=None,
                         name=None, quarter_turns=None, door_slot=None,
                         duplicate=False):
    """Prepare/validate a move or copy without mutating the input document.

    A move removes the old visual identity and its tactical stamp *before*
    checking the destination. This permits self-overlapping moves, while
    keeping other buildings, units, objects and objectives protected.
    """
    require(type(duplicate) is bool, 'Invalid duplicate flag')
    instance = structure_at(data, mission_id, cell)
    name = instance.name if name is None else name
    quarter_turns = instance.turns if quarter_turns is None else quarter_turns
    door_slot = instance.door_slot if door_slot is None else door_slot
    anchor = instance.anchor if anchor is None else anchor
    clip = structure_template(name, quarter_turns, door_slot=door_slot)
    # Do not silently reinterpret an invalid anchor as a placement pivot.
    structure_footprint(clip, anchor)
    original = (instance.name, instance.anchor, instance.turns, instance.door_slot)
    requested = (name, tuple(anchor), quarter_turns, door_slot)
    prepared = deepcopy(data)
    mission = _mission(prepared, mission_id)
    if not duplicate:
        from .structure_underlay import restore_footprint
        restore_footprint(mission, instance)
    if duplicate or requested != original:
        validate_structure_placement(prepared, mission_id, clip, anchor)
        # Legacy stamps also reserve real ground. Do not overwrite them
        # merely because they have no authored identity record yet.
        from .iso_architecture import architecture_instances
        scene = Content.from_dict(prepared).missions[mission_id]
        destination = set(structure_footprint(clip, anchor))
        for other in architecture_instances(scene.board, scene.structures):
            require(not destination.intersection(other.cells),
                    'Structure overlaps an existing legacy structure')
    return prepared, instance, requested, original


def validate_structure_edit(data, mission_id, cell, *, anchor=None,
                            name=None, quarter_turns=None, door_slot=None,
                            duplicate=False):
    """Headless placement check, also used for drag-preview colouring."""
    _structure_edit_plan(data, mission_id, cell, anchor=anchor, name=name,
                         quarter_turns=quarter_turns, door_slot=door_slot,
                         duplicate=duplicate)


def edit_structure(data, mission_id, cell, *, anchor=None, name=None,
                   quarter_turns=None, door_slot=None, duplicate=False):
    """Edit a whole structure atomically; legacy stamps gain an identity.

    A changed structure is re-stamped from its canonical preset. Newly
    authored structures restore their recorded sparse underlying terrain;
    records predating snapshots keep legacy erase semantics. Tactical
    repaint done over the structure itself does not overwrite its underlay.
    The source ID survives a move/property edit; copies receive a new ID.
    """
    prepared, instance, requested, original = _structure_edit_plan(
        data, mission_id, cell, anchor=anchor, name=name,
        quarter_turns=quarter_turns, door_slot=door_slot,
        duplicate=duplicate)
    if not duplicate and requested == original and instance.id:
        return deepcopy(data)
    chosen_name, chosen_anchor, chosen_turns, chosen_door = requested
    result = place_structure(prepared, mission_id, chosen_name,
                             chosen_anchor, chosen_turns, door_slot=chosen_door)
    if not duplicate and instance.id:
        # The new record is last; its automatically chosen ID is replaced
        # with the old persistent ID without touching any other record.
        _mission(result, mission_id)['structures'][-1]['id'] = instance.id
    return Content.from_dict(result).to_dict()


def move_structure(data, mission_id, cell, anchor):
    """Move a structure by its clicked footprint cell, preserving its ID."""
    return edit_structure(data, mission_id, cell, anchor=anchor)


def duplicate_structure(data, mission_id, cell, anchor):
    """Clone a preset at a new anchor with a distinct visual identity."""
    return edit_structure(data, mission_id, cell, anchor=anchor, duplicate=True)

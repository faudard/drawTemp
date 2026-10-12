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
    validate_structure_placement(data, mission_id, clip, anchor)
    updated = paste_terrain(data, mission_id, clip, anchor)
    mission = _mission(updated, mission_id)
    structures = mission.setdefault('structures', [])
    names = {record['id'] for record in structures}
    index = 1
    while 'structure_' + str(index) in names:
        index += 1
    structures.append({'id': 'structure_' + str(index), 'name': name,
                       'anchor': list(anchor), 'turns': quarter_turns,
                       'door_slot': door_slot})
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
    if instance.id:
        mission['structures'] = [record for record in mission.get('structures', ())
                                 if record['id'] != instance.id]
    mission['board']['tiles'] = [tile for tile in mission['board']['tiles']
                                 if tuple(tile['pos']) not in instance.cells]
    return Content.from_dict(updated).to_dict()

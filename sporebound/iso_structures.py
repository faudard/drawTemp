"""Reusable, headless multi-cell scenery presets for the 2.5D map editor.

These are ordinary, rotated terrain stamps, NOT new tactical entities or a new
save schema. Their footprint is checked before one validated paste transaction.
"""
from .map_authoring import _cell, _mission, paste_terrain, TerrainClipboard
from .map_transform import _validate_clipboard, transform_terrain
from .model import RuleError, require


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


def structure_template(name, quarter_turns=0):
    """Return a fresh TerrainClipboard suitable for preview, rotation or paste."""
    require(isinstance(name, str) and name in _STRUCTURE_PLANS,
            'Unknown structure preset')
    require(type(quarter_turns) is int and 0 <= quarter_turns <= 3,
            'Rotation must be 0, 1, 2 or 3 quarter turns')
    rows = _STRUCTURE_PLANS[name]
    width, height = len(rows[0]), len(rows)
    require(all(len(row) == width for row in rows),
            'Inconsistent structure dimensions')
    offsets = tuple((x, y) for y in range(height) for x in range(width))
    terrain = tuple(_tile_for_token(rows[y][x]) for x, y in offsets)
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
    blocked = {cell for cell, tile in zip(destination, clip.terrain)
               if tile.get('blocked', False)}
    zones = {tuple(cell) for zone in mission.get('deployment', ())
             for cell in zone.get('cells', ())}
    require(not blocked.intersection(zones),
            'Structure wall would block an authored deployment zone')
    return destination


def place_structure(data, mission_id, name, anchor, quarter_turns=0):
    """Commit all cells in one content-validation transaction or none."""
    clip = structure_template(name, quarter_turns)
    validate_structure_placement(data, mission_id, clip, anchor)
    return paste_terrain(data, mission_id, clip, anchor)

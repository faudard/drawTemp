"""Transactional map-authoring operations independent of Tk and of Battle.

A clipboard copies *terrain and goal cells only*. Actors, triggers and siege
objects have identities and links, so silently cloning them would be unsafe.
Every edit is validated as complete Content before returning a new document.
"""
from copy import deepcopy
from dataclasses import dataclass

from .model import Content, RuleError, require


def _mission(data, mission_id):
    require(isinstance(data, dict) and isinstance(data.get('missions'), list),
            'Invalid content document')
    mission = next((m for m in data['missions'] if m.get('id') == mission_id), None)
    require(mission is not None, f'Unknown mission: {mission_id}')
    return mission


def _cell(mission, value):
    require(isinstance(value, (tuple, list)) and len(value) == 2
            and all(type(n) is int for n in value), 'Expected a map cell (x, y)')
    x, y = value
    require(0 <= x < mission['board']['width']
            and 0 <= y < mission['board']['height'],
            f'Cell outside the map: {value}')
    return x, y


def cells_in_rectangle(data, mission_id, start, end):
    """Inclusive rectangle, compatible with reversed corners."""
    mission = _mission(data, mission_id)
    x1, y1 = _cell(mission, start)
    x2, y2 = _cell(mission, end)
    return tuple((x, y) for y in range(min(y1, y2), max(y1, y2) + 1)
                 for x in range(min(x1, x2), max(x1, x2) + 1))


def selected_cells(data, mission_id, cells):
    """Canonical ordered selection. Reject bool coordinates and off-board cells."""
    require(isinstance(cells, (list, tuple, set, frozenset)) and bool(cells),
            'Select at least one cell')
    mission = _mission(data, mission_id)
    result = {_cell(mission, cell) for cell in cells}
    return tuple(sorted(result, key=lambda cell: (cell[1], cell[0])))


def _transaction(data, mission_id, edit):
    updated = deepcopy(data)
    mission = _mission(updated, mission_id)
    edit(mission)
    return Content.from_dict(updated).to_dict()


@dataclass(frozen=True)
class TerrainClipboard:
    """Sparse offsets anchored at top-left; snapshot is independent of source."""
    width: int
    height: int
    offsets: tuple
    terrain: tuple
    goals: tuple


def copy_terrain(data, mission_id, cells):
    selected = selected_cells(data, mission_id, cells)
    mission = _mission(data, mission_id)
    x0, y0 = min(x for x, _ in selected), min(y for _, y in selected)
    x1, y1 = max(x for x, _ in selected), max(y for _, y in selected)
    tiles = {tuple(t['pos']): t for t in mission['board']['tiles']}
    goals = {tuple(c) for c in mission.get('goal', [])}
    offsets = tuple((x-x0, y-y0) for x, y in selected)
    terrain = tuple(deepcopy({k: v for k, v in tiles.get(c, {}).items()
                              if k != 'pos'}) for c in selected)
    goal_offsets = tuple((x-x0, y-y0) for x, y in selected if (x, y) in goals)
    return TerrainClipboard(x1-x0+1, y1-y0+1, offsets, terrain, goal_offsets)


def paste_terrain(data, mission_id, clipboard, anchor):
    require(isinstance(clipboard, TerrainClipboard)
            and clipboard.offsets and len(clipboard.offsets) == len(clipboard.terrain),
            'Copy terrain before pasting')
    mission = _mission(data, mission_id)
    x0, y0 = _cell(mission, anchor)
    destination = tuple(_cell(mission, (x0+dx, y0+dy))
                        for dx, dy in clipboard.offsets)
    require(len(set(destination)) == len(destination),
            'Clipboard contains duplicate cells')
    source_goals = set(clipboard.goals)
    require(source_goals <= set(clipboard.offsets), 'Invalid clipboard goals')
    copied_terrain = deepcopy(clipboard.terrain)

    def change(m):
        selected = set(destination)
        m['board']['tiles'] = [tile for tile in m['board']['tiles']
                               if tuple(tile['pos']) not in selected]
        m['board']['tiles'].extend(
            [{'pos': list(cell), **tile} for cell, tile in
             zip(destination, copied_terrain) if tile])
        existing_goals = {tuple(c) for c in m.get('goal', [])} - selected
        existing_goals.update((x0+dx, y0+dy) for dx, dy in source_goals)
        m['goal'] = [list(c) for c in sorted(existing_goals, key=lambda c: (c[1], c[0]))]
    return _transaction(data, mission_id, change)


def move_unit(data, mission_id, unit_id, cell):
    mission = _mission(data, mission_id)
    target = _cell(mission, cell)
    def change(m):
        unit = next((u for u in m['units'] if u['id'] == unit_id), None)
        require(unit is not None, f'Unknown unit: {unit_id}')
        unit['pos'] = list(target)
    return _transaction(data, mission_id, change)


def move_object(data, mission_id, object_id, cell):
    mission = _mission(data, mission_id)
    target = _cell(mission, cell)
    def change(m):
        obj = next((o for o in m['objects'] if o['id'] == object_id), None)
        require(obj is not None, f'Unknown object: {object_id}')
        dx, dy = target[0] - obj['pos'][0], target[1] - obj['pos'][1]
        obj['pos'] = list(target)
        # Defense fields are geometrically attached to the weapon.
        if obj['kind'] == 'defense':
            obj['cells'] = [[x+dx, y+dy] for x, y in obj['cells']]
        # A passage destination is its explicitly authored exit: do not shift.
    return _transaction(data, mission_id, change)


def paint_deployment(data, mission_id, zone_id, cells, *, erase=False):
    """Paint a deployment zone; seed a new zone with current player footprints.

    A zone must contain full player spawns or Content validation rejects it.
    Removing the last zone deletes the zone (unrestricted legacy deployment).
    """
    require(isinstance(zone_id, str) and zone_id and len(zone_id) <= 64
            and all(c.isalnum() or c in '_-' for c in zone_id),
            'Invalid deployment zone identifier')
    selected = set(selected_cells(data, mission_id, cells))
    def change(m):
        zones = m.setdefault('deployment', [])
        zone = next((z for z in zones if z['id'] == zone_id), None)
        if zone is None:
            require(not erase, 'Unknown deployment zone')
            # First authored zone must not strand starting player characters.
            spawn = set()
            if not zones:
                for u in m['units']:
                    if u['team'] == 'player' and u['hp'] > 0:
                        x, y = u['pos']
                        w, h = u.get('footprint', [1, 1])
                        spawn.update((x+dx, y+dy) for dy in range(h)
                                     for dx in range(w))
            zone = {'id': zone_id, 'cells': []}
            zones.append(zone)
            selected.update(spawn)
        current = {tuple(c) for c in zone['cells']}
        current = current - selected if erase else current | selected
        if not current:
            zones.remove(zone)
        else:
            zone['cells'] = [list(c) for c in sorted(current, key=lambda c: (c[1], c[0]))]
    return _transaction(data, mission_id, change)

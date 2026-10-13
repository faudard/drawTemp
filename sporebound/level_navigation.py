"""Deterministic navigation across authored interior floors.

Layer 0 is the legacy tactical board; 1..3 are existing authored upper decks.
Connections are explicit, undirected stair/ladder links. This module contains
no renderer/Tk logic and does not invent three-dimensional combat physics.
"""
from heapq import heappop, heappush
from .model import RuleError, require
from .interior_levels import MAX_INTERIOR_LEVEL


def walkable_levels(mission):
    """Map each level to available absolute (x,y) cells."""
    cells = {0: {cell for cell in mission.board.cells()
                 if not mission.board.tile(cell).blocked}}
    structures = {item['id']: item for item in mission.structures}
    for floor in mission.interior_floors:
        parent = structures[floor['structure_id']]
        x0, y0 = parent['anchor']
        cells.setdefault(floor['level'], set()).update(
            (x0+tile['pos'][0], y0+tile['pos'][1])
            for tile in floor['tiles'])
    return cells


def validate_levels(mission):
    """Reject dangling connectors, invalid upper-floor spawns and gaps."""
    from .model import distance
    levels = walkable_levels(mission)
    ids = {u.id for u in mission.units}
    require(type(mission.unit_levels) is dict, 'Unit levels must be an object')
    require(set(mission.unit_levels) <= ids, 'Unknown unit in level placement')
    require(not mission.unit_levels or bool(mission.level_links),
            'Upper-floor spawns require an authored connector')
    for uid, level in mission.unit_levels.items():
        require(type(level) is int and 1 <= level <= MAX_INTERIOR_LEVEL,
                'Unit spawn level must be 1..3')
        actor = next(u for u in mission.units if u.id == uid)
        require(actor.footprint == (1, 1),
                'Upper-floor units currently require a 1x1 footprint')
        require(tuple(actor.pos) in levels.get(level, set()),
                'Unit spawn is not on an authored upper-floor tile')
        require(not (actor.team == 'player' and mission.deployment),
                'Upper-floor player spawns cannot use ground-only deployment')

    require(type(mission.level_links) is list, 'Level links must be a list')
    link_ids, pairs = set(), set()
    for edge in mission.level_links:
        require(type(edge) is dict and set(edge) == {'id', 'from', 'to', 'cost'},
                'Invalid level connection fields')
        lid = edge['id']
        require(type(lid) is str and 1 <= len(lid) <= 64 and lid.isascii()
                and lid[0].isalpha() and all(ch.isalnum() or ch in '_-' for ch in lid)
                and lid not in link_ids, 'Invalid or duplicate level connector id')
        link_ids.add(lid)
        ends = []
        for key in ('from', 'to'):
            value = edge[key]
            require(type(value) is list and len(value) == 3
                    and all(type(v) is int for v in value),
                    'Connector endpoints must be [level, x, y]')
            level, x, y = value
            require(level in levels and (x, y) in levels[level],
                    'Connector endpoint is not walkable')
            ends.append(tuple(value))
        a, b = ends
        require(abs(a[0]-b[0]) == 1 and distance(a[1:], b[1:]) <= 1,
                'Connectors must link adjacent floors at nearby cells')
        key = tuple(sorted((a, b)))
        require(key not in pairs, 'Duplicate level connection')
        pairs.add(key)
        require(type(edge['cost']) is int and 1 <= edge['cost'] <= 20,
                'Connector movement cost must be 1..20')
    return levels


def available_level_moves(battle, unit=None):
    """Dijkstra paths indexed by (level,x,y); each result (cost,path).

    Legacy Battle.reachable remains a 2D interface; this method is the new
    explicit multilevel query. No implicit vertical adjacency or teleports.
    """
    unit = unit or battle.active
    if (unit is None or not unit.alive or unit.moved
            or battle.status_blocks(unit, 'move')):
        return {}
    require(unit.footprint == (1, 1),
            'Layered navigation currently requires a 1x1 unit')
    floors = walkable_levels(battle.mission)
    level = battle.unit_levels.get(unit.id, 0)
    origin = (level, *unit.pos)
    budget = battle.movement_budget(unit)
    occupied = {(battle.unit_levels.get(o.id, 0), *cell)
                for o in battle.units if o.alive and o.id != unit.id
                for cell in o.occupied_cells()}
    links = {}
    for edge in battle.mission.level_links:
        a, b = tuple(edge['from']), tuple(edge['to'])
        links.setdefault(a, []).append((b, edge['cost']))
        links.setdefault(b, []).append((a, edge['cost']))
    result = {origin: (0, [origin])}
    queue = [(0, origin)]
    while queue:
        spent, pos = heappop(queue)
        if spent != result[pos][0]:
            continue
        lvl, x, y = pos
        edges = [(tuple((lvl, x+dx, y+dy)), None)
                 for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))]
        edges.extend(links.get(pos, ()))
        for other, transition in edges:
            target_level, tx, ty = other
            if (tx, ty) not in floors.get(target_level, set()) or other in occupied:
                continue
            if transition is None and lvl == 0 and not battle.can_step_height(
                    unit, (x, y), (tx, ty)):
                continue
            cost = ((battle.board.tile((tx, ty)).cost if lvl == 0 else 1)
                    if transition is None else transition)
            new_cost = spent + cost
            if new_cost <= budget and (other not in result or
                                       new_cost < result[other][0]):
                result[other] = (new_cost, result[pos][1] + [other])
                heappush(queue, (new_cost, other))
    return result


def navigate_level(battle, unit, *, level, cell):
    """Execute one full layered move as a single undoable/replayable command.

    Reactions, hazards and 3D LOS are not yet defined for upstairs traversal;
    they cannot be silently applied using ground-floor collision rules.
    """
    require(type(level) is int and 0 <= level <= MAX_INTERIOR_LEVEL,
            'Invalid destination level')
    require(type(cell) in (tuple, list) and len(cell) == 2
            and all(type(v) is int for v in cell), 'Invalid level destination')
    destination = (level, *cell)
    current = (battle.unit_levels.get(unit.id, 0), *unit.pos)
    require(current[0] > 0 or level > 0,
            'Use ordinary ground movement for ground-only destinations')
    reachable = available_level_moves(battle, unit)
    require(destination != current and destination in reachable,
            'Layered destination unreachable or movement spent')
    cost, path = reachable[destination]
    # Legacy event consumers still see the 2D position, but level transition
    # and path are recorded explicitly. All mutation belongs to Battle.execute.
    unit.pos = tuple(cell)
    if level:
        battle.unit_levels[unit.id] = level
    else:
        battle.unit_levels.pop(unit.id, None)
    unit.moved = True
    battle.emit('level_move', unit=unit.id, start=list(current),
                end=list(destination), path=[list(p) for p in path], cost=cost)
    return cost


def add_level_link(data, mission_id, source, destination, *, cost=1):
    """Create a bidirectional stair connector without editing raw JSON."""
    from copy import deepcopy
    from .model import Content
    require(type(source) in (list, tuple) and type(destination) in (list, tuple)
            and all(type(v) is int for v in (*source, *destination))
            and len(source) == len(destination) == 3,
            'Expected endpoints [level, x, y]')
    updated = deepcopy(data)
    mission = next((m for m in updated['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown mission')
    rows = mission.setdefault('level_links', [])
    existing = {row['id'] for row in rows}
    index = 1
    while 'stair_' + str(index) in existing:
        index += 1
    rows.append({'id': 'stair_' + str(index),
                 'from': list(source), 'to': list(destination),
                 'cost': cost})
    return Content.from_dict(updated).to_dict()


def remove_level_link(data, mission_id, connector_id):
    from copy import deepcopy
    from .model import Content
    updated = deepcopy(data)
    mission = next((m for m in updated['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown mission')
    links = mission.get('level_links', [])
    require(any(x['id'] == connector_id for x in links),
            'Unknown level connector')
    mission['level_links'] = [row for row in links if row['id'] != connector_id]
    return Content.from_dict(updated).to_dict()


def place_unit_on_level(data, mission_id, unit_id, level, cell):
    """Author an upper-floor spawn without changing any other unit's position."""
    from copy import deepcopy
    from .model import Content
    require(type(level) is int and 0 <= level <= MAX_INTERIOR_LEVEL,
            'Invalid unit spawn level')
    require(type(cell) in (list, tuple) and len(cell) == 2
            and all(type(v) is int for v in cell), 'Invalid spawn position')
    updated = deepcopy(data)
    mission = next((m for m in updated['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown mission')
    unit = next((u for u in mission['units'] if u['id'] == unit_id), None)
    require(unit is not None, 'Unknown unit')
    unit['pos'] = list(cell)
    levels = mission.setdefault('unit_levels', {})
    if level:
        levels[unit_id] = level
    else:
        levels.pop(unit_id, None)
    return Content.from_dict(updated).to_dict()

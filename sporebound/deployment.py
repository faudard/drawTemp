"""Pre-battle placement policies shared by content validation and the runtime."""
from .model import require


def cell(value):
    require(isinstance(value, (list, tuple)) and len(value) == 2
            and all(type(n) is int for n in value), "Invalid deployment cell")
    return tuple(value)


def validate(mission):
    zones = mission.deployment
    require(isinstance(zones, list), "Deployment zones must be a list")
    ids = set()
    closed = {tuple(o['pos']) for o in mission.objects
              if o['kind'] == 'door' and not o.get('open', False)}
    for zone in zones:
        require(isinstance(zone, dict), "Invalid deployment zone")
        zid = zone.get('id')
        require(isinstance(zid, str) and zid and zid not in ids, "Invalid deployment zone id")
        ids.add(zid)
        require(isinstance(zone.get('cells'), list) and zone['cells'], "Empty deployment zone")
        cells = [cell(c) for c in zone['cells']]
        require(len(set(cells)) == len(cells), "Duplicate deployment cell")
        require(all(mission.board.contains(c) and not mission.board.tile(c).blocked
                    and c not in closed for c in cells), "Blocked deployment zone")
    if zones:
        for unit in mission.units:
            if unit.team == 'player' and unit.alive:
                require(in_zone(mission, unit, unit.pos), "Player spawn outside deployment zones")


def in_zone(mission, unit, anchor):
    footprint = unit.occupied_cells(anchor)
    return any(footprint <= {tuple(c) for c in zone['cells']} for zone in mission.deployment)


def check_position(battle, unit, anchor):
    require(in_zone(battle.mission, unit, anchor), "Entire unit must fit in one deployment zone")
    occupied = set().union(*(u.occupied_cells() for u in battle.units
                             if u.id != unit.id and u.alive))
    require(all(battle.board.contains(c) and not battle.board.tile(c).blocked
                and c not in occupied for c in unit.occupied_cells(anchor)),
            "Deployment position is blocked or occupied")


def execute(battle, command):
    kind = command.get('kind')
    if kind == 'deploy':
        uid = command.get('unit')
        unit = next((u for u in battle.units if u.id == uid), None)
        require(unit is not None and unit.team == 'player' and unit.alive,
                "Only living player units can deploy")
        anchor = cell(command.get('cell'))
        facing = cell(command.get('facing', unit.facing))
        require(facing in {(0, 1), (0, -1), (1, 0), (-1, 0)}, "Invalid deployment facing")
        check_position(battle, unit, anchor)
        unit.pos, unit.facing = anchor, facing
        battle.emit('unit_deployed', unit=unit.id, pos=anchor, facing=facing)
    elif kind == 'start_battle':
        for unit in battle.units:
            if unit.team == 'player' and unit.alive:
                check_position(battle, unit, unit.pos)
        battle.deploying = False
        battle.emit('deployment_completed')
        for unit in battle.units:
            battle._collect(unit)
        battle._advance()
    else:
        require(False, "Deploy your units, then start the battle")

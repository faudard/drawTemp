"""Data-defined traversals and crew-operated defensive emplacements."""
from .model import distance, require


def validate(mission, obj, cell, integer):
    if obj['kind'] == 'passage':
        cell(obj['destination'], mission.board)
        require(tuple(obj['pos']) != tuple(obj['destination']), 'Passage endpoints must differ')
        require(not mission.board.tile(tuple(obj['pos'])).blocked
                and not mission.board.tile(tuple(obj['destination'])).blocked, 'Blocked passage endpoint')
        integer(obj.get('cost', 2), 1, 99, 'passage.cost')
        for flag in ('enabled', 'bidirectional'):
            require(type(obj.get(flag, True)) is bool, 'Invalid passage flag')
    if obj['kind'] == 'defense':
        require(obj.get('team') in {'player', 'enemy'}, 'Defense needs a team')
        require(isinstance(obj.get('cells'), list) and bool(obj['cells']), 'Defense needs target cells')
        for target in obj['cells']:
            cell(target, mission.board)
        integer(obj.get('power', 15), 1, 10000, 'defense.power')
        integer(obj.get('charges', 2), 0, 100, 'defense.charges')
        integer(obj.get('cooldown', 20), 1, 10000, 'defense.cooldown')
        require(type(obj.get('disabled', False)) is bool, 'Invalid defense disabled flag')
        require('ready_at' not in obj, 'Defense ready_at is runtime-only')


def links(battle, origin):
    for obj in battle.mission.objects:
        if obj['kind'] != 'passage' or not obj.get('enabled', True):
            continue
        start, end = tuple(obj['pos']), tuple(obj['destination'])
        if origin == start:
            yield end, obj.get('cost', 2)
        if origin == end and obj.get('bidirectional', True):
            yield start, obj.get('cost', 2)


def defense_targets(battle, obj):
    cells = {tuple(c) for c in obj['cells']}
    return [u for u in battle.units if u.alive and u.occupied_cells() & cells]


def defense_ready(battle, obj):
    return (not obj.get('disabled', False) and obj.get('charges', 2) > 0
            and battle.tick >= obj.get('ready_at', 0))


def defense_value(battle, unit, obj):
    if not defense_ready(battle, obj) or unit.team != obj['team']:
        return 0
    return sum(min(u.hp, obj.get('power', 15)) * (1 if u.team != unit.team else -2)
               for u in defense_targets(battle, obj))


def interact(battle, unit, obj):
    if obj['kind'] == 'passage':
        require(not obj.get('enabled', True), 'Passage already installed: move to traverse it')
        obj['enabled'] = True
        battle.emit('passage_installed', unit=unit.id, object=obj['id'])
    elif unit.team != obj['team']:
        require(not obj.get('disabled', False), 'Defense already sabotaged')
        obj['disabled'] = True
        battle.emit('defense_sabotaged', unit=unit.id, object=obj['id'])
    else:
        require(defense_ready(battle, obj), 'Defense empty, cooling down or sabotaged')
        obj['charges'] = obj.get('charges', 2) - 1
        obj['ready_at'] = battle.tick + obj.get('cooldown', 20)
        battle.emit('defense_fired', unit=unit.id, object=obj['id'], cells=obj['cells'])
        # Fixed footprint; friendly fire is intentional, each large actor hit once.
        for target in defense_targets(battle, obj):
            battle._hurt(target, obj.get('power', 15), unit, reactions=False)
    unit.acted = True
    unit.cast = None

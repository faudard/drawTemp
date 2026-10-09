"""Validated scenario predicates and actions, dispatched independently."""
from copy import deepcopy
from dataclasses import dataclass
from ..model import require
from .registry import Registry, TriggerActionRule, TriggerConditionRule


@dataclass(frozen=True)
class ValidationContext:
    board: object
    unit_ids: set
    rules: object
    archetypes: dict | None = None

    def integer(self, value, low, high):
        require(type(value) is int and low <= value <= high, f'Expected integer {low}..{high}')

    def cell(self, value):
        require(isinstance(value, (tuple, list)) and len(value) == 2
                and all(type(v) is int for v in value) and self.board.contains(value), 'Invalid trigger cell')

    def unit(self, uid):
        require(uid in self.unit_ids, 'Unknown trigger unit')


def hazard(battle, action):
    cell = tuple(action['pos'])
    battle.board.tiles[cell] = deepcopy(battle.board.tile(cell))
    battle.board.tiles[cell].hazard = action['amount']


def validate_hazard(context, action):
    context.cell(action['pos'])
    context.integer(action['amount'], 0, 10000)


def validate_status(context, action):
    context.unit(action['unit'])
    context.rules.statuses.get(action['status'])
    context.integer(action['duration'], 1, 10000)


def validate_wave_limit(context, action):
    context.integer(action['max_alive'], 0, 100000)


def wave_capacity(battle, action):
    team = action.get('team', 'enemy')
    return sum(u.alive and u.team == team for u in battle.units) <= action['max_alive']


def validate_wave_capacity(context, trigger):
    context.integer(trigger['max_alive'], 0, 100000)
    require(trigger.get('team', 'enemy') in {'enemy', 'player', 'neutral'}, 'Invalid wave team')


def default_trigger_conditions():
    return Registry((
        ('tick', TriggerConditionRule(lambda b, t: b.tick >= t['value'],
                                     lambda c, t: c.integer(t['value'], 0, 100000))),
        ('enter', TriggerConditionRule(lambda b, t: any(u.alive and u.team == 'player' and u.pos == tuple(t['pos']) for u in b.units),
                                      lambda c, t: c.cell(t['pos']))),
        ('wave_capacity', TriggerConditionRule(wave_capacity, validate_wave_capacity)),
        ('defeated', TriggerConditionRule(lambda b, t: not b.unit(t['unit']).alive,
                                         lambda c, t: c.unit(t['unit']))),
    ))


def spawn_actor(battle, action):
    spec = deepcopy(action['actor'])
    battle.spawn_actor(spec, lifetime=action.get('lifetime'), owner_id=action.get('owner'))


def validate_spawn(context, action):
    require(isinstance(action.get('actor'), dict), 'Spawn actor must be an object')
    actor = action['actor']
    require(isinstance(actor.get('id'), str) and actor['id'], 'Spawn actor needs id')
    require('pos' in actor, 'Spawn actor needs pos')
    context.cell(actor['pos'])
    archetype = actor.get('archetype', '')
    require(not archetype or (context.archetypes is not None and archetype in context.archetypes), 'Unknown spawn archetype')
    if 'lifetime' in action:
        context.integer(action['lifetime'], 1, 100000)
    if 'owner' in action:
        context.unit(action['owner'])


def validate_despawn(context, action):
    require(isinstance(action.get('unit'), str) and action['unit'], 'Despawn needs unit id')


def validate_wave(context, action):
    actors = action.get('actors')
    require(isinstance(actors, list) and bool(actors), 'Wave needs actors')
    ids = set()
    for actor in actors:
        require(isinstance(actor, dict), 'Wave actor must be an object')
        uid = actor.get('id')
        require(isinstance(uid, str) and bool(uid) and uid not in ids, 'Duplicate or invalid wave actor')
        require(uid not in context.unit_ids, 'Wave actor conflicts with mission unit')
        ids.add(uid)
        require('pos' in actor, 'Wave actor needs pos')
        context.cell(actor['pos'])
        archetype = actor.get('archetype', '')
        require(not archetype or (context.archetypes is not None and archetype in context.archetypes), 'Unknown wave archetype')
    if 'lifetime' in action:
        context.integer(action['lifetime'], 1, 100000)


def default_trigger_actions():
    return Registry((
        ('hazard', TriggerActionRule(hazard, validate_hazard)),
        ('status', TriggerActionRule(lambda b, a: b._status(b.unit(a['unit']), a['status'], a['duration']), validate_status)),
        ('message', TriggerActionRule(lambda b, a: b.emit('message', text=a.get('text', '')), lambda c, a: None)),
        ('spawn', TriggerActionRule(spawn_actor, validate_spawn)),
        ('wave', TriggerActionRule(lambda b, a: b.spawn_wave(a['actors'], lifetime=a.get('lifetime')), validate_wave)),
        ('despawn', TriggerActionRule(lambda b, a: b.despawn_actor(a['unit']), validate_despawn)),
    ))


def dispatch(battle):
    for trigger in battle.mission.triggers:
        if trigger['id'] in battle.fired:
            continue
        if not battle.rules.trigger_conditions.get(trigger['condition']).matches(battle, trigger):
            continue
        battle.fired.append(trigger['id'])
        battle.emit('trigger', id=trigger['id'])
        for action in trigger['actions']:
            battle.rules.trigger_actions.get(action['kind']).apply(battle, action)

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


def default_trigger_conditions():
    return Registry((
        ('tick', TriggerConditionRule(lambda b, t: b.tick >= t['value'],
                                     lambda c, t: c.integer(t['value'], 0, 100000))),
        ('enter', TriggerConditionRule(lambda b, t: any(u.alive and u.team == 'player' and u.pos == tuple(t['pos']) for u in b.units),
                                      lambda c, t: c.cell(t['pos']))),
        ('defeated', TriggerConditionRule(lambda b, t: not b.unit(t['unit']).alive,
                                         lambda c, t: c.unit(t['unit']))),
    ))


def spawn_actor(battle, action):\n    spec = deepcopy(action['actor'])\n    battle.spawn_actor(spec, lifetime=action.get('lifetime'))\n\n\ndef validate_spawn(context, action):\n    require(isinstance(action.get('actor'), dict), 'Spawn actor must be an object')\n    actor = action['actor']\n    require(isinstance(actor.get('id'), str) and actor['id'], 'Spawn actor needs id')\n    context.cell(actor['pos'])\n    archetype = actor.get('archetype', '')\n    require(not archetype or (context.archetypes is not None and archetype in context.archetypes), 'Unknown spawn archetype')\n    if 'lifetime' in action:\n        context.integer(action['lifetime'], 1, 100000)\n\n\ndef validate_despawn(context, action):\n    require(isinstance(action.get('unit'), str) and action['unit'], 'Despawn needs unit id')\n\n\ndef default_trigger_actions():
    return Registry((
        ('hazard', TriggerActionRule(hazard, validate_hazard)),
        ('status', TriggerActionRule(lambda b, a: b._status(b.unit(a['unit']), a['status'], a['duration']), validate_status)),
        ('message', TriggerActionRule(lambda b, a: b.emit('message', text=a.get('text', '')), lambda c, a: None)),\n        ('spawn', TriggerActionRule(spawn_actor, validate_spawn)),\n        ('despawn', TriggerActionRule(lambda b, a: b.despawn_actor(a['unit']), validate_despawn)),
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

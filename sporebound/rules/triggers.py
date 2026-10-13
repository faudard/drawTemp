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
    object_ids: set | None = None

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


def wave_capacity(battle, action):
    team = action.get('team', 'enemy')
    return sum(u.alive and u.team == team for u in battle.units) <= action['max_alive']


def validate_wave_capacity(context, trigger):
    context.integer(trigger['max_alive'], 0, 100000)
    require(trigger.get('team', 'enemy') in {'enemy', 'player', 'neutral'}, 'Invalid wave team')


def hp_below(battle, trigger):
    """One-shot boss phase gate: living actor at or below a HP percentage."""
    actor = next((u for u in battle.units if u.id == trigger['unit']), None)
    return (actor is not None and actor.alive
            and actor.hp * 100 <= actor.max_hp * trigger['percent'])


def validate_hp_below(context, trigger):
    context.unit(trigger['unit'])
    context.integer(trigger['percent'], 1, 99)


def interact_condition(battle, trigger):
    """Match interaction events produced by the battle command handler."""
    return any(row['kind'] == 'interact' and row.get('object') == trigger['object']
               for row in battle.events)


def validate_interact(context, trigger):
    require(isinstance(trigger.get('object'), str) and
            context.object_ids is not None and
            trigger['object'] in context.object_ids,
            'Unknown interactive object for trigger')


def default_trigger_conditions():
    return Registry((
        ('tick', TriggerConditionRule(lambda b, t: b.tick >= t['value'],
                                     lambda c, t: c.integer(t['value'], 0, 100000))),
        ('enter', TriggerConditionRule(lambda b, t: any(u.alive and u.team == 'player' and u.pos == tuple(t['pos']) for u in b.units),
                                      lambda c, t: c.cell(t['pos']))),
        ('wave_capacity', TriggerConditionRule(wave_capacity, validate_wave_capacity)),
        ('hp_below', TriggerConditionRule(hp_below, validate_hp_below)),
        ('defeated', TriggerConditionRule(lambda b, t: not b.unit(t['unit']).alive,
                                         lambda c, t: c.unit(t['unit']))),
        ('interact', TriggerConditionRule(interact_condition, validate_interact)),
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
    if 'max_active' in action:
        context.integer(action['max_active'], 1, 100)


def queue_wave(battle, action):
    battle.queue_wave(action['actors'], lifetime=action.get('lifetime'))


def default_trigger_actions():
    return Registry((
        ('hazard', TriggerActionRule(hazard, validate_hazard)),
        ('status', TriggerActionRule(lambda b, a: b._status(b.unit(a['unit']), a['status'], a['duration']), validate_status)),
        ('message', TriggerActionRule(lambda b, a: b.emit('message', text=a.get('text', '')), lambda c, a: None)),
        ('spawn', TriggerActionRule(spawn_actor, validate_spawn)),
        ('queue_wave', TriggerActionRule(queue_wave, validate_wave)),
        ('wave', TriggerActionRule(lambda b, a: b.spawn_wave(a['actors'], lifetime=a.get('lifetime'), max_active=a.get('max_active', 14)), validate_wave)),
        ('despawn', TriggerActionRule(lambda b, a: b.despawn_actor(a['unit']), validate_despawn)),
    ))


# Opt-in tactical composite predicates stay in the canonical trigger dispatcher.
# Leaves delegate to the registered rule set (including authored rule overrides),
# not an editor-only evaluator. Legacy rules/manifests remain unchanged.
COMPOSITE_MAX_DEPTH = 4
COMPOSITE_MAX_NODES = 32


def validate_composite(context, node, *, _depth=0, _count=None):
    if _count is None:
        _count = [0]
    _count[0] += 1
    require(_count[0] <= COMPOSITE_MAX_NODES and _depth < COMPOSITE_MAX_DEPTH,
            'Composite condition exceeds depth/node limits')
    require(isinstance(node, dict), 'Composite condition must be an object')
    if 'condition' in node:
        require(node['condition'] not in ('all', 'any', 'not') and
                'when' not in node and 'actions' not in node,
                'Composite leaf must use an existing atomic predicate')
        context.rules.trigger_conditions.get(node['condition']).validate(context, node)
        return
    require(len(node) == 1, 'Composite condition needs one operator')
    operator = next(iter(node))
    require(operator in ('all', 'any', 'not'), 'Unknown composite operator')
    if operator == 'not':
        validate_composite(context, node['not'], _depth=_depth + 1,
                           _count=_count)
    else:
        children = node[operator]
        require(isinstance(children, list) and 2 <= len(children) <= 8,
                'AND/OR needs between 2 and 8 conditions')
        for child in children:
            validate_composite(context, child, _depth=_depth + 1,
                               _count=_count)


def matches_composite(battle, node):
    """Use the registered gameplay rules, never duplicate leaf logic."""
    if 'condition' in node:
        return battle.rules.trigger_conditions.get(node['condition']).matches(
            battle, node)
    if 'all' in node:
        return all(matches_composite(battle, part) for part in node['all'])
    if 'any' in node:
        return any(matches_composite(battle, part) for part in node['any'])
    return not matches_composite(battle, node['not'])


def dispatch(battle):
    for trigger in battle.mission.triggers:
        if trigger['id'] in battle.fired:
            continue
        if not battle.rules.trigger_conditions.get(trigger['condition']).matches(battle, trigger):
            continue
        if 'when' in trigger and not matches_composite(battle, trigger['when']):
            continue
        battle.fired.append(trigger['id'])
        battle.emit('trigger', id=trigger['id'])
        for action in trigger['actions']:
            battle.rules.trigger_actions.get(action['kind']).apply(battle, action)

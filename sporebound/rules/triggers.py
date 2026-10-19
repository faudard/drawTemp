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


def dispatch(battle, *, observer=None, before_fire=None, fire_limit=None):
    """Run the one canonical tactical dispatcher, with opt-in Studio hooks.

    All normal Battle callers omit the hooks and retain historical behavior.
    A disposable debug Battle may observe evaluated conditions, pause *before*
    an event or execute a bounded number of real events. Nothing is serialized
    by these hooks; no second interpreter, scheduler or rule registry exists.
    """
    require(fire_limit is None or
            (type(fire_limit) is int and 1 <= fire_limit <= 200),
            'Invalid event-debug step limit')
    from ..temporal_events import temporal_status
    from ..event_pages import active_page, can_fire_page
    events = battle.mission.triggers
    cascades = any('after' in row or 'after_any' in row for row in events)
    fired_now = 0
    for pass_number in range(len(events) if cascades else 1):
        progressed = False
        for trigger in events:
            eid = trigger['id']
            paged = ('pages' in trigger or 'repeat' in trigger or
                     'enabled' in trigger)
            if eid in battle.fired and not paged:
                continue
            blocked = [ref for ref in trigger.get('after', ())
                       if ref not in battle.fired]
            options = trigger.get('after_any', ())
            alternate_missing = (list(options) if options and
                                 not any(ref in battle.fired for ref in options)
                                 else [])
            if blocked or alternate_missing:
                if observer is not None:
                    observer({'event_id': eid, 'state': 'waiting',
                              'missing': blocked,
                              'any_missing': alternate_missing,
                              'pass': pass_number})
                continue
            guard = trigger.get('after_choice')
            if guard and not any(
                    row['kind'] == 'story_choice' and
                    row.get('scene') == guard['scene'] and
                    row.get('choice') == guard['choice']
                    for row in battle.events):
                if observer is not None:
                    observer({'event_id': eid, 'state': 'choice_false',
                              'choice': deepcopy(guard),
                              'pass': pass_number})
                continue
            if any(key in trigger for key in (
                    'cancel_after', 'delay_ticks', 'delay_activations',
                    'expire_after_ticks', 'expire_after_activations')):
                temporal = temporal_status(battle, trigger)
                if temporal['state'] != 'ready':
                    if observer is not None:
                        observer({'event_id': eid, 'state': temporal['state'],
                                  'pass': pass_number})
                    continue
            if paged:
                # The canonical dispatcher chooses one highest-priority page;
                # conditions, state toggles and cooldowns are journal-derived.
                page = active_page(battle, trigger)
                if page is None or not can_fire_page(battle, trigger, page):
                    if observer is not None:
                        observer({'event_id': eid,
                                  'state': 'page_inactive' if page is None
                                  else 'page_waiting',
                                  'page': None if page is None else page['id'],
                                  'pass': pass_number})
                    continue
                actions = page['actions']
            else:
                if not battle.rules.trigger_conditions.get(
                        trigger['condition']).matches(battle, trigger):
                    if observer is not None:
                        observer({'event_id': eid, 'state': 'condition_false',
                                  'pass': pass_number})
                    continue
                if 'when' in trigger and not matches_composite(
                        battle, trigger['when']):
                    if observer is not None:
                        observer({'event_id': eid, 'state': 'composite_false',
                                  'pass': pass_number})
                    continue
                actions = trigger['actions']
            if before_fire is not None and before_fire(trigger):
                if observer is not None:
                    observer({'event_id': eid, 'state': 'breakpoint',
                              'pass': pass_number})
                return {'fired': fired_now, 'paused': eid}
            if eid not in battle.fired:
                battle.fired.append(eid)
            if paged:
                battle.emit('trigger', id=eid, page=page['id'])
            else:
                battle.emit('trigger', id=eid)
            for action in actions:
                battle.rules.trigger_actions.get(action['kind']).apply(
                    battle, action)
            fired_now += 1
            progressed = True
            if observer is not None:
                observer({'event_id': eid, 'state': 'fired',
                          'pass': pass_number})
            if fire_limit is not None and fired_now >= fire_limit:
                return {'fired': fired_now, 'paused': None}
        if not cascades or not progressed:
            break
    return {'fired': fired_now, 'paused': None}

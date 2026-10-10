"""Small typed event composer; each action is a declarative engine rule.

An event is saved in one validated document transaction. Ordering of actions
is explicit and preserved for replay determinism.
"""
from copy import deepcopy

from .authoring import _cell, _identifier, _mission
from .model import Content, require


def condition(kind, *, pos=None, tick=10, unit='', percent=50,
              max_alive=4, team='enemy'):
    require(kind in {'tick', 'enter', 'defeated', 'hp_below', 'wave_capacity'},
            'Unknown event condition')
    if kind == 'tick':
        return {'condition': kind, 'value': tick}
    if kind == 'enter':
        return {'condition': kind, 'pos': list(pos)}
    if kind == 'hp_below':
        return {'condition': kind, 'unit': unit, 'percent': percent}
    if kind == 'wave_capacity':
        return {'condition': kind, 'max_alive': max_alive, 'team': team}
    return {'condition': kind, 'unit': unit}


def action(kind, *, pos=None, text='', amount=4, unit='', status='haste',
           duration=10, actor_id='', archetype='', team='enemy', name='Renfort',
           max_active=14, lifetime=None):
    if kind == 'message':
        return {'kind': kind, 'text': text}
    if kind == 'hazard':
        return {'kind': kind, 'pos': list(pos), 'amount': amount}
    if kind == 'status':
        return {'kind': kind, 'unit': unit, 'status': status, 'duration': duration}
    if kind == 'despawn':
        return {'kind': kind, 'unit': unit}
    if kind in ('spawn', 'wave', 'queue_wave'):
        _identifier(actor_id, 'Spawn actor id')
        require(archetype, 'Choose an actor archetype')
        require(team in ('player', 'enemy'), 'Unknown team')
        require(isinstance(pos, (tuple, list)) and len(pos) == 2 and
                all(type(v) is int for v in pos), 'Choose a valid spawn cell')
        actor = {'id': actor_id, 'name': name, 'team': team,
                 'pos': list(pos), 'archetype': archetype}
        if kind == 'spawn':
            result = {'kind': kind, 'actor': actor}
        else:
            result = {'kind': kind, 'actors': [actor]}
            if kind == 'wave':
                require(type(max_active) is int and 1 <= max_active <= 100,
                        'Invalid maximum active reinforcements')
                result['max_active'] = max_active
        if lifetime is not None:
            require(type(lifetime) is int and lifetime >= 1,
                    'Invalid reinforcement lifetime')
            result['lifetime'] = lifetime
        return result
    raise ValueError(f'Unknown event action: {kind}')


def save_event(data, mid, eid, condition_data, actions):
    _identifier(eid, 'Event id')
    require(isinstance(condition_data, dict) and 'condition' in condition_data,
            'Event needs a condition')
    require(isinstance(actions, list) and bool(actions), 'Event needs at least one action')
    new = deepcopy(data)
    mission = _mission(new, mid)
    require(mission is not None, 'Unknown mission')
    event = {'id': eid, **deepcopy(condition_data),
             'actions': deepcopy(actions)}
    # Replacing an event is atomic; the unchanged document is kept on failure.
    events = mission.setdefault('triggers', [])
    position = next((i for i, row in enumerate(events) if row['id'] == eid), None)
    if position is None:
        events.append(event)
    else:
        events[position] = event
    return Content.from_dict(new).to_dict()


def move_action(actions, index, offset):
    require(type(index) is int and type(offset) is int and offset in (-1, 1),
            'Invalid action move')
    require(0 <= index < len(actions) and 0 <= index + offset < len(actions),
            'Cannot move action outside event')
    result = deepcopy(actions)
    result[index], result[index + offset] = result[index + offset], result[index]
    return result

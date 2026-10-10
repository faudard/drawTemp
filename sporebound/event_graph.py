"""Deterministic visual DAG and atomic edits for tactical mission triggers.

Triggers are one-shot rules evaluated in their authored list order. Within one
trigger, actions run sequentially. Edges in the diagram are presentation-only;
the serialized content remains Mission.triggers (no new runtime schema).
"""
from copy import deepcopy

from . import event_composer
from .authoring import _identifier, _mission
from .model import Content, RuleError, require


def _find_event(data, mission_id, event_id):
    mission = _mission(data, mission_id)
    require(mission is not None, f'Unknown mission: {mission_id}')
    event = next((e for e in mission.get('triggers', [])
                  if e['id'] == event_id), None)
    require(event is not None, f'Unknown tactical event: {event_id}')
    return event


def _save(data, mission_id, event_id, event):
    require(isinstance(event, dict) and
            event.get('id') == event_id and
            isinstance(event.get('actions'), list) and event['actions'],
            'An event must contain at least one action')
    return event_composer.save_event(
        data, mission_id, event_id,
        {k: deepcopy(v) for k, v in event.items()
         if k not in ('id', 'actions')},
        event['actions'])


def update_condition(data, mission_id, event_id, condition):
    """Replace the condition, preserving action IDs/order in one undo step."""
    require(isinstance(condition, dict) and 'condition' in condition,
            'Choose a valid trigger condition')
    event = deepcopy(_find_event(data, mission_id, event_id))
    event = {'id': event_id, **deepcopy(condition), 'actions': event['actions']}
    return _save(data, mission_id, event_id, event)


def add_action(data, mission_id, event_id, action, *, index=None):
    event = deepcopy(_find_event(data, mission_id, event_id))
    require(isinstance(action, dict) and
            isinstance(action.get('kind'), str), 'Invalid event action')
    if index is None:
        index = len(event['actions'])
    require(type(index) is int and 0 <= index <= len(event['actions']),
            'Invalid action insertion index')
    event['actions'].insert(index, deepcopy(action))
    return _save(data, mission_id, event_id, event)


def update_action(data, mission_id, event_id, index, action):
    event = deepcopy(_find_event(data, mission_id, event_id))
    require(type(index) is int and 0 <= index < len(event['actions']),
            'Unknown event action')
    require(isinstance(action, dict) and
            isinstance(action.get('kind'), str), 'Invalid event action')
    event['actions'][index] = deepcopy(action)
    return _save(data, mission_id, event_id, event)


def remove_action(data, mission_id, event_id, index):
    event = deepcopy(_find_event(data, mission_id, event_id))
    require(type(index) is int and 0 <= index < len(event['actions']),
            'Unknown event action')
    require(len(event['actions']) > 1,
            'An event must retain at least one action')
    del event['actions'][index]
    return _save(data, mission_id, event_id, event)


def reorder_action(data, mission_id, event_id, index, direction):
    event = deepcopy(_find_event(data, mission_id, event_id))
    event['actions'] = event_composer.move_action(
        event['actions'], index, direction)
    return _save(data, mission_id, event_id, event)


def reorder_event(data, mission_id, event_id, direction):
    """The outer event ordering is runtime-observable; preserve it explicitly."""
    require(type(direction) is int and direction in (-1, 1),
            'Invalid event direction')
    result = deepcopy(data)
    mission = _mission(result, mission_id)
    require(mission is not None, 'Unknown mission')
    events = mission.get('triggers', [])
    index = next((i for i, e in enumerate(events)
                  if e['id'] == event_id), None)
    require(index is not None and 0 <= index + direction < len(events),
            'Cannot move event outside mission')
    events[index], events[index+direction] = events[index+direction], events[index]
    return Content.from_dict(result).to_dict()


def delete_event(data, mission_id, event_id):
    result = deepcopy(data)
    mission = _mission(result, mission_id)
    require(mission is not None, 'Unknown mission')
    previous = len(mission.get('triggers', []))
    mission['triggers'] = [e for e in mission.get('triggers', [])
                           if e['id'] != event_id]
    require(len(mission['triggers']) < previous, 'Unknown tactical event')
    return Content.from_dict(result).to_dict()


def duplicate_event(data, mission_id, event_id, new_id):
    """Clone a trigger only if actor identity is not duplicated by its actions."""
    _identifier(new_id, 'New event id')
    event = deepcopy(_find_event(data, mission_id, event_id))
    require(not any(a['kind'] in ('spawn', 'wave', 'queue_wave')
                    for a in event['actions']),
            'Cannot duplicate spawn or wave actions: actor IDs must be unique')
    result = deepcopy(data)
    mission = _mission(result, mission_id)
    require(mission is not None, 'Unknown mission')
    require(all(e['id'] != new_id for e in mission.get('triggers', [])),
            'Event id already exists')
    event['id'] = new_id
    mission['triggers'].append(event)
    return Content.from_dict(result).to_dict()


def condition_title(event):
    kind = event['condition']
    if kind == 'tick':
        return f"Tick ≥ {event['value']}"
    if kind == 'enter':
        return f"Entrée en {tuple(event['pos'])}"
    if kind == 'defeated':
        return f"Défaite de {event['unit']}"
    if kind == 'hp_below':
        return f"{event['unit']} : PV ≤ {event['percent']} %"
    if kind == 'wave_capacity':
        return f"Capacité {event.get('team', 'enemy')} ≤ {event['max_alive']}"
    return kind


def action_title(action):
    kind = action.get('kind', '?')
    if kind == 'message':
        return 'Message : '+str(action.get('text', ''))[:48]
    if kind == 'hazard':
        return f"Danger {action.get('amount')} en {tuple(action.get('pos', ())) }"
    if kind == 'status':
        return f"Statut {action.get('status')} → {action.get('unit')}"
    if kind == 'spawn':
        return 'Apparition : '+str(action.get('actor', {}).get('id', '?'))
    if kind in ('wave', 'queue_wave'):
        return ('Vague immédiate : ' if kind == 'wave' else 'Renforts en attente : ') + str(
            len(action.get('actors', ()))) + ' acteurs'
    if kind == 'despawn':
        return 'Retirer : '+str(action.get('unit', '?'))
    return kind


def build_event_graph(data, mission_id, *, max_events=200, max_nodes=600):
    """Bounded deterministic presentation DAG, with sequence and stable paths.

    Each trigger has one condition vertex, then one vertex per ordered action.
    Any event beyond node budget is omitted (never silently changed).
    """
    require(type(max_events) is int and 1 <= max_events <= 1000,
            'Invalid graph event limit')
    require(type(max_nodes) is int and 2 <= max_nodes <= 3000,
            'Invalid graph node limit')
    mission = _mission(data, mission_id)
    require(mission is not None, f'Unknown mission: {mission_id}')
    triggers = mission.get('triggers', [])
    nodes, edges = [], []
    truncated = len(triggers) > max_events
    for i, event in enumerate(triggers[:max_events]):
        actions = event.get('actions', [])
        if len(nodes) + 1 + len(actions) > max_nodes:
            truncated = True
            break
        event_id = event['id']
        ckey = (event_id, 'condition')
        nodes.append(dict(key=ckey, event_id=event_id, kind='condition',
                          label=condition_title(event), x=80, y=90+i*132,
                          order=i))
        previous = ckey
        for action_index, action in enumerate(actions):
            key = (event_id, 'action', action_index)
            nodes.append(dict(key=key, event_id=event_id, kind='action',
                              index=action_index, label=action_title(action),
                              x=360+action_index*235, y=90+i*132, order=i))
            edges.append(dict(source=previous, target=key, event_id=event_id,
                              label='exécuter' if action_index == 0 else 'puis'))
            previous = key
    return dict(mission_id=mission_id, nodes=nodes, edges=edges,
                truncated=truncated, total_events=len(triggers),
                drawn_events=len({n['event_id'] for n in nodes}),
                width=max((n['x']+235 for n in nodes), default=600),
                height=max((n['y']+95 for n in nodes), default=230))

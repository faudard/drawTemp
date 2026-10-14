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
    # Editing the primary condition must not silently erase secondary predicates.
    extras = {key: deepcopy(event[key]) for key in (
        'when', 'after', 'after_any', 'after_choice',
        'delay_ticks', 'delay_activations',
        'expire_after_ticks', 'expire_after_activations', 'cancel_after')
              if key in event and key not in condition}
    event = {'id': event_id, **deepcopy(condition), **extras,
             'actions': event['actions']}
    return _save(data, mission_id, event_id, event)



def extend_condition(data, mission_id, event_id, predicate, *,
                     join='all', negate=False):
    """Add an AND/OR/NOT constraint to the selected canonical trigger.

    The primary trigger remains mandatory (e.g. a real lever interaction).
    Secondary clauses can contain nested groups. Every change is validated
    by Content and committed in a single existing document transaction.
    """
    require(join in ('all', 'any') and type(negate) is bool,
            'Choose AND or OR')
    require(isinstance(predicate, dict) and
            isinstance(predicate.get('condition'), str),
            'Choose a validated atomic condition')
    event = deepcopy(_find_event(data, mission_id, event_id))
    node = deepcopy(predicate)
    if negate:
        node = {'not': node}
    if 'when' in event:
        prior = event['when']
        if isinstance(prior, dict) and len(prior) == 1 and join in prior and (
                len(prior[join]) < 8):
            event['when'] = {join: prior[join] + [node]}
        else:
            event['when'] = {join: [prior, node]}
    else:
        event['when'] = node
    return _save(data, mission_id, event_id, event)


def clear_composite_condition(data, mission_id, event_id):
    """Clear only secondary conditions, preserving primary event and actions."""
    event = deepcopy(_find_event(data, mission_id, event_id))
    event.pop('when', None)
    return _save(data, mission_id, event_id, event)


def composite_title(node):
    if 'condition' in node:
        return condition_title(node)
    if 'not' in node:
        return 'NON (' + composite_title(node['not']) + ')'
    kind = 'all' if 'all' in node else 'any'
    return '(' + (' ET ' if kind == 'all' else ' OU ').join(
        composite_title(child) for child in node[kind]) + ')'


def _composite_child(node, index):
    """Resolve a node by an authoring-only path; no serialized node IDs."""
    require(type(index) is int and index >= 0, 'Invalid condition path')
    if 'not' in node:
        require(index == 0, 'NOT has one operand')
        return node['not']
    kind = 'all' if 'all' in node else 'any' if 'any' in node else ''
    require(bool(kind) and index < len(node[kind]), 'Unknown condition child')
    return node[kind][index]


def link_event(data, mission_id, event_id, predecessor_id):
    """Link a predecessor to the same canonical Mission.triggers event.

    References are validated transitively (unknown IDs, cycles, 8-link limit)
    by Content.from_dict in _save. No callback, event bus or runtime schema.
    """
    require(isinstance(predecessor_id, str) and bool(predecessor_id),
            'Choose a preceding event')
    event = deepcopy(_find_event(data, mission_id, event_id))
    require(event_id != predecessor_id, 'An event cannot depend on itself')
    links = event.setdefault('after', [])
    require(predecessor_id not in links, 'Prerequisite already linked')
    links.append(predecessor_id)
    return _save(data, mission_id, event_id, event)


def unlink_event(data, mission_id, event_id, predecessor_id):
    """Remove exactly one link without altering condition or actions."""
    event = deepcopy(_find_event(data, mission_id, event_id))
    links = event.get('after', [])
    require(predecessor_id in links, 'No such event prerequisite')
    links.remove(predecessor_id)
    if not links:
        event.pop('after', None)
    return _save(data, mission_id, event_id, event)


def chain_descendants(data, mission_id, event_id):
    """Connected downstream triggers in stable authoring order."""
    mission = _mission(data, mission_id)
    require(mission is not None, 'Unknown mission')
    _find_event(data, mission_id, event_id)
    seen = {event_id}
    for _ in range(len(mission.get('triggers', []))):
        old_size = len(seen)
        for candidate in mission.get('triggers', []):
            if (candidate['id'] not in seen and
                    any(ref in seen for ref in candidate.get('after', []))):
                seen.add(candidate['id'])
        if len(seen) == old_size:
            break
    return [deepcopy(row) for row in mission.get('triggers', [])
            if row['id'] in seen]


def composite_at(event, path=()):
    """Read a detached secondary predicate with a stable tuple path."""
    require(isinstance(path, (tuple, list)) and len(path) <= 8,
            'Invalid condition path')
    require('when' in event, 'No secondary condition')
    node = event['when']
    for index in path:
        node = _composite_child(node, index)
    return deepcopy(node)


def composite_nodes(event):
    """Tree projection for Tk and tests; paths never enter Mission.triggers."""
    if 'when' not in event:
        return []
    nodes = []

    def visit(node, path):
        if 'condition' in node:
            kind = 'leaf'
        else:
            kind = next(iter(node))
        nodes.append({'path': path, 'kind': kind,
                      'label': composite_title(node), 'depth': len(path)})
        if kind == 'not':
            visit(node['not'], path + (0,))
        elif kind in ('all', 'any'):
            for i, child in enumerate(node[kind]):
                visit(child, path + (i,))

    visit(event['when'], ())
    return nodes


def _replace_subtree(root, path, value):
    if not path:
        return deepcopy(value)
    result = deepcopy(root)
    parent = result
    for index in path[:-1]:
        parent = _composite_child(parent, index)
    last = path[-1]
    _composite_child(parent, last)  # bounds and operator validation
    if 'not' in parent:
        parent['not'] = deepcopy(value)
    else:
        kind = 'all' if 'all' in parent else 'any'
        parent[kind][last] = deepcopy(value)
    return result


def edit_composite_node(data, mission_id, event_id, path, *,
                        operation, predicate=None, join='all', direction=0):
    """One atomic, validated tree edit. No new predicate execution path.

    Operations: replace selected leaf; wrap selected subtree in AND/OR with
    a leaf; toggle NOT; remove; move among its siblings. Group arity is kept
    legal by collapsing a group with only one remaining child.
    """
    event = deepcopy(_find_event(data, mission_id, event_id))
    selected = composite_at(event, path)
    path = tuple(path)
    require(operation in ('replace', 'wrap', 'negate', 'remove', 'move'),
            'Unknown condition edit')
    if operation in ('replace', 'wrap'):
        require(isinstance(predicate, dict) and
                isinstance(predicate.get('condition'), str),
                'Choose an atomic predicate from the existing rule registry')
    if operation == 'replace':
        require('condition' in selected, 'Select an atomic condition to replace')
        event['when'] = _replace_subtree(event['when'], path, predicate)
    elif operation == 'wrap':
        require(join in ('all', 'any'), 'Choose AND or OR')
        event['when'] = _replace_subtree(
            event['when'], path, {join: [selected, deepcopy(predicate)]})
    elif operation == 'negate':
        result = (selected['not'] if set(selected) == {'not'}
                  else {'not': selected})
        event['when'] = _replace_subtree(event['when'], path, result)
    elif operation == 'remove':
        if not path:
            event.pop('when')
        else:
            parent_path = path[:-1]
            parent = composite_at(event, parent_path)
            if 'not' in parent:
                # Delete the entire NOT clause rather than retaining an empty op.
                return edit_composite_node(data, mission_id, event_id,
                                           parent_path, operation='remove')
            kind = 'all' if 'all' in parent else 'any'
            del parent[kind][path[-1]]
            replacement = (parent[kind][0] if len(parent[kind]) == 1
                           else parent)
            event['when'] = _replace_subtree(
                event['when'], parent_path, replacement)
    elif operation == 'move':
        require(path and type(direction) is int and direction in (-1, 1),
                'Choose a sibling direction')
        parent_path, index = path[:-1], path[-1]
        parent = composite_at(event, parent_path)
        require('all' in parent or 'any' in parent,
                'Only AND/OR operands can be moved')
        kind = 'all' if 'all' in parent else 'any'
        other = index + direction
        require(0 <= other < len(parent[kind]), 'No condition sibling there')
        parent[kind][index], parent[kind][other] = (
            parent[kind][other], parent[kind][index])
        event['when'] = _replace_subtree(
            event['when'], parent_path, parent)
    return _save(data, mission_id, event_id, event)


def configure_schedule(data, mission_id, event_id, *,
                       delay_ticks=None, delay_activations=None,
                       expire_after_ticks=None, expire_after_activations=None,
                       cancel_after=None):
    """Atomically update a canonical event's delays and cancellation guards.

    Zero removes a delay, [] clears cancellation, and None preserves a value.
    The existing Content.from_dict validation rejects orphan timers and bad
    references. No second authoring model or editor-side dispatcher is added.
    """
    event = deepcopy(_find_event(data, mission_id, event_id))
    for key, value in (('delay_ticks', delay_ticks),
                       ('delay_activations', delay_activations),
                       ('expire_after_ticks', expire_after_ticks),
                       ('expire_after_activations', expire_after_activations)):
        if value is None:
            continue
        require(type(value) is int and 0 <= value <= 10000,
                key + ' must be 0..10000')
        if value:
            event[key] = value
        else:
            event.pop(key, None)
    if cancel_after is not None:
        require(isinstance(cancel_after, (list, tuple)),
                'Choose cancellation events')
        if cancel_after:
            event['cancel_after'] = list(cancel_after)
        else:
            event.pop('cancel_after', None)
    return _save(data, mission_id, event_id, event)


def condition_summary(event):
    root = condition_title(event)
    root += (' ET ' + composite_title(event['when'])
             if 'when' in event else '')
    if event.get('after'):
        root += ' APRÈS ' + ', '.join(event['after'])
    wait = []
    if event.get('delay_ticks'):
        wait.append(str(event['delay_ticks']) + ' ticks')
    if event.get('delay_activations'):
        wait.append(str(event['delay_activations']) + ' activations')
    if wait:
        root += ' ATTENDRE ' + ' ET '.join(wait)
    expire = []
    if event.get('expire_after_ticks'):
        expire.append(str(event['expire_after_ticks']) + ' ticks')
    if event.get('expire_after_activations'):
        expire.append(str(event['expire_after_activations']) + ' activations')
    if expire:
        root += ' EXPIRE À ' + ' OU '.join(expire)
    if event.get('cancel_after'):
        root += ' ANNULÉ APRÈS ' + ', '.join(event['cancel_after'])
    return root


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


def append_wave_actor(data, mission_id, event_id, index, actor):
    """Add a second or later actor to an existing wave, with full validation."""
    event = deepcopy(_find_event(data, mission_id, event_id))
    require(type(index) is int and 0 <= index < len(event['actions']),
            'Unknown wave action')
    action = event['actions'][index]
    require(action['kind'] in ('wave', 'queue_wave'),
            'Choose an existing reinforcement wave action')
    require(isinstance(actor, dict) and isinstance(actor.get('id'), str),
            'Invalid reinforcement actor')
    action['actors'].append(deepcopy(actor))
    return _save(data, mission_id, event_id, event)


def remove_wave_actor(data, mission_id, event_id, index):
    """Remove last authored wave actor while retaining a valid nonempty wave."""
    event = deepcopy(_find_event(data, mission_id, event_id))
    require(type(index) is int and 0 <= index < len(event['actions']),
            'Unknown wave action')
    action = event['actions'][index]
    require(action['kind'] in ('wave', 'queue_wave') and
            len(action.get('actors', [])) > 1,
            'A reinforcement wave needs at least one actor')
    action['actors'].pop()
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
    if kind == 'interact':
        return f"Objet actionné : {event['object']}"
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
                          label=condition_summary(event), x=80, y=90+i*132,
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
    # Dependencies are navigable links between the existing condition/action
    # vertices. Their IDs are *not* new serialized graph nodes.
    available = {node['key'] for node in nodes}
    last_action = {row['id']: (row['id'], 'action', len(row['actions']) - 1)
                   for row in triggers if row.get('actions')}
    for event in triggers[:max_events]:
        target = (event['id'], 'condition')
        if target not in available:
            continue
        for predecessor in event.get('after', []):
            source = last_action.get(predecessor)
            if source in available:
                edges.append(dict(source=source, target=target,
                                  event_id=event['id'],
                                  label='après événement'))
    return dict(mission_id=mission_id, nodes=nodes, edges=edges,
                truncated=truncated, total_events=len(triggers),
                drawn_events=len({n['event_id'] for n in nodes}),
                width=max((n['x']+235 for n in nodes), default=600),
                height=max((n['y']+95 for n in nodes), default=230))

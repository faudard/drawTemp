"""Read-only large-campaign branch navigation and tactical route comparison.

This module projects the canonical GameProject.story and Mission.triggers;
node occurrence paths are never persisted. It is independent of Tk, Battle
and GameSession. Output is deterministic and bounded even for malformed input.
"""
from .model import require


def trace_occurrence(story, root, path):
    """Resolve a StoryGraph occurrence into concrete scenes/choices, not IDs.

    An occurrence is (root_scene, choice_id, choice_id, ...). A final choice
    without next_scene is a valid terminal occurrence. Reused scenes retain
    one canonical ID and multiple unique occurrence paths.
    """
    scenes = {scene['id']: scene for scene in story.get('scenes', [])}
    require(isinstance(path, tuple) and bool(path) and path[0] == root,
            'Choose a path from the active story root')
    require(root in scenes, 'Unknown narrative root')
    require(len(path) <= 66, 'Narrative path exceeds 64 decisions')
    current = root
    visited = []
    decisions = []
    for choice_id in path[1:]:
        require(current in scenes, 'The occurrence continues after an ending')
        scene = scenes[current]
        selected = next((row for row in scene['choices']
                         if row['id'] == choice_id), None)
        require(selected is not None, 'The narrative occurrence is stale')
        decisions.append({
            'scene_id': current, 'scene_title': scene['title'],
            'choice_id': choice_id, 'label': selected['label'],
            'condition': selected.get('when'),
            'effects': selected.get('effects', []),
            'tactical_effects': selected.get('tactical_effects', []),
            'next_scene': selected.get('next_scene', ''),
        })
        visited.append(current)
        current = selected.get('next_scene', '')
    if current:
        require(current in scenes, 'Unknown final narrative scene')
        visited.append(current)
    return {'root': root, 'path': path, 'scenes': visited,
            'decisions': decisions, 'ending': not bool(current),
            'end_scene': current}


def compare_occurrences(story, data, mission_id, root, path_a, path_b):
    """Compare two actual occurrence paths including choice-gated events."""
    a = trace_occurrence(story, root, path_a)
    b = trace_occurrence(story, root, path_b)
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown mission for branch comparison')
    guarded = {
        (e['after_choice']['scene'], e['after_choice']['choice']): []
        for e in mission.get('triggers', []) if 'after_choice' in e
    }
    for event in mission.get('triggers', []):
        guard = event.get('after_choice')
        if guard is not None:
            guarded[(guard['scene'], guard['choice'])].append(event['id'])

    def annotate(route):
        steps = []
        for row in route['decisions']:
            key = (row['scene_id'], row['choice_id'])
            steps.append({
                **row, 'event_ids': guarded.get(key, []),
            })
        return {**route, 'steps': steps,
                'event_ids': list(dict.fromkeys(
                    eid for row in steps for eid in row['event_ids']))}
    a, b = annotate(a), annotate(b)
    shared_length = 0
    for left, right in zip(a['steps'], b['steps']):
        if (left['scene_id'], left['choice_id']) != (
                right['scene_id'], right['choice_id']):
            break
        shared_length += 1
    return {
        'a': a, 'b': b,
        'shared_steps': a['steps'][:shared_length],
        'only_a': a['steps'][shared_length:],
        'only_b': b['steps'][shared_length:],
        'only_a_events': sorted(set(a['event_ids']) - set(b['event_ids'])),
        'only_b_events': sorted(set(b['event_ids']) - set(a['event_ids'])),
        'common_events': sorted(set(a['event_ids']) & set(b['event_ids'])),
    }


def grouped_branches(story, root, data, mission_id, *,
                     max_depth=32, max_visits=1500):
    """Summarize first-level choices without expanding every occurrence.

    Count unique scene references and choice-guarded events by branch. A
    shared scene counts once within each branch, not once globally; this is
    intentional, because choices can converge.
    """
    require(type(max_depth) is int and 1 <= max_depth <= 64,
            'Invalid grouping depth')
    require(type(max_visits) is int and 10 <= max_visits <= 20000,
            'Invalid grouping budget')
    scenes = {scene['id']: scene for scene in story.get('scenes', [])}
    require(root in scenes, 'Unknown narrative root')
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown mission')
    guards = {}
    for event in mission.get('triggers', []):
        guard = event.get('after_choice')
        if guard:
            guards.setdefault((guard['scene'], guard['choice']), []).append(
                event['id'])
    budget = [max_visits]
    results = []
    for first in scenes[root]['choices']:
        known, events = set(), set()
        leaves = [0]
        truncated = [False]
        def walk(sid, depth, active):
            if not sid:
                leaves[0] += 1
                return
            if sid in active or depth > max_depth or budget[0] <= 0:
                truncated[0] = True
                return
            budget[0] -= 1
            known.add(sid)
            for choice in scenes[sid]['choices']:
                events.update(guards.get((sid, choice['id']), ()))
                walk(choice.get('next_scene', ''), depth+1, active | {sid})
        events.update(guards.get((root, first['id']), ()))
        walk(first.get('next_scene', ''), 1, {root})
        results.append({
            'choice_id': first['id'], 'label': first['label'],
            'next_scene': first.get('next_scene', ''),
            'scene_count': len(known), 'ending_count': leaves[0],
            'event_ids': sorted(events), 'truncated': truncated[0],
        })
    return results


def grouped_collapse_paths(story, root, *, at_depth=2, max_visits=3500):
    """Generate UI-only collapsed *occurrences* below the first subbranches."""
    require(type(at_depth) is int and 1 <= at_depth <= 20,
            'Invalid automatic collapse depth')
    scenes = {scene['id']: scene for scene in story.get('scenes', [])}
    require(root in scenes, 'Unknown narrative root')
    collapsed = set()
    todo = [(root, (root,), 0, frozenset())]
    seen = 0
    while todo and seen < max_visits:
        sid, path, depth, active = todo.pop()
        seen += 1
        if not sid or sid in active:
            continue
        if depth >= at_depth:
            if any(choice.get('next_scene') for choice in scenes[sid]['choices']):
                collapsed.add(path)
            continue
        for choice in reversed(scenes[sid]['choices']):
            next_id = choice.get('next_scene', '')
            if next_id:
                todo.append((next_id, path+(choice['id'],),
                             depth+1, active | {sid}))
    return collapsed


def format_path_comparison(report):
    def path_label(item):
        return ' → '.join(
            step['choice_id'] for step in item['steps']) or '(racine)'
    lines = [
        'COMPARAISON DES PARCOURS — StoryBook / événements tactiques',
        'A : '+path_label(report['a']),
        'B : '+path_label(report['b']),
        'Décisions communes : '+str(len(report['shared_steps'])),
    ]
    for label, steps, events in (
            ('A seulement', report['only_a'], report['only_a_events']),
            ('B seulement', report['only_b'], report['only_b_events'])):
        lines.append(label + ' :')
        if not steps:
            lines.append('  Même choix sur cette portion.')
        for step in steps:
            lines.append('  '+step['scene_title']+' → '+step['label'])
            if step['condition']:
                lines.append('    Condition : '+str(step['condition']))
            for effect in step['effects']:
                lines.append('    Effet narratif : '+str(effect))
            for effect in step['tactical_effects']:
                lines.append('    Effet tactique : '+str(effect))
        lines.append('  Événements exclusifs : '+(', '.join(events) or 'aucun'))
    lines.append('Événements communs : ' +
                 (', '.join(report['common_events']) or 'aucun'))
    return lines

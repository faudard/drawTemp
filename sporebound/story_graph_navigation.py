"""Read-only Story Graph navigation, grounded structural reachability diagnostics.

Only GameProject.story and Content.missions are indexed; search, filters,
routing and orphan reports never mutate authored data or claim to evaluate
runtime flags, mission outcomes, or dialogue availability.
"""
from collections import deque
import unicodedata

from .model import require


FILTERS = ('all', 'scenes', 'choices', 'conditions', 'events', 'issues')


def _fold(value):
    normalized = unicodedata.normalize('NFKD', str(value))
    return ''.join(ch for ch in normalized
                   if not unicodedata.combining(ch)).casefold()


def entry_scene_ids(story):
    """Include *all* runtime entry families, not the editor's chosen root."""
    require(isinstance(story, dict), 'Invalid narrative graph')
    keys = ('entry_scenes', 'after_mission', 'during_tactical_event',
            'after_strategic_event')
    roots = set()
    for key in keys:
        mapping = story.get(key, {})
        require(isinstance(mapping, dict), 'Invalid narrative entry map')
        roots.update(sid for sid in mapping.values() if sid)
    return sorted(roots)


def _scene_map(story):
    scenes = story.get('scenes', [])
    require(isinstance(scenes, list), 'Invalid narrative scene collection')
    mapping = {s['id']: s for s in scenes}
    require(len(mapping) == len(scenes), 'Duplicate narrative scene')
    return mapping


def _traverse(scenes, roots, *, conditional=True, max_nodes=20000):
    """Iterative bounded traversal, cycle-safe and linear in visited choices."""
    queue = deque(sid for sid in sorted(set(roots)) if sid in scenes)
    visited = set()
    while queue:
        sid = queue.popleft()
        if sid in visited:
            continue
        require(len(visited) < max_nodes, 'Narrative reachability budget exceeded')
        visited.add(sid)
        for choice in scenes[sid].get('choices', []):
            if not conditional and choice.get('when') is not None:
                continue
            target = choice.get('next_scene', '')
            if target in scenes and target not in visited:
                queue.append(target)
    return visited


def navigation_diagnostics(story, *, max_nodes=20000):
    """Flag disconnected authoring without treating conditional paths as dead.

    Structural orphans may be intentionally reusable/unlinked draft scenes.
    Conditions mark 'conditional_only'; their satisfiability is unknown here.
    """
    scenes = _scene_map(story)
    roots = entry_scene_ids(story)
    inbound = {sid: 0 for sid in scenes}
    for scene in scenes.values():
        for choice in scene.get('choices', []):
            target = choice.get('next_scene', '')
            if target in inbound:
                inbound[target] += 1
    reachable = _traverse(scenes, roots, max_nodes=max_nodes)
    unconditional = _traverse(
        scenes, roots, conditional=False, max_nodes=max_nodes)
    records = []
    for sid in sorted(scenes):
        if sid not in reachable:
            status = 'unreferenced' if inbound[sid] == 0 else 'disconnected'
        elif sid not in unconditional:
            status = 'conditional_only'
        else:
            status = 'reachable'
        records.append({
            'scene_id': sid, 'title': scenes[sid]['title'],
            'status': status, 'incoming': inbound[sid],
            'entry': sid in roots,
        })
    return {
        'entries': roots, 'missing_entries': [s for s in roots if s not in scenes],
        'total_scenes': len(scenes),
        'reachable_count': len(reachable),
        'records': records,
        'structurally_unreachable': [
            row for row in records if row['status'] in ('unreferenced', 'disconnected')],
        'conditional_only': [
            row for row in records if row['status'] == 'conditional_only'],
    }


def shortest_occurrence(story, root, destination, *, max_nodes=20000,
                        max_depth=64):
    """Shortest canonical choice-ID occurrence, or None for no structural path.

    Never use per-occurrence expansion as a search index. Cycles are bounded
    by visited scene IDs, and the returned tuple is StoryGraph-compatible.
    """
    scenes = _scene_map(story)
    require(root in scenes and destination in scenes,
            'Unknown source or destination scene')
    require(type(max_depth) is int and 0 <= max_depth <= 64,
            'Invalid search depth')
    frontier = deque([(root, (root,))])
    visited = {root}
    while frontier:
        sid, path = frontier.popleft()
        if sid == destination:
            return path
        if len(path)-1 >= max_depth:
            continue
        for choice in scenes[sid].get('choices', []):
            target = choice.get('next_scene', '')
            if target in scenes and target not in visited:
                require(len(visited) < max_nodes,
                        'Narrative navigation budget exceeded')
                visited.add(target)
                frontier.append((target, path+(choice['id'],)))
    return None


def search_narrative(story, data, mission_id, query='', *,
                     kind='all', max_results=100):
    """Deterministic, bounded results across scenes, choices and mission events.

    Search uses canonical IDs. Statuses are authoring diagnostics, not game
    execution predictions. Return the match total separately from display cap.
    """
    require(kind in FILTERS, 'Unknown narrative search filter')
    require(isinstance(query, str) and len(query) <= 160,
            'Search text must be up to 160 characters')
    require(type(max_results) is int and 1 <= max_results <= 500,
            'Invalid search result cap')
    scenes = _scene_map(story)
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown mission')
    statuses = {r['scene_id']: r['status']
                for r in navigation_diagnostics(story)['records']}
    needle = _fold(query.strip())
    results = []
    count = 0

    def emit(item, haystack):
        nonlocal count
        if needle and needle not in _fold(' '.join(map(str, haystack))):
            return
        count += 1
        if len(results) < max_results:
            results.append(item)

    for sid in sorted(scenes):
        scene = scenes[sid]
        status = statuses[sid]
        issue = status != 'reachable'
        if kind in ('all', 'scenes') or kind == 'issues' and issue:
            emit({
                'kind': 'scene', 'id': sid, 'scene_id': sid,
                'label': scene['title'], 'status': status,
            }, (sid, scene['title'], scene.get('speaker',''),
                scene.get('text','')))
        if kind in ('all', 'choices', 'conditions', 'issues'):
            for choice in scene.get('choices', []):
                conditional = choice.get('when') is not None
                if kind == 'conditions' and not conditional:
                    continue
                if kind == 'issues' and not (issue or conditional):
                    continue
                emit({
                    'kind': 'choice', 'id': sid+'/'+choice['id'],
                    'scene_id': sid, 'choice_id': choice['id'],
                    'label': choice['label'],
                    'status': 'conditional_only' if conditional else status,
                }, (sid, choice['id'], choice['label'],
                    choice.get('next_scene',''), choice.get('when','')))
    if kind in ('all', 'events'):
        for event in sorted(mission.get('triggers', []),
                            key=lambda e: e['id']):
            actions = ' '.join(str(a) for a in event.get('actions', []))
            guard = event.get('after_choice', {})
            emit({
                'kind': 'event', 'id': event['id'], 'event_id': event['id'],
                'label': event['condition'], 'status': 'event',
            }, (event['id'], event['condition'], actions,
                guard.get('scene',''), guard.get('choice','')))
    return {'results': results, 'matches': count,
            'truncated': count > len(results),
            'filter': kind, 'query': query, 'mission_id': mission_id}

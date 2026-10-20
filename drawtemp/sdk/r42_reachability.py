"""R42.C deterministic reachability through the actual GameSession narrative API.

Entry-scene narrative choices only: no fabricated combat victory, scene route,
trigger event or Battle replay. Conditional choices are evaluated by R9 and
reward effects are applied by GameSession, never by a shadow interpreter.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
import json

from sporebound.game_session import GameSession
from sporebound.model import require


def audit_narrative(content, project, campaign_id, *, expected_endings=(),
                    min_reused_scenes=0, max_states=2048, max_choices=32,
                    strict=False):
    """Enumerate narrative branches, produce route witnesses and dead-choice cases.

    Each outgoing edge forks a *copy* of the canonical GameSession. The input
    content and project never change. A report is not proof of tactical replay,
    external scene triggers or Player executable packaging.
    """
    require(type(max_states) is int and 1 <= max_states <= 4096
            and type(max_choices) is int and 1 <= max_choices <= 32,
            'Invalid R42 reachability budget')
    require(type(min_reused_scenes) is int and 0 <= min_reused_scenes <= 16,
            'Invalid reusable-scene coverage threshold')
    require(type(expected_endings) in (list, tuple)
            and bool(expected_endings)
            and all(type(v) is str and v for v in expected_endings)
            and len(set(expected_endings)) == len(expected_endings),
            'Invalid expected R42 ending identities')
    require(type(strict) is bool, 'Invalid strict QA option')
    project.validate(content)
    require(project.story.get('schema_version') == 2,
            'R42 reachability requires a v2 story')
    require(project.campaign(campaign_id) is not None,
            'Unknown R42 campaign')
    from sporebound.narrative_state_r42 import state_key
    ending = next((row for row in project.story.get('state', [])
                   if row['id'] == 'ending' and row['scope'] == 'campaign'
                   and row['owner'] == campaign_id), None)
    require(ending is not None and ending['kind'] == 'text',
            'R42 QA requires the canonical campaign ending declaration')
    ending_key = state_key(ending)

    session = GameSession.new(content, project, campaign_id, seed=17)
    pending = deque([(session, ())])
    scenes = {scene['id']: scene for scene in project.story['scenes']}
    authored = {(scene['id'], choice['id'])
                for scene in project.story['scenes']
                for choice in scene['choices']}
    seen_scenes, seen_choices = set(), set()
    samples = {}
    witnesses = {}
    unclassified = []
    explored = 0
    transitions = 0
    while pending:
        require(explored < max_states, 'R42 QA path exploration exceeds state budget')
        game, path = pending.popleft()
        explored += 1
        scene = game.active_scene()
        if scene is None:
            current_ending = game.progress.story_flags[ending_key]
            terminal = {'route': list(path), 'ending': current_ending,
                        'gold': game.progress.gold,
                        'unlocked': sorted(game.progress.unlocked),
                        'choice_count': len(game.progress.story_history),
                        'flags': deepcopy(game.progress.story_flags)}
            if current_ending in expected_endings:
                witnesses.setdefault(current_ending, terminal)
            else:
                unclassified.append(terminal)
            continue
        scene_id = scene['id']
        seen_scenes.add(scene_id)
        # Advancing a dialogue is a real, persisted GameSession operation.
        while not game.narrative_line()['complete']:
            game.advance_narrative_line()
        available = game.available_choices()
        present = {choice['id'] for choice in available}
        if scene_id not in samples:
            samples[scene_id] = {
                'route_to_scene': list(path),
                'flags': deepcopy(game.progress.story_flags),
                'gold': game.progress.gold,
            }
        require(bool(available), 'R42 QA found a scene without an available choice')
        for choice in available:
            seen_choices.add((scene_id, choice['id']))
            require(len(path) < max_choices,
                    'R42 QA path exceeds choice depth budget')
            clone = deepcopy(game)
            clone.choose_story_option(choice['id'])
            transitions += 1
            pending.append((clone, (*path, {'scene': scene_id,
                                           'choice': choice['id']})))
    # Scenes owned by a Battle trigger or an authenticated mission outcome
    # are NOT reachable from the campaign-entry-only search. Keep them separate
    # rather than calling them dead or falsely claiming verified coverage.
    external_roots = {
        *project.story.get('after_mission', {}).values(),
        *project.story.get('during_tactical_event', {}).values(),
        *project.story.get('after_strategic_event', {}).values(),
    }
    external_scenes = set()
    pending_external = list(external_roots)
    while pending_external:
        sid = pending_external.pop()
        if sid in external_scenes:
            continue
        external_scenes.add(sid)
        pending_external.extend(
            choice['next_scene'] for choice in scenes[sid]['choices']
            if 'next_scene' in choice)
    entry_unreached = set(scenes) - seen_scenes
    dead_scenes = sorted(entry_unreached - external_scenes)
    deferred_scenes = sorted(entry_unreached & external_scenes)
    dead_choices = []
    for scene_id, choice_id in sorted(authored - seen_choices):
        if scene_id in external_scenes:
            continue  # Requires an independently evidenced trigger or victory.
        choice = next(c for c in scenes[scene_id]['choices']
                      if c['id'] == choice_id)
        dead_choices.append({
            'scene': scene_id,
            'choice': choice_id,
            'reason': 'unreachable_scene' if scene_id in dead_scenes
                      else 'condition_never_satisfied',
            'condition': deepcopy(choice.get('when')),
            'counterexample': deepcopy(samples.get(scene_id)),
        })
    # Count *dynamically traversed* fan-in, not just authored edges that
    # could be permanently disabled by impossible conditions.
    incoming = {scene_id: set() for scene_id in scenes}
    for origin, choice_id in seen_choices:
        choice = next(c for c in scenes[origin]['choices']
                      if c['id'] == choice_id)
        target = choice.get('next_scene')
        if target:
            incoming[target].add(origin)
    reused_scenes = sorted(scene_id for scene_id, sources in incoming.items()
                           if len(sources) >= 2)
    missing_reuse = max(0, min_reused_scenes - len(reused_scenes))
    missing_endings = sorted(set(expected_endings) - set(witnesses))
    passed = (not dead_scenes and not dead_choices and not missing_endings
              and not unclassified and not missing_reuse)
    report = {
        'campaign': campaign_id, 'scope': 'campaign_entry_narrative_only',
        'explored_states': explored, 'choice_transitions': transitions,
        'reachable_scenes': sorted(seen_scenes),
        'reachable_choices': [{'scene': s, 'choice': c}
                              for s, c in sorted(seen_choices)],
        'dead_scenes': dead_scenes, 'dead_choices': dead_choices,
        'external_trigger_scenes_unverified': deferred_scenes,
        'external_trigger_roots': sorted(external_roots),
        'missing_endings': missing_endings,
        'reused_scenes': reused_scenes,
        'required_reused_scenes': min_reused_scenes,
        'missing_reused_scenes': missing_reuse,
        'endings': {name: deepcopy(witnesses[name])
                    for name in sorted(witnesses)},
        'unclassified_terminals': unclassified,
        'passed': passed, 'tactical_replay_verified': False,
        'player_export_verified': False,
    }
    require(not strict or passed,
            'R42 unreachable narrative path(s): ' + json.dumps({
                'dead_scenes': dead_scenes,
                'dead_choices': [row['scene'] + '/' + row['choice']
                                 for row in dead_choices],
                'missing_endings': missing_endings,
                'missing_reused_scenes': missing_reuse,
                'unclassified_terminals': len(unclassified),
            }, ensure_ascii=False, sort_keys=True))
    return report


def captain_slice_audit():
    """Executable reference report; safe for CI and no user-file writes."""
    from .r42_captain_slice import CAMPAIGN, ENDINGS, make_captain_slice
    content, project = make_captain_slice()
    return audit_narrative(content, project, CAMPAIGN,
                           expected_endings=ENDINGS, min_reused_scenes=2,
                           strict=True)


if __name__ == '__main__':
    print(json.dumps(captain_slice_audit(), ensure_ascii=False, indent=2))

"""Read-only previews of tactical dialogue branches, through canonical rules.

The authoring probe explicitly stages a Battle, so it NEVER claims verified
GameSession replay. Each branch forks the same disposable state and performs a
real Battle.execute(story_effects), not a forged fired-event ID.
"""
from copy import deepcopy

from . import event_context
from .game_session import GameSession
from .model import Content, RuleError, require
from .tactical_rpg3 import authored_rules_for_document


def preview_choice_routes(data, project, mission_id, event_id, *,
                          tick=0, scenario='satisfied'):
    """Preview all currently available choices, including OR-rejoins.

    Every branch starts from the same isolated post-trigger snapshot, so it
    cannot inherit consequences from any competing, mutually exclusive choice.
    """
    rules = authored_rules_for_document(data)
    content = Content.from_dict(data, rules=rules)
    project.validate(content)
    link = mission_id + '/' + event_id
    scene_id = project.story.get('during_tactical_event', {}).get(link)
    require(bool(scene_id), 'Link this event to a tactical narrative scene first')
    seed_session = GameSession.new(content, project, project.campaigns[0]['id'],
                                   rules=rules)
    progress = deepcopy(seed_session.progress)
    progress.story_pending = scene_id
    choices = seed_session.story.choices(progress)
    require(bool(choices), 'No available narrative choice for this scene')
    preview = event_context.preview_event_chain(
        data, mission_id, event_id, project=project,
        tick=tick, scenario=scenario, include_scene=True)
    report = {
        'mission_id': mission_id, 'event_id': event_id,
        'scene_id': scene_id,
        'source_fired': event_id in preview['fired_ids'],
        'source_events': preview['fired_ids'],
        'scenario_notes': preview['scenario_notes'],
        'routes': [], 'isolated': True,
        'replay_verified': None,
    }
    # Do not consume a choice when the source event itself was not emitted.
    if not report['source_fired']:
        report['blocked_reason'] = (
            'Source event not fired: no tactical dialogue can be selected')
        return report

    starting_battle = preview['scene_after']
    actions = {row['id']: row for row in
               next(m for m in data['missions'] if m['id'] == mission_id)['triggers']}
    for choice in choices:
        battle = deepcopy(starting_battle)
        before_fired = set(battle.fired)
        hazard_cells = (
            {tuple(a['pos']) for row in actions.values()
             for a in row['actions'] if a['kind'] == 'hazard'} |
            {tuple(effect['pos'])
             for effect in choice.get('tactical_effects', [])
             if effect['kind'] == 'hazard'}
        )
        before = event_context._snapshot(battle, hazard_cells)
        error = ''
        flags = {}
        try:
            result_progress = seed_session.story.choose(progress, choice['id'])
            flags = {key: deepcopy(value)
                     for key, value in result_progress.story_flags.items()
                     if progress.story_flags.get(key) != value}
            battle.execute({
                'kind': 'story_effects', 'scene': scene_id,
                'choice': choice['id'],
                'effects': deepcopy(choice.get('tactical_effects', [])),
            })
        except (RuleError, ValueError, KeyError, IndexError) as exc:
            error = str(exc)
        after = event_context._snapshot(battle, hazard_cells)
        newly_fired = [eid for eid in battle.fired if eid not in before_fired]
        clips, scenes = [], []
        if not error:
            from .cinematics import triggered_tactical_cinematics
            triggered, _ = triggered_tactical_cinematics(project, battle)
            clips = [c['id'] for c in triggered]
            links = project.story.get('during_tactical_event', {})
            scenes = [links[mission_id + '/' + eid] for eid in newly_fired
                      if mission_id + '/' + eid in links]
        waiting = []
        for row in actions.values():
            if row['id'] in battle.fired:
                continue
            guard = row.get('after_choice')
            if guard and guard['scene'] == scene_id:
                waiting.append({
                    'event_id': row['id'],
                    'expected_choice': guard['choice'],
                    'selected_choice': choice['id'],
                })
        report['routes'].append({
            'choice_id': choice['id'], 'label': choice['label'],
            'next_scene': choice.get('next_scene', ''),
            'fired_ids': newly_fired,
            'changes': event_context._state_changes(before, after),
            'story_flags': flags, 'cinematic_ids': clips,
            'narrative_scene_ids': scenes,
            'excluded': waiting,
            'error': error,
        })
    return report


def format_choice_routes(report):
    lines = [
        'EMBRANCHEMENTS TACTIQUES — choix du StoryBook / Battle réel',
        'Scène : ' + report['scene_id'],
        'Source : ' + report['event_id'],
        'Replay : NON ATTESTÉ (préparation contextuelle de Battle)',
    ]
    lines.extend('Préparation : ' + line for line in report['scenario_notes'])
    if report.get('blocked_reason'):
        lines.append('BLOQUÉ : ' + report['blocked_reason'])
        return lines
    for route in report['routes']:
        lines.append('CHOIX ' + route['choice_id'] + ' — ' + route['label'])
        lines.append('  Événements : ' +
                     (', '.join(route['fired_ids']) or 'aucun'))
        if route['next_scene']:
            lines.append('  Scène suivante : ' + route['next_scene'])
        lines.extend('  Conséquence : ' + line for line in route['changes'])
        if route['story_flags']:
            lines.append('  Drapeaux : ' + repr(route['story_flags']))
        if route['cinematic_ids']:
            lines.append('  Cinématiques : ' + ', '.join(route['cinematic_ids']))
        if route['narrative_scene_ids']:
            lines.append('  Dialogues déclenchés : ' +
                         ', '.join(route['narrative_scene_ids']))
        if route['excluded']:
            lines.append('  Branches non retenues : ' +
                         ', '.join(item['event_id']
                                   for item in route['excluded']))
        if route['error']:
            lines.append('  ERREUR : ' + route['error'])
    return lines

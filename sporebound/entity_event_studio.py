"""Entity & Event Studio 2.0: one contextual, validated siege authoring flow.

Reuses Content mission objects, event_composer, and GameProject cinematics.
No parallel event schema, evaluator, runtime interpreter, or Tk dependency.
"""
from copy import deepcopy

from .authoring import _cell, _identifier, _mission, add_object
from .cinematics import (cinematic_template, event_template,
                         tactical_event_target, triggered_tactical_cinematics)
from .event_composer import action, condition, save_event
from .event_graph import extend_condition
from .event_context import preview_event
from .game_project import GameProject
from .story_authoring import set_tactical_scene
from .model import Content, require
from .tactical_rpg3 import authored_rules_for_document


def gate_context(data, mission_id, door_id):
    """Resolve a selected door and its linked levers from current mission data."""
    mission = _mission(data, mission_id)
    require(mission is not None, 'Mission introuvable')
    door = next((row for row in mission.get('objects', ())
                 if row['id'] == door_id and row['kind'] == 'door'), None)
    require(door is not None, 'Sélectionner une porte de la mission')
    levers = tuple(row for row in mission['objects']
                   if row['kind'] == 'switch' and row.get('link') == door_id)
    return deepcopy(door), deepcopy(levers)


def author_gate_sequence(data, project, mission_id, *, door_id, lever_id,
                         lever_cell, event_id, danger_cell, danger=4,
                         dialogue='La porte est ouverte !', cinematic_id='',
                         min_tick=None, extra_actions=(), scene_id=''):
    """Prepare BOTH documents atomically, without mutating either input.

    An existing linked lever is reused; otherwise it is placed through the
    current validated object authoring API. The single-use interaction event
    affects a real tactical tile and cues a Player cinematic, never a fake
    editor-only outcome. Callers commit both results in one Studio history step.
    """
    require(isinstance(project, GameProject), 'Ouvrir un projet de jeu')
    _identifier(lever_id, 'Lever id')
    _identifier(event_id, 'Event id')
    clip_id = cinematic_id or ('cin_' + event_id)
    _identifier(clip_id, 'Cinematic id')
    require(type(danger) is int and 1 <= danger <= 10000,
            'Danger attendu entre 1 et 10000')
    require(isinstance(dialogue, str) and 0 < len(dialogue.strip()) <= 1600,
            'Un dialogue narratif est requis')
    door, _ = gate_context(data, mission_id, door_id)
    require(not door.get('open', False),
            'La porte doit être initialement fermée')
    mission = _mission(data, mission_id)
    lever_cell = _cell(mission, lever_cell)
    danger_cell = _cell(mission, danger_cell)
    require(lever_cell != door['pos'], 'Ne pas placer le levier sur la porte')
    require(not any(event['id'] == event_id
                    for event in mission.get('triggers', ())),
            'Un événement porte déjà cet identifiant')
    existing = next((obj for obj in mission['objects']
                     if obj['id'] == lever_id), None)
    if existing:
        require(existing['kind'] == 'switch' and existing.get('link') == door_id,
                'Ce levier doit cibler la porte sélectionnée')
        require(existing['pos'] == lever_cell,
                'Le levier existant est situé sur une autre case')
        staged = deepcopy(data)
    else:
        require(not any(obj['pos'] == lever_cell for obj in mission['objects']),
                'La case du levier contient déjà un objet')
        require(not any(unit['pos'] == lever_cell for unit in mission['units']),
                'La case du levier contient une unité')
        staged = add_object(data, mission_id, lever_id, 'switch',
                            lever_cell, link=door_id)
    require(isinstance(extra_actions, (list, tuple)) and
            len(extra_actions) <= 12, 'Au maximum 12 effets supplémentaires')
    staged = save_event(
        staged, mission_id, event_id,
        condition('interact', object_id=lever_id),
        [action('message', text=dialogue.strip()),
         action('hazard', pos=danger_cell, amount=danger),
         *deepcopy(list(extra_actions))])
    if min_tick is not None:
        require(type(min_tick) is int and 0 <= min_tick <= 100000,
                'Tick minimum invalide')
        staged = extend_condition(
            staged, mission_id, event_id, condition('tick', tick=min_tick))

    clip = cinematic_template(
        clip_id, 'Siège · ' + event_id,
        'tactical_event', tactical_event_target(mission_id, event_id))
    clip['events'] = [
        event_template('background', 'gate_background', 0, 8000),
        {**event_template('dialogue', 'gate_dialogue', 800, 5500),
         'speaker': 'Garde', 'text': dialogue.strip()},
    ]
    project_data = project.to_dict()
    require(not any(row['id'] == clip_id
                    for row in project_data.get('cinematics', ())),
            'Une cinématique porte déjà cet identifiant')
    project_data.setdefault('cinematics', []).append(clip)
    content = Content.from_dict(
        staged, rules=authored_rules_for_document(staged))
    updated_project = GameProject.from_dict(project_data, content)
    if scene_id:
        # Existing Story Studio bridge validates the real trigger and scene.
        updated_project = set_tactical_scene(
            updated_project, content, mission_id, event_id, scene_id)
    return staged, updated_project


def probe_gate_sequence(data, project, mission_id, event_id, door_id):
    """Inspect real engine transitions and the Player's cinematic queue."""
    gate_context(data, mission_id, door_id)
    report = preview_event(data, mission_id, event_id,
                           scenario='satisfied', include_scene=True)
    before, after = report['scene_before'], report['scene_after']
    old_door = next(obj for obj in before.mission.objects
                    if obj['id'] == door_id)
    new_door = next(obj for obj in after.mission.objects
                    if obj['id'] == door_id)
    gate_cell = tuple(new_door['pos'])
    clips, _ = triggered_tactical_cinematics(project, after)
    tactical_effect = any('danger' in row for row in report['changes'])
    gate_opened = (not old_door.get('open', False)
                   and new_door.get('open', False)
                   and before.board.tile(gate_cell).blocked
                   and not after.board.tile(gate_cell).blocked)
    return {
        'event': report,
        'gate_opened': gate_opened,
        'tactical_effect': tactical_effect,
        'cinematic_ids': [clip['id'] for clip in clips],
        'narrative_scene_id': project.story.get(
            'during_tactical_event', {}).get(mission_id + '/' + event_id, ''),
        'gate_passable': not after.board.tile(gate_cell).blocked,
        'gate_scenario_ok': (
            report['outcome'] == 'applied' and gate_opened
            and tactical_effect and bool(clips)),
    }

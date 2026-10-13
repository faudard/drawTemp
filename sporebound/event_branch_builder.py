"""Coordinated map-to-narrative authoring using canonical StoryBook and triggers.

Creates one self-contained fork of a tactical event into 2..4 narrative
choices, per-choice tactical consequences, and optional OR convergence.
Return BOTH validated artifacts; the Studio commits them as one global history
transaction. No runtime, renderer or parallel event graph is introduced.
"""
from copy import deepcopy

from .authoring import _identifier, _mission
from .event_composer import action as typed_action, condition, save_event
from .game_project import GameProject
from .model import Content, require
from .narrative import _id
from .tactical_rpg3 import authored_rules_for_document


def author_choice_fork(data, project, mission_id, *,
                       origin_event_id, origin_cell, scene_id,
                       title, text, branches, reunion_event_id='',
                       reunion_message='', speaker=''):
    """Atomically author an event-linked choice fork from a map selection.

    Each branch is {'id', 'label', 'event_id', 'kind', 'text', 'amount'}.
    An optional 'scene_text' is used for its follow-up narrative scene.
    Action kinds are intentionally limited to safe, existing common
    message/hazard actions; advanced actions are edited later in Event Graph.
    """
    require(isinstance(project, GameProject), 'Ouvrir un projet de jeu')
    require(isinstance(branches, list) and 2 <= len(branches) <= 4,
            'Créer de deux à quatre choix')
    _identifier(origin_event_id, 'Origin tactical event id')
    _id(scene_id, 'Scene id')
    require(isinstance(title, str) and bool(title.strip()) and
            isinstance(text, str) and bool(text.strip()) and
            isinstance(speaker, str), 'Indiquer un titre et un dialogue')
    require(isinstance(origin_cell, (list, tuple)) and len(origin_cell) == 2
            and all(type(n) is int for n in origin_cell),
            'Sélectionner une case de la carte')
    mission = _mission(data, mission_id)
    require(mission is not None, 'Unknown mission')
    board = mission['board']
    require(0 <= origin_cell[0] < board['width'] and
            0 <= origin_cell[1] < board['height'],
            'Case choisie hors de la carte')
    ids = [origin_event_id] + [b.get('event_id') for b in branches]
    if reunion_event_id:
        ids.append(reunion_event_id)
        _identifier(reunion_event_id, 'Reunion event id')
    require(len(ids) == len(set(ids)), 'Event ids must be unique')
    for event_id in ids:
        _identifier(event_id, 'Tactical event id')
    require(isinstance(reunion_message, str), 'Invalid reunion message')
    choice_ids = []
    for item in branches:
        require(isinstance(item, dict) and
                {'id', 'label', 'event_id', 'kind', 'text', 'amount'} <= set(item) <=
                {'id', 'label', 'event_id', 'kind', 'text', 'amount', 'scene_text'},
                'Invalid choice branch definition')
        _id(item['id'], 'Choice id')
        require(isinstance(item['label'], str) and bool(item['label'].strip()),
                'Choice label is required')
        require(item['kind'] in ('message', 'hazard'),
                'Use the existing message or hazard tactical action')
        require(isinstance(item['text'], str) and
                type(item['amount']) is int, 'Invalid branch effects')
        choice_ids.append(item['id'])
    require(len(set(choice_ids)) == len(choice_ids),
            'Duplicate narrative choice id')

    # Plan every scene ID before editing either artifact.
    followups = [scene_id + '_' + choice_id for choice_id in choice_ids]
    join_scene = scene_id + '_reunion' if reunion_event_id else ''
    scene_ids = [scene_id, *followups, *([join_scene] if join_scene else [])]
    for sid in scene_ids:
        _id(sid, 'Narrative scene id')
    require(len(set(scene_ids)) == len(scene_ids), 'Narrative scene IDs overlap')
    project_raw = deepcopy(project.to_dict())
    story = project_raw.setdefault(
        'story', {'scenes': [], 'entry_scenes': {}, 'after_mission': {}})
    known_scenes = {row['id'] for row in story.get('scenes', [])}
    require(not known_scenes.intersection(scene_ids),
            'One of the generated narrative scene IDs already exists')
    existing = {row['id'] for row in mission.get('triggers', [])}
    require(not any(b['event_id'] in existing for b in branches) and
            (not reunion_event_id or reunion_event_id not in existing),
            'One of the branch event IDs already exists')
    if origin_event_id in existing:
        require(origin_event_id in {
            row['id'] for row in mission['triggers']
        }, 'Unknown source event')
    mapping = story.setdefault('during_tactical_event', {})
    origin_ref = mission_id + '/' + origin_event_id
    require(not mapping.get(origin_ref),
            'The source event already has a linked narrative scene')

    updated = deepcopy(data)
    if origin_event_id not in existing:
        updated = save_event(
            updated, mission_id, origin_event_id,
            condition('enter', pos=list(origin_cell)),
            [typed_action('message', text=title)])
    elif any(row['id'] == origin_event_id and row.get('after_choice')
             for row in mission['triggers']):
        from .model import RuleError
        raise RuleError('Source must not itself await a narrative choice')

    root_choices = []
    branch_ids = []
    for item, followup in zip(branches, followups):
        kind = item['kind']
        effect = (typed_action('hazard', pos=list(origin_cell),
                               amount=item['amount'])
                  if kind == 'hazard'
                  else typed_action('message', text=item['text']))
        updated = save_event(
            updated, mission_id, item['event_id'],
            {'condition': 'tick', 'value': 0,
             'after': [origin_event_id],
             'after_choice': {'scene': scene_id, 'choice': item['id']}},
            [effect])
        branch_ids.append(item['event_id'])
        root_choices.append({
            'id': item['id'], 'label': item['label'],
            'effects': [], 'next_scene': followup,
        })
        line = item.get('scene_text') or item['text'] or item['label']
        story.setdefault('scenes', []).append({
            'id': followup, 'title': item['label'],
            'speaker': speaker, 'text': line,
            'choices': [{
                'id': 'continue', 'label': 'Continuer',
                **({'next_scene': join_scene} if join_scene else {}),
            }],
        })
    story['scenes'].append({
        'id': scene_id, 'title': title, 'speaker': speaker,
        'text': text, 'choices': root_choices,
    })
    if reunion_event_id:
        updated = save_event(
            updated, mission_id, reunion_event_id,
            {'condition': 'tick', 'value': 0,
             'after_any': branch_ids},
            [typed_action('message',
                          text=reunion_message or 'Les chemins se rejoignent')])
        story['scenes'].append({
            'id': join_scene, 'title': 'Retrouvailles',
            'speaker': speaker,
            'text': reunion_message or 'Les chemins se rejoignent.',
            'choices': [{'id': 'continue', 'label': 'Continuer'}],
        })
    mapping[origin_ref] = scene_id

    rules = authored_rules_for_document(updated)
    content = Content.from_dict(updated, rules=rules)
    new_project = GameProject.from_dict(project_raw, content)
    return content.to_dict(), new_project


def branch_recipe(*, first_id, first_label, first_event,
                  second_id, second_label, second_event,
                  first_action='hazard', first_text='Assaut',
                  first_amount=6, second_action='message',
                  second_text='Négociation', second_amount=0):
    """Small presentation helper; author_choice_fork is the sole mutation."""
    return [
        {'id': first_id, 'label': first_label, 'event_id': first_event,
         'kind': first_action, 'text': first_text,
         'amount': first_amount},
        {'id': second_id, 'label': second_label, 'event_id': second_event,
         'kind': second_action, 'text': second_text,
         'amount': second_amount},
    ]

"""Transactional narrative authoring for GameProject.story.

Every operation returns a fully validated new project dictionary; a failing
operation never mutates the active project in the UI.
"""
from copy import deepcopy

from .game_project import GameProject
from .model import require
from .narrative import _id


def _edit(project, content, change):
    data = deepcopy(project.to_dict() if isinstance(project, GameProject) else project)
    data.setdefault('story', {'scenes': [], 'entry_scenes': {}, 'after_mission': {}})
    change(data['story'])
    return GameProject.from_dict(data, content)


def _scene(story, scene_id):
    scene = next((row for row in story['scenes'] if row['id'] == scene_id), None)
    require(scene is not None, 'Unknown narrative scene')
    return scene


def create_scene(project, content, scene_id, title, text, speaker=''):
    _id(scene_id, 'Scene id')
    def change(story):
        require(not any(row['id'] == scene_id for row in story['scenes']),
                'Duplicate narrative scene')
        story['scenes'].append({
            'id': scene_id, 'title': title, 'speaker': speaker, 'text': text,
            'choices': [{'id': 'continue', 'label': 'Continuer', 'effects': []}],
        })
    return _edit(project, content, change)


def update_scene(project, content, scene_id, *, title, speaker, text):
    def change(story):
        _scene(story, scene_id).update(title=title, speaker=speaker, text=text)
    return _edit(project, content, change)


def delete_scene(project, content, scene_id):
    def change(story):
        _scene(story, scene_id)
        story['scenes'] = [row for row in story['scenes'] if row['id'] != scene_id]
        require(bool(story['scenes']), 'Cannot delete the last scene')
        # Existing references are rejected by GameProject validation.
    return _edit(project, content, change)


def add_choice(project, content, scene_id, choice_id, label, *,
               when=None, next_scene='', effects=None):
    _id(choice_id, 'Choice id')
    def change(story):
        choices = _scene(story, scene_id)['choices']
        require(not any(row['id'] == choice_id for row in choices),
                'Duplicate choice id')
        new = {'id': choice_id, 'label': label, 'effects': deepcopy(effects or [])}
        if when is not None:
            new['when'] = deepcopy(when)
        if next_scene:
            new['next_scene'] = next_scene
        choices.append(new)
    return _edit(project, content, change)


def update_choice(project, content, scene_id, choice_id, *, label=None,
                  when=None, next_scene=None, effects=None, clear_condition=False):
    def change(story):
        choices = _scene(story, scene_id)['choices']
        choice = next((row for row in choices if row['id'] == choice_id), None)
        require(choice is not None, 'Unknown narrative choice')
        if label is not None:
            choice['label'] = label
        if clear_condition:
            choice.pop('when', None)
        elif when is not None:
            choice['when'] = deepcopy(when)
        if next_scene is not None:
            if next_scene:
                choice['next_scene'] = next_scene
            else:
                choice.pop('next_scene', None)
        if effects is not None:
            choice['effects'] = deepcopy(effects)
    return _edit(project, content, change)


def remove_choice(project, content, scene_id, choice_id):
    def change(story):
        choices = _scene(story, scene_id)['choices']
        require(any(row['id'] == choice_id for row in choices), 'Unknown narrative choice')
        _scene(story, scene_id)['choices'] = [
            row for row in choices if row['id'] != choice_id]
    return _edit(project, content, change)


def add_effect(project, content, scene_id, choice_id, effect):
    def change(story):
        choice = next((c for c in _scene(story, scene_id)['choices']
                       if c['id'] == choice_id), None)
        require(choice is not None, 'Unknown narrative choice')
        choice.setdefault('effects', []).append(deepcopy(effect))
    return _edit(project, content, change)


def set_scene_entry(project, content, campaign_id, scene_id=''):
    def change(story):
        mapping = story.setdefault('entry_scenes', {})
        if scene_id:
            mapping[campaign_id] = scene_id
        else:
            mapping.pop(campaign_id, None)
    return _edit(project, content, change)


def set_mission_outcome(project, content, mission_id, scene_id=''):
    def change(story):
        mapping = story.setdefault('after_mission', {})
        if scene_id:
            mapping[mission_id] = scene_id
        else:
            mapping.pop(mission_id, None)
    return _edit(project, content, change)

"""3.6: typed, atomic Story Graph <-> Event Graph link commands.

No alternative graph schema. The UI-only ports refer exclusively to
GameProject.story.scenes, during_tactical_event and Mission.triggers.
"""
from copy import deepcopy

from . import event_graph, story_authoring
from .game_project import GameProject
from .model import Content, require
from .tactical_rpg3 import authored_rules_for_document


KINDS = ('scene', 'event')


def connect_visual_branch(data, project, mission_id, *, source_kind, source_id,
                          target_kind, target_id, choice_id='',
                          event_join='all'):
    """Return a fully validated (Content dict, GameProject) pair.

    source scene + choice  -> scene: StoryBook.next_scene
    source scene + choice  -> event: Mission.after_choice
    source event           -> scene: StoryBook.during_tactical_event
    source event           -> event: Mission.after or after_any

    All mutations are copy-on-write, and the project is validated against the
    NEW content, not the previous content. Failed links never touch the UI.
    """
    require(source_kind in KINDS and target_kind in KINDS,
            'Unknown visual graph endpoint kind')
    require(isinstance(source_id, str) and bool(source_id)
            and isinstance(target_id, str) and bool(target_id),
            'Select two existing graph endpoints')
    require(event_join in ('all', 'any'), 'Unknown tactical link mode')
    require(isinstance(project, GameProject), 'Open a GameProject')
    require(mission_id in {m['id'] for m in data['missions']}, 'Unknown mission')
    if source_kind == 'scene':
        scene = next((s for s in project.story.get('scenes', [])
                      if s['id'] == source_id), None)
        require(scene is not None, 'Unknown source narrative scene')
        require(any(choice['id'] == choice_id for choice in scene['choices']),
                'Select a valid outgoing narrative choice')
    else:
        require(not choice_id, 'Tactical event links have no source choice')
    require(source_kind != target_kind or source_id != target_id,
            'Cannot connect a graph node to itself')

    updated_data = deepcopy(data)
    updated_project = project
    if source_kind == 'scene' and target_kind == 'scene':
        updated_project = story_authoring.link_choice(
            project, Content.from_dict(updated_data,
                                       rules=authored_rules_for_document(updated_data)),
            source_id, choice_id, target_id)
    elif source_kind == 'scene' and target_kind == 'event':
        updated_data = event_graph.bind_choice(
            updated_data, mission_id, target_id, source_id, choice_id)
    elif source_kind == 'event' and target_kind == 'scene':
        updated_project = story_authoring.set_tactical_scene(
            project, Content.from_dict(updated_data,
                                       rules=authored_rules_for_document(updated_data)),
            mission_id, source_id, target_id)
    else:
        operation = (event_graph.link_event if event_join == 'all'
                     else event_graph.link_alternative)
        updated_data = operation(updated_data, mission_id, target_id, source_id)

    rules = authored_rules_for_document(updated_data)
    valid_content = Content.from_dict(updated_data, rules=rules)
    valid_project = GameProject.from_dict(updated_project.to_dict(), valid_content)
    return valid_content.to_dict(), valid_project


def visual_target_palette(data, project, mission_id, visible_scene_ids=(),
                          *, max_scenes=30, max_events=60):
    """Display-target projection for one mission, with explicit truncation.

    Detached scenes are shown once; linked occurrence scenes stay in the Story
    Graph. Event references stay mission-local and can never cross missions.
    """
    require(type(max_scenes) is int and 1 <= max_scenes <= 200,
            'Invalid scene palette budget')
    require(type(max_events) is int and 1 <= max_events <= 200,
            'Invalid event palette budget')
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown palette mission')
    visible = set(visible_scene_ids)
    scenes = sorted((s for s in project.story.get('scenes', [])
                     if s['id'] not in visible), key=lambda s: s['id'])
    events = mission.get('triggers', [])
    return {
        'scenes': [{'kind': 'scene', 'id': s['id'], 'title': s['title']}
                   for s in scenes[:max_scenes]],
        'events': [{'kind': 'event', 'id': e['id'],
                    'title': event_graph.condition_summary(e)}
                   for e in events[:max_events]],
        'scenes_truncated': len(scenes) > max_scenes,
        'events_truncated': len(events) > max_events,
    }

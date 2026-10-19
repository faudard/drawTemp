"""R42.A opt-in Narrative Studio 2.0 authoring contract.

GameProject.story remains the sole authored dialogue/choice graph. R9's
validate_story / StoryBook remain the sole evaluators for conditions and
effects. The additional schema annotates the *same* scenes with stable,
multi-speaker line identities and named, reusable entry points.

Version 2 is explicit; legacy stories are never migrated on load. For now the
Player continues presenting the legacy first line. R42.B must add multi-line
playback and UI before the user-facing gate can be considered complete.
"""
from __future__ import annotations

from copy import deepcopy

from .model import require
from .narrative import _id, validate_story

SCHEMA_VERSION = 2
MAX_SCENES = 512
MAX_LINES_PER_SCENE = 32
MAX_TOTAL_LINES = 4096
MAX_SUBGRAPHS = 64
MAX_PATH_EDGES = 32


def _legacy_projection(story):
    """Project v2 onto R9's executable schema, without changing semantics."""
    allowed = {'schema_version', 'subgraphs', 'state', 'scenes', 'entry_scenes',
               'after_mission', 'after_strategic_event', 'during_tactical_event'}
    require(type(story) is dict and set(story) <= allowed,
            'Unknown Narrative v2 field')
    require(type(story.get('schema_version')) is int
            and story['schema_version'] == SCHEMA_VERSION,
            'Unsupported Narrative v2 schema version')
    result = {key: deepcopy(value) for key, value in story.items()
              if key not in ('schema_version', 'subgraphs', 'state', 'scenes')}
    result['scenes'] = []
    for scene in story.get('scenes', []):
        require(type(scene) is dict and 'lines' in scene,
                'Narrative v2 scene requires lines')
        result['scenes'].append({key: deepcopy(value)
                                 for key, value in scene.items() if key != 'lines'})
    return result


def validate_story_v2(story, content, campaigns):
    """Validate v2 *and* the production R9 conditions, effects and links.

    The v2 contract never defines a new predicate/effect interpreter. Subgraph
    labels are named references to existing canonical scene IDs, not scripts,
    duplicated graph content or implicit runtime calls.
    """
    legacy = _legacy_projection(story)
    validate_story(legacy, content, campaigns)
    scenes = story['scenes']
    require(len(scenes) <= MAX_SCENES, 'Narrative v2 scene budget exceeded')
    ids = {scene['id'] for scene in scenes}
    total_lines = 0
    for scene in scenes:
        require(set(scene) == {'id', 'title', 'speaker', 'text', 'choices', 'lines'},
                'Narrative v2 scene has unsupported fields')
        lines = scene['lines']
        require(type(lines) is list and 1 <= len(lines) <= MAX_LINES_PER_SCENE,
                'Narrative v2 requires 1..32 dialogue lines per scene')
        local_ids = set()
        for line in lines:
            require(type(line) is dict and set(line) == {'id', 'speaker', 'text'},
                    'Invalid Narrative v2 dialogue line')
            _id(line['id'], 'Dialogue line id')
            require(line['id'] not in local_ids, 'Duplicate dialogue line id')
            local_ids.add(line['id'])
            require(type(line['speaker']) is str and len(line['speaker']) <= 120,
                    'Invalid dialogue speaker')
            require(type(line['text']) is str and
                    0 < len(line['text'].strip()) <= 5000,
                    'Invalid dialogue text')
        # R9 Player still renders speaker/text. Fail closed against drift until
        # R42.B supports multi-line playback; no other truth is copied to disk.
        require((scene['speaker'], scene['text']) ==
                (lines[0]['speaker'], lines[0]['text']),
                'Narrative v2 first line must match legacy Player projection')
        total_lines += len(lines)
    require(total_lines <= MAX_TOTAL_LINES, 'Narrative v2 line budget exceeded')

    entries = story.get('subgraphs', [])
    require(type(entries) is list and len(entries) <= MAX_SUBGRAPHS,
            'Invalid Narrative v2 subgraphs')
    names = set()
    for item in entries:
        require(type(item) is dict and set(item) == {'id', 'entry_scene'},
                'Subgraph needs id and entry_scene')
        _id(item['id'], 'Subgraph id')
        require(item['id'] not in names, 'Duplicate subgraph id')
        names.add(item['id'])
        require(type(item['entry_scene']) is str and item['entry_scene'] in ids,
                'Subgraph entry must reference an authored scene')

    # R42.A2 uses ordinary R9 flags/conditions/effects, with typed validation.
    from .narrative_state_r42 import validate_state_catalog
    validate_state_catalog(story, content, campaigns)

    # R9 validates acyclicity. Enforce a separate v2 bound on longest path,
    # including reused branches, to avoid unbounded authoring/Player navigation.
    edges = {scene['id']: [c['next_scene'] for c in scene['choices']
                           if 'next_scene' in c] for scene in scenes}
    longest = {}
    def depth(node):
        if node not in longest:
            longest[node] = 0 if not edges[node] else 1 + max(
                depth(next_id) for next_id in edges[node])
        return longest[node]
    for scene_id in sorted(ids):
        require(depth(scene_id) <= MAX_PATH_EDGES,
                'Narrative v2 path exceeds 32 choices')
    return True


def migrate_story_v1(project, content):
    """Explicit copy-on-write authoring migration (never called at load).

    Existing saves contain the old story digest; they cannot be silently
    rebound to a changed narrative definition. Keep old project+save together
    or create a new game after the explicit authoring migration.
    """
    from .game_project import GameProject
    data = deepcopy(project.to_dict() if isinstance(project, GameProject)
                    else project)
    checked = GameProject.from_dict(data, content)
    raw = checked.story
    require(raw and 'schema_version' not in raw,
            'Migration requires an unversioned legacy story')
    upgraded = deepcopy(raw)
    upgraded['schema_version'] = SCHEMA_VERSION
    upgraded['subgraphs'] = []
    for scene in upgraded['scenes']:
        scene['lines'] = [{'id': 'line_001', 'speaker': scene['speaker'],
                           'text': scene['text']}]
    data['story'] = upgraded
    return GameProject.from_dict(data, content)


def set_dialogue_lines(project, content, scene_id, lines):
    """Return a validated new project; callers apply via AuthoringSession."""
    from .game_project import GameProject
    data = deepcopy(project.to_dict() if isinstance(project, GameProject)
                    else project)
    story = data.get('story', {})
    require(story.get('schema_version') == SCHEMA_VERSION,
            'Dialogue lines require an explicit v2 migration')
    scenes = [s for s in story.get('scenes', []) if s['id'] == scene_id]
    require(len(scenes) == 1, 'Unknown narrative scene')
    require(type(lines) is list and bool(lines) and type(lines[0]) is dict
            and 'speaker' in lines[0] and 'text' in lines[0],
            'Dialogue lines require a first spoken line')
    scene = scenes[0]
    scene['lines'] = deepcopy(lines)
    scene['speaker'], scene['text'] = lines[0]['speaker'], lines[0]['text']
    return GameProject.from_dict(data, content)


def declare_subgraph(project, content, subgraph_id, entry_scene):
    """Name an existing reusable scene, without copying scenes or effects."""
    from .game_project import GameProject
    data = deepcopy(project.to_dict() if isinstance(project, GameProject)
                    else project)
    story = data.get('story', {})
    require(story.get('schema_version') == SCHEMA_VERSION,
            'Subgraphs require Narrative v2')
    story.setdefault('subgraphs', []).append(
        {'id': subgraph_id, 'entry_scene': entry_scene})
    return GameProject.from_dict(data, content)


def line_references(story):
    """Read-only stable identifiers for future localization/inspector tools."""
    require(type(story) is dict and story.get('schema_version') == SCHEMA_VERSION,
            'Line references require Narrative v2')
    return tuple((scene['id'] + '/' + line['id'])
                 for scene in story['scenes'] for line in scene['lines'])

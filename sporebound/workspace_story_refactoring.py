"""R2.7 — validated, two-document renames for story scenes and campaigns.

No hidden substitutions: only typed links in existing Content/GameProject
schemas are rewritten. All other exact references fail closed. Scene and
campaign changes share the existing StudioHistory snapshot/undo contract.
"""
from copy import deepcopy
import json
from pathlib import Path

from .authoring import _identifier
from .game_project import GameProject
from .model import Content, RuleError, require
from .tactical_rpg3 import authored_rules_for_document
from .workspace_refactoring import _mentions


def story_baseline(project, key):
    """Fingerprint a canonical scene or campaign in GameProject."""
    kind, separator, identifier = key.partition(':')
    require(separator and kind in ('scene', 'campaign'),
            'Sélectionner une scène ou une campagne')
    source = project.to_dict() if isinstance(project, GameProject) else project
    rows = (source.get('story', {}).get('scenes', ()) if kind == 'scene'
            else source.get('campaigns', ()))
    row = next((item for item in rows if item['id'] == identifier), None)
    require(row is not None, 'Ressource supprimée ou renommée : ' + key)
    return json.dumps(row, sort_keys=True, ensure_ascii=True)


def _retarget_map_values(mapping, old, new):
    for key, value in tuple(mapping.items()):
        if value == old:
            mapping[key] = new


def plan_story_rename(data, project, key, baseline, new_id, *,
                      project_path=None):
    """Return validated Content and GameProject without mutating either.

    Campaign IDs are also filesystem namespace keys for save slots. Such a
    rename is refused unless the caller provides a project path and the old
    slot directory is absent. Existing saves are NEVER moved/deleted here.
    """
    kind, separator, old = key.partition(':')
    require(separator and kind in ('scene', 'campaign'),
            'Renommage réservé aux scènes et campagnes')
    current = project.to_dict() if isinstance(project, GameProject) else project
    require(story_baseline(current, key) == baseline,
            'Référence obsolète : recharger la ressource')
    _identifier(new_id, 'Nouvel identifiant')
    require(new_id != old, 'Identifiant inchangé')

    candidate = deepcopy(data)
    updated = deepcopy(current)
    rows = (updated.get('story', {}).get('scenes', ()) if kind == 'scene'
            else updated['campaigns'])
    require(not any(row['id'] == new_id for row in rows),
            'Cet identifiant existe déjà')

    if kind == 'scene':
        scene = next(row for row in rows if row['id'] == old)
        scene['id'] = new_id
        story = updated['story']
        for row in rows:
            for choice in row['choices']:
                if choice.get('next_scene') == old:
                    choice['next_scene'] = new_id
        for field in ('entry_scenes', 'after_mission',
                      'after_strategic_event', 'during_tactical_event'):
            _retarget_map_values(story.get(field, {}), old, new_id)
        for event in updated.get('world', {}).get('events', ()):
            if event.get('scene') == old:
                event['scene'] = new_id
        for clip in updated.get('cinematics', ()):
            if (clip['trigger']['kind'] == 'scene'
                    and clip['trigger']['target'] == old):
                clip['trigger']['target'] = new_id
        for mission in candidate['missions']:
            for trigger in mission.get('triggers', ()):
                if (trigger.get('after_choice', {}).get('scene') == old):
                    trigger['after_choice']['scene'] = new_id

    else:
        require(project_path is not None,
                'Chemin du projet requis pour contrôler les sauvegardes')
        path = Path(project_path)
        save_dir = path.with_name(path.stem + '_saves') / old
        require(not save_dir.exists(),
                'Sauvegardes existantes : migrer les slots explicitement avant de renommer')
        campaign = next(row for row in rows if row['id'] == old)
        campaign['id'] = new_id
        story = updated.get('story', {})
        entries = story.get('entry_scenes', {})
        if old in entries:
            entries[new_id] = entries.pop(old)
        for siege in updated.get('sieges', ()):
            if siege.get('campaign_id') == old:
                siege['campaign_id'] = new_id
        for clip in updated.get('cinematics', ()):
            if (clip['trigger']['kind'] == 'campaign_start'
                    and clip['trigger']['target'] == old):
                clip['trigger']['target'] = new_id

    require(not _mentions(updated, old),
            'GameProject contient une référence non prise en charge : ' + old)
    require(not _mentions(candidate, old),
            'Content contient une référence non prise en charge : ' + old)
    normalized = Content.from_dict(
        candidate, rules=authored_rules_for_document(candidate)).to_dict()
    checked = Content.from_dict(
        normalized, rules=authored_rules_for_document(normalized))
    updated_project = GameProject.from_dict(updated, checked)
    return normalized, updated_project

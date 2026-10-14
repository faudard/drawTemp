"""R2.7 — conservative ID refactoring on canonical Content documents.

The refactor applies only known, typed mission-local relationships. Unknown
references cause an explicit refusal instead of a silent broken link. Project
references are checked but never rewritten by this Content-only command.
"""
from copy import deepcopy
from dataclasses import dataclass
import json

from .authoring import _identifier
from .model import Content, RuleError, require
from .tactical_rpg3 import authored_rules_for_document
from .workspace_editing import _locate


def _mentions(value, identifier):
    """Detect exact ID tokens or suffix-qualified IDs in opaque structures."""
    if isinstance(value, dict):
        return any(_mentions(key, identifier) or _mentions(item, identifier)
                   for key, item in value.items())
    if isinstance(value, (tuple, list)):
        return any(_mentions(item, identifier) for item in value)
    return (isinstance(value, str) and
            (value == identifier or value.endswith(':' + identifier) or
             value.endswith('/' + identifier)))


def _rewrite_condition(node, old, new):
    """Retarget only supported actor predicates, including composite leaves."""
    if not isinstance(node, dict):
        return
    if node.get('condition') in ('defeated', 'hp_below') and node.get('unit') == old:
        node['unit'] = new
    for op in ('all', 'any'):
        for child in node.get(op, ()):
            _rewrite_condition(child, old, new)
    if 'not' in node:
        _rewrite_condition(node['not'], old, new)


@dataclass(frozen=True)
class RenameMapResourceCommand:
    key: str
    baseline: str
    new_id: str
    project_snapshot: dict
    kind: str = 'workspace-rename-resource'
    views: tuple = ('renderer', 'minimap', 'inspector', 'workspace')

    def transform(self, data, mission_id):
        category, mid, old, _mission, row = _locate(data, self.key)
        if category not in ('map_actor', 'map_object'):
            raise RuleError('Renommage ID réservé aux acteurs et objets placés')
        require(mid == mission_id, 'Changer de mission avant de renommer')
        require(json.dumps(row, sort_keys=True, ensure_ascii=True) == self.baseline,
                'Ressource modifiée depuis la prévisualisation')
        _identifier(self.new_id, 'New resource id')
        require(self.new_id != old, 'Nouvel identifiant identique')
        # GameProject may reference the local resource in narrative, cinematic
        # or campaign content: never rewrite one document behind its back.
        require(not _mentions(self.project_snapshot, old),
                'Référence GameProject : utiliser une migration coordonnée')
        changed = deepcopy(data)
        mission = next(m for m in changed['missions'] if m['id'] == mid)
        entities = mission['units'] if category == 'map_actor' else mission['objects']
        require(not any(item['id'] == self.new_id for item in entities),
                'Identifiant déjà utilisé dans cette mission')
        target = next(item for item in entities if item['id'] == old)
        target['id'] = self.new_id

        if category == 'map_actor':
            if mission.get('protected_id') == old:
                mission['protected_id'] = self.new_id
            if old in mission.get('unit_levels', {}):
                mission['unit_levels'][self.new_id] = mission['unit_levels'].pop(old)
            for group in mission.get('editor_groups', ()):
                group['unit_ids'] = [
                    self.new_id if ref == old else ref
                    for ref in group['unit_ids']]
            for unit in mission['units']:
                unit['tags'] = [
                    ('formation:escort:' + self.new_id
                     if tag == 'formation:escort:' + old else tag)
                    for tag in unit.get('tags', ())]
            for trigger in mission.get('triggers', ()):
                _rewrite_condition(trigger, old, self.new_id)
                _rewrite_condition(trigger.get('when'), old, self.new_id)
                for action in trigger.get('actions', ()):
                    if action.get('kind') in ('status', 'despawn') and action.get('unit') == old:
                        action['unit'] = self.new_id
                    if action.get('kind') == 'spawn' and action.get('owner') == old:
                        action['owner'] = self.new_id
        else:
            for group in mission.get('editor_groups', ()):
                group['object_ids'] = [
                    self.new_id if ref == old else ref
                    for ref in group['object_ids']]
            for other in mission['objects']:
                if other.get('kind') in ('switch', 'ram', 'catapult') and other.get('link') == old:
                    other['link'] = self.new_id
            for trigger in mission.get('triggers', ()):
                _rewrite_interaction(trigger, old, self.new_id)
                _rewrite_interaction(trigger.get('when'), old, self.new_id)

        # A schema validator does not necessarily know every presentation or
        # authoring-only ID reference. Refuse any unknown remaining raw token.
        require(not _mentions(mission, old),
                'Référence non prise en charge : renommage refusé, aucun changement')
        result = Content.from_dict(
            changed, rules=authored_rules_for_document(changed)).to_dict()
        return result


def _rewrite_interaction(node, old, new):
    if not isinstance(node, dict):
        return
    if node.get('condition') == 'interact' and node.get('object') == old:
        node['object'] = new
    for op in ('all', 'any'):
        for child in node.get(op, ()):
            _rewrite_interaction(child, old, new)
    if 'not' in node:
        _rewrite_interaction(node['not'], old, new)


@dataclass(frozen=True)
class DeleteMapResourceCommand:
    """Remove a map resource only when all external references remain sound.

    Canonical entity deletion handles group membership cleanup. A complete
    Content validation and a conservative token scan reject dangling links.
    """
    key: str
    baseline: str
    project_snapshot: dict
    kind: str = 'workspace-delete-resource'
    views: tuple = ('renderer', 'minimap', 'inspector', 'workspace')

    def transform(self, data, mission_id):
        category, mid, identifier, _mission, row = _locate(data, self.key)
        require(category in ('map_actor', 'map_object'),
                'Suppression réservée aux acteurs et objets placés')
        require(mid == mission_id, 'Changer de mission avant de supprimer')
        require(json.dumps(row, sort_keys=True, ensure_ascii=True) == self.baseline,
                'Ressource modifiée : recommencer la prévisualisation')
        require(not _mentions(self.project_snapshot, identifier),
                'Référence GameProject : suppression refusée')
        from .entity_editing import remove_entity
        candidate = remove_entity(
            data, mid, 'actor' if category == 'map_actor' else 'object', identifier)
        require(not _mentions(candidate, identifier),
                'Suppression refusée : référence Content restante')
        return Content.from_dict(
            candidate, rules=authored_rules_for_document(candidate)).to_dict()



@dataclass(frozen=True)
class DeleteMapResourcesCommand:
    """Fail-closed, dependency-aware multi-deletion in one Editor transaction.

    The command reuses the existing typed single-delete validation. A link
    from a selected switch to a selected door is resolved by deleting its
    source first; all other dangling references block the entire operation.
    The returned document is committed only once by EditingContext.
    """
    keys: tuple
    baselines: tuple
    project_snapshot: dict
    kind: str = 'workspace-batch-delete'
    views: tuple = ('renderer', 'minimap', 'inspector', 'workspace')

    def transform(self, data, mission_id):
        require(isinstance(self.keys, tuple) and
                2 <= len(self.keys) <= 128 and
                len(self.keys) == len(set(self.keys)) and
                len(self.keys) == len(self.baselines),
                'Suppression multiple : 2 à 128 ressources distinctes')
        remaining = {}
        for key, baseline in zip(self.keys, self.baselines):
            category, mid, _identity, _mission, row = _locate(data, key)
            require(category in ('map_actor', 'map_object') and mid == mission_id,
                    'Suppression multiple : acteurs/objets de la même mission')
            require(json.dumps(row, sort_keys=True, ensure_ascii=True) == baseline,
                    'Sélection modifiée depuis la prévisualisation')
            remaining[key] = baseline

        candidate = data
        while remaining:
            previous_count = len(remaining)
            failures = {}
            for key, baseline in tuple(sorted(remaining.items())):
                command = DeleteMapResourceCommand(
                    key, baseline, self.project_snapshot)
                try:
                    candidate = command.transform(candidate, mission_id)
                except RuleError as exc:
                    failures[key] = str(exc)
                else:
                    del remaining[key]
            if len(remaining) == previous_count:
                details = '; '.join(
                    key + ': ' + reason for key, reason in sorted(failures.items()))
                raise RuleError(
                    'Suppression multiple refusée : liens non résolus. ' + details[:850])
        return candidate


def plan_coordinated_rename(data, project, key, baseline, new_id):
    """Plan a validated two-document rename without committing either document.

    An actor cue in a cinematic explicitly triggered by the same mission is
    the only supported cross-document actor reference. Arbitrary scene,
    campaign, narration and foreign-mission cues remain ambiguous and block.
    The caller commits both snapshots through the existing StudioHistory.
    """
    from .game_project import GameProject

    category, mid, old, _mission, _row = _locate(data, key)
    require(category in ('map_actor', 'map_object'),
            'Migration réservée aux ressources placées')
    original = project.to_dict() if isinstance(project, GameProject) else project
    updated = deepcopy(original)
    if category == 'map_actor':
        for clip in updated.get('cinematics', ()):
            trigger = clip['trigger']
            for event in clip['events']:
                if event.get('kind') != 'actor' or event.get('actor') != old:
                    continue
                kind = trigger['kind']
                target = trigger['target']
                same_mission = (
                    kind in ('before_mission', 'after_mission') and target == mid
                    or kind == 'tactical_event' and target.startswith(mid + '/'))
                require(same_mission,
                        'Cinématique non rattachée à cette mission : migration refusée')
                event['actor'] = new_id

    require(not _mentions(updated, old),
            'GameProject contient des références non prises en charge')
    command = RenameMapResourceCommand(key, baseline, new_id, updated)
    candidate = command.transform(data, mid)
    validated_content = Content.from_dict(
        candidate, rules=authored_rules_for_document(candidate))
    validated_project = GameProject.from_dict(updated, validated_content)
    return candidate, validated_project

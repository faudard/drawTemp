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

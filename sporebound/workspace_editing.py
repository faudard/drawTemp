"""3.7.33A — validated, Tk-free projections for editing a Workspace selection.

All mutations go through the existing EntityCommand/edit_entity,
editor_groups.rename_editor_group or the editor's canonical terrain brushes.
The caller executes WorkspacePropertyCommand with EditingContext: one
Document.replace, one history entry and the same authored Content rules.
"""
from dataclasses import dataclass
from copy import deepcopy
import json
from types import SimpleNamespace

from .model import RuleError
from .studio_entity_inspector import OBJECT_FIELDS, FIELD_LABELS, BOOL_FIELDS, INT_FIELDS


@dataclass(frozen=True)
class EditableField:
    name: str
    label: str
    value: object
    kind: str = 'text'
    choices: tuple = ()


@dataclass(frozen=True)
class EditableForm:
    key: str
    mission_id: str
    baseline: str
    fields: tuple


def _locate(data, key):
    if ':' not in key:
        raise RuleError('Ressource Workspace invalide : ' + key)
    kind, identifier = key.split(':', 1)
    if kind not in ('map_actor', 'map_object', 'editor_group', 'map_tile',
                    'tactical_event'):
        raise RuleError('Ressource non éditable dans cet inspecteur : ' + key)
    if '/' not in identifier:
        raise RuleError('Identifiant Workspace invalide : ' + key)
    mid, entity_id = identifier.split('/', 1)
    mission = next((m for m in data['missions'] if m['id'] == mid), None)
    if mission is None:
        raise RuleError('Mission introuvable : ' + mid)
    if kind == 'map_tile':
        try:
            x, y = (int(part) for part in entity_id.split(','))
        except ValueError as exc:
            raise RuleError('Coordonnées de case invalides') from exc
        if not (0 <= x < mission['board']['width'] and
                0 <= y < mission['board']['height']):
            raise RuleError('Case hors carte')
        entity = next((row for row in mission['board']['tiles']
                       if tuple(row['pos']) == (x, y)), {'pos': [x, y]})
        return kind, mid, (x, y), mission, entity
    source = ('units' if kind == 'map_actor' else
              'objects' if kind == 'map_object' else
              'triggers' if kind == 'tactical_event' else 'editor_groups')
    entity = next((row for row in mission.get(source, ())
                   if row['id'] == entity_id), None)
    if entity is None:
        raise RuleError('Ressource déplacée ou supprimée : ' + key)
    return kind, mid, entity_id, mission, entity


def editable_form(data, key):
    kind, mid, identity, mission, row = _locate(data, key)
    baseline = json.dumps(row, sort_keys=True, ensure_ascii=True)
    fields = []
    if kind == 'map_actor':
        from .iso_actor_atlas import actor_direction
        choices = {'team': ('player', 'enemy'),
                   'facing': ('south', 'north', 'east', 'west')}
        for name in ('name', 'team', 'facing'):
            value = (actor_direction(SimpleNamespace(**row))
                     if name == 'facing' else row[name])
            fields.append(EditableField(name, FIELD_LABELS[name], value,
                                        'choice' if name in choices else 'text',
                                        choices.get(name, ())))
    elif kind == 'map_object':
        defaults = {'locked': False, 'enabled': True, 'bidirectional': True,
                    'disabled': False, 'hp': 1, 'amount': 1, 'power': 15,
                    'ammo': 0, 'charges': 2, 'cost': 2}
        if row['kind'] in ('ram', 'catapult'):
            defaults['power'] = 1
        if row['kind'] in ('ram', 'catapult', 'defense'):
            defaults['team'] = 'enemy' if row['kind'] == 'defense' else 'player'
        for name in OBJECT_FIELDS[row['kind']]:
            value = row.get(name, defaults.get(name, ''))
            if name == 'destination':
                value = ','.join(map(str, value))
            choices = (tuple(o['id'] for o in mission['objects']
                             if o['kind'] == 'door')
                       if name == 'link' else
                       ('player', 'enemy') if name == 'team' else ())
            field_kind = ('boolean' if name in BOOL_FIELDS else
                          'integer' if name in INT_FIELDS else
                          'choice' if choices else 'text')
            fields.append(EditableField(name, FIELD_LABELS[name], value,
                                        field_kind, choices))
    elif kind == 'tactical_event':
        # Only single-despawn event references are editable inline. Complex
        # multi-action events retain their existing specialized graph editor.
        despawns = [action for action in row.get('actions', ())
                    if action.get('kind') == 'despawn']
        if len(despawns) == 1:
            choices = tuple(actor['id'] for actor in mission['units'])
            fields.append(EditableField(
                'despawn_unit', 'Référence acteur (despawn)',
                despawns[0].get('unit', ''), 'choice', choices))
    elif kind == 'editor_group':
        fields.append(EditableField('name', 'Nom du groupe', row['name']))
    elif kind == 'map_tile':
        from .iso_map import FEATURES, SURFACES
        fields.extend((
            EditableField('surface', 'Surface', row.get('surface', 'grass'),
                          'choice', tuple(sorted(SURFACES))),
            EditableField('feature', 'Décor', row.get('feature', ''),
                          'choice', ('',) + tuple(sorted(FEATURES))),
            EditableField('height', 'Hauteur', row.get('height', 0), 'integer'),
        ))
    return EditableForm(key, mid, baseline, tuple(fields))


def _parse(field, value):
    if field.kind == 'boolean':
        if type(value) is not bool:
            raise RuleError('Une case à cocher est attendue : ' + field.name)
        return value
    if field.kind == 'integer':
        if type(value) is bool:
            raise RuleError('Entier attendu : ' + field.name)
        try:
            if isinstance(value, str) and not value.strip():
                raise ValueError('empty')
            return int(value)
        except (ValueError, TypeError) as exc:
            raise RuleError('Entier attendu : ' + field.name) from exc
    if not isinstance(value, str):
        raise RuleError('Texte attendu : ' + field.name)
    if field.kind == 'choice' and value not in field.choices:
        raise RuleError('Valeur inconnue pour ' + field.name + ' : ' + value)
    return value


@dataclass(frozen=True)
class WorkspacePropertyCommand:
    key: str
    baseline: str
    values: tuple
    kind: str = 'workspace-property'
    views: tuple = ('renderer', 'minimap', 'inspector', 'workspace')

    def transform(self, data, mission_id):
        form = editable_form(data, self.key)
        if form.mission_id != mission_id:
            raise RuleError('Changer de mission avant de modifier cette ressource')
        if form.baseline != self.baseline:
            raise RuleError('Ressource modifiée depuis sa sélection : actualiser l’inspecteur')
        allowed = {field.name: field for field in form.fields}
        raw = dict(self.values)
        if not raw or len(raw) != len(self.values) or not raw.keys() <= allowed.keys():
            raise RuleError('Propriétés non prises en charge')
        parsed = {name: _parse(allowed[name], value) for name, value in raw.items()}
        changed = {name: value for name, value in parsed.items()
                   if value != allowed[name].value}
        if not changed:
            raise RuleError('Aucune propriété modifiée')
        category, mid, identity, _mission, _row = _locate(data, self.key)
        if category in ('map_actor', 'map_object'):
            from .entity_editing import edit_entity
            return edit_entity(data, mid, 'actor' if category == 'map_actor'
                               else 'object', identity, **changed)
        if category == 'tactical_event':
            result = deepcopy(data)
            mission = next(m for m in result['missions'] if m['id'] == mid)
            trigger = next(t for t in mission['triggers'] if t['id'] == identity)
            matches = [a for a in trigger['actions'] if a.get('kind') == 'despawn']
            if set(changed) != {'despawn_unit'} or len(matches) != 1:
                raise RuleError('Édition spécialisée requise pour cet événement')
            matches[0]['unit'] = changed['despawn_unit']
            return result
        if category == 'editor_group':
            from .editor_groups import rename_editor_group
            return rename_editor_group(data, mid, identity, changed['name'])
        # Use the same paint path as the map editor; no second terrain codec.
        from .editor import Document
        from .model import Content
        from .tactical_rpg3 import authored_rules_for_document
        scratch = Document(Content.from_dict(
            data, rules=authored_rules_for_document(data)))
        for name, value in changed.items():
            if name == 'height':
                if not 0 <= value <= 99:
                    raise RuleError('Hauteur attendue entre 0 et 99')
                brush = 'height:' + str(value)
            elif name == 'feature':
                brush = 'feature:' + value if value else 'feature-erase'
            else:
                brush = 'surface:' + value
            scratch.paint_many(mid, [identity], brush)
        return scratch.data

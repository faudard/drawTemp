"""Contextual editing of existing mission actors and interactive objects.

Pure headless transactions: Content and the authored rules remain authoritative.
No new persisted pose/action field or standalone combat interpreter.
"""
from copy import deepcopy
from dataclasses import dataclass

from .authoring import _edit, _identifier
from .entity_placement import FACING, palette_entities, place_palette_entity, suggested_id
from .map_authoring import _cell, _mission
from .model import require


@dataclass(frozen=True)
class EntitySelection:
    kind: str
    id: str
    label: str


def entities_at(data, mission_id, cell):
    """Locate units using their whole footprint; objects use their anchor."""
    mission = _mission(data, mission_id)
    point = _cell(mission, cell)
    result = []
    for actor in mission['units']:
        x, y = actor['pos']
        w, h = actor.get('footprint', (1, 1))
        if x <= point[0] < x+w and y <= point[1] < y+h:
            result.append(EntitySelection('actor', actor['id'], actor['name']))
    for obj in mission['objects']:
        if tuple(obj['pos']) == point:
            result.append(EntitySelection('object', obj['id'], obj['kind']))
    return tuple(result)


def get_entity(data, mission_id, kind, entity_id):
    require(kind in ('actor', 'object'), 'Unknown entity category')
    mission = _mission(data, mission_id)
    field = 'units' if kind == 'actor' else 'objects'
    entity = next((r for r in mission[field] if r['id'] == entity_id), None)
    require(entity is not None, 'Entity no longer exists')
    return deepcopy(entity)


def _name(value):
    require(isinstance(value, str) and bool(value.strip()), 'Actor needs a name')
    return value.strip()


def edit_entity(data, mission_id, entity_kind, entity_id, **values):
    """Whitelist authored properties; immutable IDs and object kinds never change."""
    require(entity_kind in ('actor', 'object'), 'Unknown entity category')
    original = get_entity(data, mission_id, entity_kind, entity_id)
    if entity_kind == 'actor':
        allowed = {'name', 'team', 'facing'}
    else:
        allowed = {
            'door': {'locked', 'hp'},
            'chest': {'amount'},
            'switch': {'link'},
            'ram': {'link', 'power', 'team'},
            'catapult': {'link', 'power', 'team', 'ammo'},
            'passage': {'destination', 'enabled', 'bidirectional', 'cost'},
            'defense': {'team', 'power', 'charges', 'disabled'},
        }[original['kind']]
    require(bool(values) and set(values) <= allowed, 'Unsupported entity properties')
    prepared = {}
    for key, value in values.items():
        if key == 'name':
            value = _name(value)
        elif key in ('team',):
            require(value in ('player', 'enemy'), 'Invalid team')
        elif key == 'facing':
            require(value in FACING, 'Invalid facing')
            value = list(FACING[value])
        elif key == 'link':
            require(type(value) is str and bool(value), 'Choose an existing door')
        elif key == 'destination':
            from .entity_placement import parse_destination
            value = list(parse_destination(value))
        elif key in ('locked', 'enabled', 'bidirectional', 'disabled'):
            require(type(value) is bool, 'Expected a boolean switch')
        elif key in ('hp', 'amount', 'power', 'charges', 'ammo', 'cost'):
            require(type(value) is int, 'Expected an integer property')
        prepared[key] = value

    def change(_, mission):
        field = 'units' if entity_kind == 'actor' else 'objects'
        record = next(e for e in mission[field] if e['id'] == entity_id)
        record.update(deepcopy(prepared))
    return _edit(data, mission_id, change)


def relocate_entity(data, mission_id, kind, entity_id, cell):
    """Move an entity, keeping defense targets and patrol paths with their owner."""
    old = get_entity(data, mission_id, kind, entity_id)
    mission = _mission(data, mission_id)
    target = _cell(mission, cell)
    dx, dy = target[0]-old['pos'][0], target[1]-old['pos'][1]
    require(dx != 0 or dy != 0, 'Select a different cell')

    def change(_, m):
        field = 'units' if kind == 'actor' else 'objects'
        record = next(e for e in m[field] if e['id'] == entity_id)
        record['pos'] = list(target)
        if kind == 'actor' and record.get('patrol_route'):
            record['patrol_route'] = [[x+dx, y+dy] for x, y in record['patrol_route']]
        if kind == 'object' and record['kind'] == 'defense':
            record['cells'] = [[x+dx, y+dy] for x, y in record['cells']]
        # Passage destinations deliberately stay absolute; caller edits exit explicitly.
    return _edit(data, mission_id, change)


def duplicate_entity(data, mission_id, kind, entity_id, cell):
    """Clone a configured actor or object, retaining links but assigning a fresh ID."""
    original = get_entity(data, mission_id, kind, entity_id)
    mission = _mission(data, mission_id)
    target = _cell(mission, cell)
    if kind == 'actor':
        from .iso_actor_atlas import actor_direction
        from types import SimpleNamespace
        entry = next(e for e in palette_entities(data, mission_id)
                     if e.kind == 'actor' and e.value == 'unit:' + entity_id)
        return place_palette_entity(
            data, mission_id, entry, target, team=original['team'],
            name=original['name'],
            facing=actor_direction(SimpleNamespace(**original)))
    entry = next(e for e in palette_entities(data, mission_id)
                 if e.kind == 'object' and e.value == original['kind'])
    clone = deepcopy(original)
    clone['id'] = suggested_id(data, mission_id, entry)
    dx, dy = target[0]-clone['pos'][0], target[1]-clone['pos'][1]
    clone['pos'] = list(target)
    if clone['kind'] == 'defense':
        clone['cells'] = [[x+dx, y+dy] for x, y in clone['cells']]
    def change(_, m):
        m['objects'].append(clone)
    return _edit(data, mission_id, change)


def remove_entity(data, mission_id, kind, entity_id):
    """Fail atomically on last-team or dangling mission references."""
    get_entity(data, mission_id, kind, entity_id)
    def change(_, mission):
        field = 'units' if kind == 'actor' else 'objects'
        mission[field] = [e for e in mission[field] if e['id'] != entity_id]
    return _edit(data, mission_id, change)

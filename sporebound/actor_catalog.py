"""Reusable, validated actor templates backed by Content.archetypes.

Mission instances are snapshots: changing a template never silently rewrites
already-authored encounters or a replay.
"""
from copy import deepcopy
from dataclasses import asdict

from .actors import TEMPLATE_FIELDS
from .model import Content, require
from .authoring import _identifier, _cell, _mission


def _checked(data):
    return Content.from_dict(data).to_dict()


def capture_actor(data, mission_id, unit_id, archetype_id):
    """Promote an existing playable actor to a reusable template."""
    _identifier(archetype_id, 'Archetype id')
    content = Content.from_dict(data)
    require(archetype_id not in content.archetypes, 'Archetype already exists')
    require(mission_id in content.missions, 'Unknown mission')
    unit = next((u for u in content.missions[mission_id].units if u.id == unit_id), None)
    require(unit is not None, 'Select an existing actor')
    new = deepcopy(data)
    new.setdefault('archetypes', {})[archetype_id] = {
        key: deepcopy(value) for key, value in asdict(unit).items()
        if key in TEMPLATE_FIELDS
    }
    return _checked(new)


def create_archetype(data, archetype_id, *, kind='monster', max_hp=40,
                     attack=5, speed=10, move=4, weapon='melee', skills=()):
    _identifier(archetype_id, 'Archetype id')
    require(kind in ('character', 'monster', 'summon'), 'Unknown actor kind')
    new = deepcopy(data)
    library = new.setdefault('archetypes', {})
    require(archetype_id not in library, 'Archetype already exists')
    library[archetype_id] = {
        'kind': kind, 'max_hp': max_hp, 'attack': attack, 'speed': speed,
        'move': move, 'weapon': weapon, 'skills': list(skills),
    }
    return _checked(new)


def place_archetype(data, mission_id, archetype_id, unit_id, name, team, pos):
    _identifier(unit_id, 'Actor id')
    require(team in ('player', 'enemy'), 'Actors belong to player or enemy')
    require(isinstance(name, str) and bool(name.strip()), 'Actor needs a name')
    new = deepcopy(data)
    require(archetype_id in new.get('archetypes', {}), 'Unknown archetype')
    mission = _mission(new, mission_id)
    require(mission is not None, 'Unknown mission')
    require(all(unit['id'] != unit_id for unit in mission['units']), 'Actor id already exists')
    cell = _cell(mission, pos)
    mission['units'].append({'id': unit_id, 'name': name.strip(),
                             'team': team, 'pos': cell, 'archetype': archetype_id})
    return _checked(new)


def remove_archetype(data, archetype_id):
    new = deepcopy(data)
    require(archetype_id in new.get('archetypes', {}), 'Unknown archetype')
    for mission in new['missions']:
        require(all(actor.get('archetype') != archetype_id for actor in mission['units']),
                'Archetype is used by a mission')
        for trigger in mission.get('triggers', []):
            for action in trigger.get('actions', []):
                actors = [action.get('actor', {})] + action.get('actors', [])
                require(all(actor.get('archetype') != archetype_id for actor in actors),
                        'Archetype is used by an event')
    del new['archetypes'][archetype_id]
    return _checked(new)

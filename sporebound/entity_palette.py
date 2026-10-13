"""Headless 3.7.19C palette for mission actors and interactive objects.

Actor presets are *existing mission actors* rather than a parallel registry.
This deliberately works with older campaigns that have no archetypes. Edits
return validated Content snapshots for Document.replace and undo/redo.
"""
from copy import deepcopy
from dataclasses import dataclass

from .authoring import add_object
from .map_authoring import _cell, _mission
from .model import Content, require
from .tactical_rpg3 import authored_rules_for_document


FACING = {
    'south': (0, 1), 'north': (0, -1),
    'east': (1, 0), 'west': (-1, 0),
}
# Presentation-only placeholders backed by the existing scenery atlas.
# These are not new gameplay objects and do not claim to be final item art.
OBJECT_PROP_HINTS = {
    'door': 'arch', 'switch': 'lantern', 'chest': 'crate',
    'ram': 'pillar', 'catapult': 'boulder', 'passage': 'stairs',
    'defense': 'stone_wall',
}

OBJECT_LABELS = (
    ('door', 'Porte'),
    ('switch', 'Levier'),
    ('chest', 'Coffre'),
    ('ram', 'Bélier'),
    ('catapult', 'Catapulte'),
    ('passage', 'Passage'),
    ('defense', 'Défense'),
)


@dataclass(frozen=True)
class EntityEntry:
    id: str
    label: str
    kind: str
    team: str = ''
    style: str = ''
    description: str = ''


def entity_entries(data, mission_id):
    """One palette per active mission, including legacy actor snapshots."""
    mission = _mission(data, mission_id)
    from .iso_actor_atlas import actor_style
    from types import SimpleNamespace
    actors = tuple(EntityEntry('actor:' + actor['id'], actor['name'],
                               'actor', actor['team'],
                               actor_style(SimpleNamespace(**actor)),
                               'Copie de l’acteur de cette mission')
                   for actor in mission['units']
                   if actor.get('team') in ('player', 'enemy'))
    # Templates created by Character/Bestiary Studio can be placed without
    # first inserting a sacrificial copy into the current mission.
    archetypes = tuple(EntityEntry(
        'archetype:' + key, key.replace('_', ' ').capitalize(), 'archetype',
        'enemy',
        actor_style(SimpleNamespace(
            id='', name='', team='enemy', archetype=key,
            weapon=definition.get('weapon', ''))),
        'Modèle installé dans Character/Bestiary Studio')
        for key, definition in sorted(data.get('archetypes', {}).items()))
    objects = tuple(EntityEntry('object:' + kind, label, 'object',
                                description=('Choisir une porte cible' if kind in
                                             ('switch', 'ram', 'catapult') else
                                             'Préciser une sortie x,y' if kind == 'passage'
                                             else 'Objet interactif'))
                    for kind, label in OBJECT_LABELS)
    return actors + archetypes + objects


def _unique_id(mission, prefix):
    identifiers = {item['id'] for field in ('units', 'objects')
                   for item in mission.get(field, ())}
    index = 1
    while f'{prefix}_{index}' in identifiers:
        index += 1
    return f'{prefix}_{index}'


def place_entity(data, mission_id, entry_id, cell, *,
                 facing='south', link='', destination=None, team=None):
    """Place a validated actor copy or interactive object, in one transaction.

    Linked objects continue to use authoring.add_object and the real gameplay
    object schema; no fake Studio-only gameplay interpretation is introduced.
    """
    mission = _mission(data, mission_id)
    pos = _cell(mission, cell)
    require(isinstance(entry_id, str) and ':' in entry_id,
            'Choose an actor or object from the palette')
    kind, _, source_id = entry_id.partition(':')
    require(facing in FACING, 'Unknown actor orientation')
    require(kind in ('actor', 'archetype', 'object'), 'Unknown entity kind')
    require(bool(source_id), 'Invalid entity template')

    # Reject ambiguous stacking before triggering the full Content validator.
    occupied = {tuple(obj['pos']) for obj in mission.get('objects', ())}
    for actor in mission.get('units', ()):
        x, y = actor['pos']
        w, h = actor.get('footprint', (1, 1))
        occupied.update((x+dx, y+dy) for dy in range(h) for dx in range(w))

    if kind == 'object':
        require(source_id in dict(OBJECT_LABELS), 'Unknown object type')
        require(pos not in occupied, 'Cell occupied by an actor or object')
        identifier = _unique_id(mission, source_id)
        return add_object(data, mission_id, identifier, source_id, pos,
                          link=link, destination=destination)

    if kind == 'archetype':
        source = data.get('archetypes', {}).get(source_id)
        require(source is not None, 'Archetype template no longer exists')
    else:
        source = next((unit for unit in mission['units']
                       if unit['id'] == source_id), None)
        require(source is not None, 'Actor template no longer exists')
    w, h = source.get('footprint', (1, 1))
    destination_cells = {(pos[0]+dx, pos[1]+dy)
                         for dy in range(h) for dx in range(w)}
    for target in destination_cells:
        _cell(mission, target)
    require(not destination_cells.intersection(occupied),
            'Actor footprint overlaps another entity')

    new = deepcopy(data)
    target_mission = _mission(new, mission_id)
    if kind == 'archetype':
        # Spawn through the existing Content/ActorFactory template resolver.
        # The archetype is never flattened or modified in the palette.
        chosen_team = 'enemy' if team is None else team
        require(chosen_team in ('player', 'enemy'), 'Choose an actor team')
        target_mission['units'].append({
            'id': _unique_id(target_mission, 'actor'),
            'name': source_id.replace('_', ' ').capitalize(),
            'team': chosen_team, 'pos': list(pos),
            'archetype': source_id, 'facing': list(FACING[facing]),
        })
        return Content.from_dict(
            new, rules=authored_rules_for_document(new)).to_dict()
    actor = deepcopy(source)
    actor['id'] = _unique_id(target_mission, 'actor')
    actor['pos'] = list(pos)
    actor['facing'] = list(FACING[facing])
    if 'max_hp' in actor:
        actor['hp'] = actor['max_hp']
    if 'max_mp' in actor:
        actor['mp'] = actor['max_mp']
    actor['ct'] = 0
    for flag in ('moved', 'acted', 'disengaging'):
        actor.pop(flag, None)
    actor.pop('cast', None)
    actor.pop('statuses', None)
    # Patrols are relative to their original spawn. Moving the template
    # must translate every waypoint as a unit, or validation rejects it.
    dx, dy = pos[0] - source['pos'][0], pos[1] - source['pos'][1]
    if source.get('patrol_route'):
        actor['patrol_route'] = [[x+dx, y+dy]
                                 for x, y in source['patrol_route']]
    target_mission['units'].append(actor)
    return Content.from_dict(
        new, rules=authored_rules_for_document(new)).to_dict()


@dataclass(frozen=True)
class EntityPlacementPreview:
    """Exact validation result plus affected cells for Canvas overlays."""
    cells: tuple
    allowed: bool
    reason: str = ''


def preview_entity_placement(data, mission_id, entry_id, cell, *,
                             facing='south', link='', destination=None, team=None):
    """Authoritative WYSIWYG placement check; does not modify the document.

    For correctness the hover calls the same Content-validating operation as
    committing a placement. The GUI caches this result per hovered cell to
    avoid full Content validation on every mouse pixel.
    """
    mission = _mission(data, mission_id)
    cells = (tuple(cell),)
    if isinstance(entry_id, str) and (entry_id.startswith('actor:')
                                      or entry_id.startswith('archetype:')):
        kind, _, source_id = entry_id.partition(':')
        if kind == 'archetype':
            source = data.get('archetypes', {}).get(source_id)
        else:
            source = next((actor for actor in mission['units']
                           if actor['id'] == source_id), None)
        if source:
            width, height = source.get('footprint', (1, 1))
            cells = tuple((cell[0] + dx, cell[1] + dy)
                          for dy in range(height) for dx in range(width))
    try:
        place_entity(data, mission_id, entry_id, cell,
                     facing=facing, link=link, destination=destination,
                     team=team)
    except (ValueError, TypeError) as exc:
        return EntityPlacementPreview(cells, False, str(exc))
    return EntityPlacementPreview(cells, True)


def preview_passage_source(data, mission_id, cell):
    """Validate the first click of a graphical passage placement.

    No half-created passage ever enters the document. The complete passage
    remains subject to place_entity / Content validation at the second click.
    """
    from .model import RuleError
    try:
        mission = Content.from_dict(
            data, rules=authored_rules_for_document(data)).missions[mission_id]
        source = _cell(_mission(data, mission_id), cell)
        require(not mission.board.tile(source).blocked,
                'Blocked passage entrance')
        require(not any(source in unit.occupied_cells() for unit in mission.units),
                'Passage entrance overlaps an actor')
        require(not any(tuple(obj['pos']) == source for obj in mission.objects),
                'Passage entrance overlaps an object')
    except (RuleError, ValueError, KeyError, TypeError) as exc:
        return EntityPlacementPreview((tuple(cell),), False, str(exc))
    return EntityPlacementPreview((source,), True)

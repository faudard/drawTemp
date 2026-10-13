"""3.7.19C — Palette actors and tactical objects using existing Content APIs.

The catalog is a view of the live project, not a second actor/object registry.
Placement edits are validated transactions; no runtime or replay code lives here.
"""
from dataclasses import asdict

from .asset_palette import PaletteEntry
from .authoring import _edit, _identifier, add_object
from .model import Content, require
from .tactical_rpg3 import authored_rules_for_document

FACING = {'south': (0, 1), 'north': (0, -1),
          'east': (1, 0), 'west': (-1, 0)}
OBJECT_LABELS = {
    'chest': 'Coffre', 'door': 'Porte', 'switch': 'Levier',
    'passage': 'Passage', 'ram': 'Bélier', 'catapult': 'Catapulte',
    'defense': 'Défense',
}


def palette_entities(data, mission_id):
    """Entries from actual archetypes/mission actors plus supported siege objects."""
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown mission')
    result = []
    for identifier, template in sorted(data.get('archetypes', {}).items()):
        size = tuple(template.get('footprint', (1, 1)))
        result.append(PaletteEntry('actor:archetype:' + identifier, identifier,
                                   'Acteurs', 'actor', 'archetype:' + identifier,
                                   size=size))
    for actor in mission['units']:
        result.append(PaletteEntry('actor:unit:' + actor['id'],
                                   actor['name'] + ' (' + actor['id'] + ')',
                                   'Acteurs', 'actor', 'unit:' + actor['id'],
                                   size=tuple(actor.get('footprint', (1, 1)))))
    for kind, name in OBJECT_LABELS.items():
        result.append(PaletteEntry('object:' + kind, name, 'Interactions',
                                   'object', kind))
    return tuple(result)


def suggested_id(data, mission_id, entry):
    """Never reuse an ID after placing the same palette item twice."""
    mission = next(m for m in data['missions'] if m['id'] == mission_id)
    occupied = {entity['id'] for key in ('units', 'objects') for entity in mission[key]}
    stem = ('actor_' if entry.kind == 'actor' else 'obj_') + ''.join(
        c if c.isascii() and (c.isalnum() or c == '_') else '_'
        for c in entry.value.rsplit(':', 1)[-1].lower())
    stem = stem[:50].rstrip('_') or 'entity'
    if stem not in occupied:
        return stem
    index = 2
    while f'{stem}_{index}' in occupied:
        index += 1
    return f'{stem}_{index}'


def parse_destination(value):
    if isinstance(value, str):
        parts = value.split(',')
        require(len(parts) == 2 and all(part.strip().lstrip('-').isdigit()
                                         for part in parts),
                'Passage: destination attendue au format x,y')
        return tuple(int(part.strip()) for part in parts)
    require(isinstance(value, (tuple, list)) and len(value) == 2
            and all(type(n) is int for n in value),
            'Passage: destination attendue au format x,y')
    return tuple(value)


def place_palette_entity(data, mission_id, entry, cell, *, entity_id='',
                         name='', team='enemy', facing='south', link='',
                         destination=''):
    """One atomic, validated edit, suitable for Document.replace and Undo/Redo."""
    require(entry.kind in ('actor', 'object'), 'Choose an actor or interactive object')
    entity_id = (entity_id or suggested_id(data, mission_id, entry)).strip()
    _identifier(entity_id, 'Entity id')
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown mission')
    require(not any(row['id'] == entity_id for key in ('units', 'objects')
                    for row in mission[key]), 'Entity id already exists')
    if entry.kind == 'object':
        require(entry.value in OBJECT_LABELS, 'Unknown object type')
        exit_cell = parse_destination(destination) if entry.value == 'passage' else None
        return add_object(data, mission_id, entity_id, entry.value, cell,
                          link=link.strip(), destination=exit_cell)

    require(facing in FACING, 'Unknown actor orientation')
    require(team in ('player', 'enemy'), 'Choose player or enemy team')
    actor_name = (name or entry.name.split(' (', 1)[0]).strip()
    require(bool(actor_name), 'Actor needs a name')
    source = entry.value

    def change(doc, current):
        # The actor factory and Content validator own archetype inheritance.
        if source.startswith('archetype:'):
            template = source[len('archetype:'):]
            require(template in doc.get('archetypes', {}), 'Unknown actor archetype')
            spawn = {'id': entity_id, 'name': actor_name, 'team': team,
                     'pos': list(cell), 'facing': list(FACING[facing]),
                     'archetype': template}
        elif source.startswith('unit:'):
            source_id = source[len('unit:'):]
            original = next((u for u in current['units'] if u['id'] == source_id), None)
            require(original is not None, 'Actor template no longer exists')
            # Snapshot the complete unit, including inherited archetype data.
            resolved = Content.from_dict(
                doc, rules=authored_rules_for_document(doc)).missions[mission_id]
            original = next(u for u in resolved.units if u.id == source_id)
            spawn = asdict(original)
            spawn.update(id=entity_id, name=actor_name, team=team,
                         pos=list(cell), facing=list(FACING[facing]),
                         hp=original.max_hp, mp=original.max_mp,
                         ct=0, moved=False, acted=False, cast=None,
                         disengaging=False, statuses={})
            # Patrol cells are authored absolute coordinates: translate with the clone.
            if original.patrol_route:
                dx, dy = cell[0] - original.pos[0], cell[1] - original.pos[1]
                spawn['patrol_route'] = [[x+dx, y+dy]
                                         for x, y in original.patrol_route]
        else:
            raise ValueError('Unknown palette actor source')
        current['units'].append(spawn)

    # Do not mutate `data` if overlap, invalid footprint, blocked terrain,
    # missing skills, etc. fails the existing Content contract.
    return _edit(data, mission_id, change)


def preview_entity_cells(data, mission_id, entry, cell, *, link='',
                         destination=''):
    """Cheap hover validation only; click always uses full Content validation."""
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    if mission is None or not isinstance(cell, (list, tuple)) or len(cell) != 2:
        return (), False
    if any(type(n) is not int for n in cell):
        return (), False
    w, h = entry.footprint()
    cells = tuple((cell[0]+dx, cell[1]+dy)
                  for dy in range(h) for dx in range(w))
    width, height = mission['board']['width'], mission['board']['height']
    allowed = all(0 <= x < width and 0 <= y < height for x, y in cells)
    if not allowed:
        return cells, False
    if entry.kind == 'actor':
        blocked = {tuple(tile['pos']) for tile in mission['board']['tiles']
                   if tile.get('blocked', False)}
        occupied = {(u['pos'][0]+dx, u['pos'][1]+dy)
                    for u in mission['units']
                    for dx in range(u.get('footprint', (1, 1))[0])
                    for dy in range(u.get('footprint', (1, 1))[1])}
        allowed = not any(c in blocked or c in occupied for c in cells)
    elif entry.kind == 'object':
        if entry.value in ('switch', 'ram', 'catapult'):
            allowed = any(o['kind'] == 'door' and o['id'] == link
                          for o in mission['objects'])
        if entry.value == 'passage':
            try:
                x, y = parse_destination(destination)
                allowed = 0 <= x < width and 0 <= y < height
            except ValueError:
                allowed = False
        if entry.value == 'door':
            allowed = not any(tuple(u['pos']) == tuple(cell)
                              for u in mission['units'])
    return cells, allowed

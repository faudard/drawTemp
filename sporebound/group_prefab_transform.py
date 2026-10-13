"""Rotate self-contained 3.7.25D group prefabs without a second map model.

The returned document is still a normal group prefab and remains editable by
existing Content/structure/floor operations. Rotation uses map (x,y) geometry:
clockwise (x,y) -> (height-1-y,x). No authoring file is mutated.
"""
from copy import deepcopy

from .group_prefabs import _validate_prefab
from .iso_structures import structure_template
from .model import require


def rotate_group_prefab(prefab, quarter_turns):
    """Return a new validated 0/90/180/270-degree prefab.

    Every record carrying map coordinates is rotated as part of one coherent
    layout: tiles, hierarchy, structure identity/turns, upper decks, stair
    endpoints, actor patrols/footprints, and interactive object destinations.
    """
    _validate_prefab(prefab)
    require(type(quarter_turns) is int and 0 <= quarter_turns <= 3,
            'Prefab rotation must be 0, 1, 2, or 3 quarter turns')
    result = deepcopy(prefab)
    for _ in range(quarter_turns):
        width, height = result['size']

        def point(cell):
            x, y = cell
            return [height - 1 - y, x]

        def rect_corner(pos, w, h):
            # Rotate the occupied rectangle, not just its north-west point.
            return [height - pos[1] - h, pos[0]]

        for tile in result['tiles']:
            tile['pos'] = point(tile['pos'])
        for group in result['groups']:
            group['cells'] = [point(c) for c in group['cells']]
        for building in result['structures']:
            plan = structure_template(building['name'], building['turns'],
                                      door_slot=building['door_slot'])
            building['anchor'] = rect_corner(building['anchor'],
                                             plan.width, plan.height)
            building['turns'] = (building['turns'] + 1) % 4
            # Local deck coordinates are relative to their *building*, not
            # to the global prefab bounding box, so transform separately.
            for floor in result['interior_floors']:
                if floor['structure_id'] == building['id']:
                    for tile in floor['tiles']:
                        x, y = tile['pos']
                        tile['pos'] = [plan.height - 1 - y, x]
                    floor['tiles'].sort(key=lambda t: (t['pos'][1], t['pos'][0]))
            if 'appearance' in building and 'windows' in building['appearance']:
                building['appearance']['windows'] = [
                    [plan.height - 1 - y, x]
                    for x, y in building['appearance']['windows']]
        for actor in result['units']:
            w, h = actor.get('footprint', (1, 1))
            actor['pos'] = rect_corner(actor['pos'], w, h)
            if 'footprint' in actor:
                actor['footprint'] = [h, w]
            actor['patrol_route'] = [point(p)
                                     for p in actor.get('patrol_route', ())]
            if actor.get('facing') in ('north', 'east', 'south', 'west'):
                actor['facing'] = {'north': 'east', 'east': 'south',
                                   'south': 'west', 'west': 'north'}[actor['facing']]
        for obj in result['objects']:
            obj['pos'] = point(obj['pos'])
            if obj['kind'] == 'defense':
                obj['cells'] = [point(c) for c in obj['cells']]
            if obj['kind'] == 'passage':
                obj['destination'] = point(obj['destination'])
        for link in result['level_links']:
            for endpoint in ('from', 'to'):
                level, x, y = link[endpoint]
                link[endpoint] = [level, *point((x, y))]
        result['size'] = [height, width]
    return _validate_prefab(result)

"""3.7.32B — optional visual architecture details on existing structure identities.

Visual metadata is strictly local to Maison/Tour: it never changes tactical
collision, gameplay stair links, roof visibility flags or the board schema.
"""
from copy import deepcopy

from .iso_structures import structure_template
from .map_authoring import _cell, _mission
from .model import Content, require

FACADES = ('pierre', 'torchis', 'brique')
ROOFS = ('tuiles', 'ardoise', 'plat')
DEFAULT_APPEARANCE = {'facade': 'pierre', 'roof': 'tuiles', 'windows': []}
BUILDINGS = frozenset(('Maison', 'Tour'))


def exterior_wall_cells(structure):
    """Candidate *local* window cells from the authoritative structure preset."""
    clip = structure_template(structure['name'], structure['turns'],
                              door_slot=structure['door_slot'])
    found = []
    for (x, y), tile in zip(clip.offsets, clip.terrain):
        if (tile.get('blocked', False) and tile.get('feature') == 'stone_wall'
                and (x in (0, clip.width - 1) or y in (0, clip.height - 1))):
            found.append((x, y))
    return tuple(found)


def validate_building_appearance(structure):
    """Validate optional record-local data; legacy structures need no upgrade."""
    details = structure.get('appearance')
    if details is None:
        return
    require(structure['name'] in BUILDINGS,
            'Only houses and towers support custom facades and roofs')
    require(type(details) is dict
            and set(details) == {'facade', 'roof', 'windows'},
            'Invalid building appearance fields')
    require(type(details['facade']) is str and details['facade'] in FACADES,
            'Unknown facade material')
    require(type(details['roof']) is str and details['roof'] in ROOFS,
            'Unknown roof profile')
    windows = details['windows']
    require(type(windows) is list and len(windows) <= 32,
            'Invalid building windows')
    possible = set(exterior_wall_cells(structure))
    seen = set()
    for cell in windows:
        require(type(cell) is list and len(cell) == 2
                and all(type(x) is int for x in cell),
                'Expected local window cell [x, y]')
        point = tuple(cell)
        require(point in possible and point not in seen,
                'Window must occupy a unique exterior wall')
        seen.add(point)


def building_appearance(structure):
    """Read visual settings without mutating a historic structure record."""
    validate_building_appearance(structure)
    return deepcopy(structure.get('appearance', DEFAULT_APPEARANCE))


def _record(data, mission_id, structure_id):
    mission = _mission(data, mission_id)
    require(type(structure_id) is str and bool(structure_id),
            'Select a persistent building')
    item = next((r for r in mission.get('structures', ())
                 if r['id'] == structure_id), None)
    require(item is not None, 'Unknown authored building')
    require(item['name'] in BUILDINGS,
            'Only houses and towers support custom facades and roofs')
    return item


def edit_building_appearance(data, mission_id, structure_id, *,
                             facade=None, roof=None):
    """Single validated content change, suitable for Document.replace/undo."""
    require(facade is not None or roof is not None,
            'Choose a facade or roof modification')
    updated = deepcopy(data)
    item = _record(updated, mission_id, structure_id)
    settings = building_appearance(item)
    if facade is not None:
        settings['facade'] = facade
    if roof is not None:
        settings['roof'] = roof
    item['appearance'] = settings
    return Content.from_dict(updated).to_dict()


def set_building_window(data, mission_id, structure_id, cell, *, present=True):
    """Decorative opening in a wall; no implicit tactical breach or teleport."""
    require(type(present) is bool, 'Window presence must be boolean')
    updated = deepcopy(data)
    item = _record(updated, mission_id, structure_id)
    target = _cell(_mission(updated, mission_id), cell)
    x0, y0 = item['anchor']
    local = (target[0] - x0, target[1] - y0)
    require(local in exterior_wall_cells(item),
            'Click an exterior wall, not a door, floor or roof')
    settings = building_appearance(item)
    windows = {tuple(p) for p in settings['windows']}
    if present:
        windows.add(local)
    else:
        windows.discard(local)
    settings['windows'] = [list(p) for p in sorted(windows, key=lambda p: (p[1], p[0]))]
    item['appearance'] = settings
    return Content.from_dict(updated).to_dict()


def rotated_appearance(structure, new_name, new_turns, new_door_slot):
    """Preserve visual details across structure edits, rotating local windows.

    A different footprint/template must still accept every window explicitly;
    reject impossible transformations instead of silently deleting details.
    """
    if 'appearance' not in structure:
        return None
    details = building_appearance(structure)
    prior = structure_template(structure['name'], structure['turns'],
                               door_slot=structure['door_slot'])
    width, height = prior.width, prior.height
    steps = (new_turns - structure['turns']) % 4 if new_name == structure['name'] else 0
    windows = [tuple(p) for p in details['windows']]
    for _ in range(steps):
        windows = [(height - 1 - y, x) for x, y in windows]
        width, height = height, width
    details['windows'] = [list(p) for p in sorted(windows, key=lambda p: (p[1], p[0]))]
    candidate = {'name': new_name, 'turns': new_turns,
                 'door_slot': new_door_slot, 'appearance': details}
    validate_building_appearance(candidate)
    return details

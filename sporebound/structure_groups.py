"""Atomic multi-structure authoring built on the existing structure operations.

The Map Editor already selects tiles. Only full structure footprints qualify for
group moves, to avoid silently editing a half-selected adjacent building.
No Tk import, no new serialization schema and no duplicate tactical renderer.
"""
from copy import deepcopy

from .iso_architecture import architecture_instances
from .iso_structures import (place_structure, structure_template,
                             structure_footprint, validate_structure_placement)
from .map_authoring import _mission, selected_cells
from .model import Content, require


def selected_structures(data, mission_id, cells):
    """Select persistent or legacy structures entirely inside given tiles."""
    selected = set(selected_cells(data, mission_id, cells))
    mission = Content.from_dict(data).missions[mission_id]
    candidates = architecture_instances(mission.board, mission.structures)
    return tuple(sorted((item for item in candidates
                         if item.cells.issubset(selected)),
                        key=lambda item: (item.anchor[1], item.anchor[0],
                                          item.name, item.id)))


def transform_structure_group(data, mission_id, cells, dx, dy, *,
                              duplicate=False):
    """Translate/copy all selected structures as one validated transaction.

    Removing all original footprints up front allows adjacent buildings to
    move together or partially overlap their previous positions. Validation
    covers all destinations before any new stamp is applied.
    """
    require(type(dx) is int and type(dy) is int, 'Expected integer group offset')
    require(type(duplicate) is bool, 'Invalid group duplicate flag')
    require(not duplicate or (dx, dy) != (0, 0),
            'Duplicating onto the same structures is not allowed')
    originals = selected_structures(data, mission_id, cells)
    require(bool(originals), 'Select the complete footprint of a structure')
    require(len(originals) <= 128, 'Select at most 128 structures per operation')
    if not duplicate and (dx, dy) == (0, 0):
        return deepcopy(data)
    prepared = deepcopy(data)
    mission = _mission(prepared, mission_id)
    if not duplicate:
        old_cells = set().union(*(item.cells for item in originals))
        ids = {item.id for item in originals if item.id}
        mission['structures'] = [
            record for record in mission.get('structures', ())
            if record['id'] not in ids]
        mission['board']['tiles'] = [
            tile for tile in mission['board']['tiles']
            if tuple(tile['pos']) not in old_cells]
    scene = Content.from_dict(prepared).missions[mission_id]
    occupied = set()
    for item in architecture_instances(scene.board, scene.structures):
        occupied.update(item.cells)
    anchors = []
    for item in originals:
        new_anchor = (item.anchor[0] + dx, item.anchor[1] + dy)
        clip = structure_template(item.name, item.turns,
                                  door_slot=item.door_slot)
        new_cells = set(structure_footprint(clip, new_anchor))
        validate_structure_placement(prepared, mission_id, clip, new_anchor)
        require(not occupied.intersection(new_cells),
                'Structure group overlaps another structure')
        occupied.update(new_cells)
        anchors.append(new_anchor)

    result = prepared
    for item, new_anchor in zip(originals, anchors):
        result = place_structure(result, mission_id, item.name, new_anchor,
                                 item.turns, door_slot=item.door_slot)
        if not duplicate and item.id:
            _mission(result, mission_id)['structures'][-1]['id'] = item.id
    return Content.from_dict(result).to_dict()

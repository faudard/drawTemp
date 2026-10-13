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

    Restoring all saved original underlays first allows adjacent buildings to
    move together or partially overlap their previous positions. Validation
    covers all destinations before any new stamp is applied.
    """
    require(type(dx) is int and type(dy) is int, 'Expected integer group offset')
    require(type(duplicate) is bool, 'Invalid group duplicate flag')
    require(not duplicate or (dx, dy) != (0, 0),
            'Duplicating onto the same structures is not allowed')
    originals = selected_structures(data, mission_id, cells)
    require(bool(originals), 'Select the complete footprint of a structure')
    # Group transformation does not yet remap per-building tactical stair
    # endpoints. Reject rather than silently keeping them at old positions.
    moving_ids = {row.id for row in originals if row.id}
    mission_raw = _mission(data, mission_id)
    require(not any(f['structure_id'] in moving_ids
                    for f in mission_raw.get('interior_floors', ())),
            'Move buildings with authored floors individually until group floor remapping is supported')
    require(len(originals) <= 128, 'Select at most 128 structures per operation')
    if not duplicate and (dx, dy) == (0, 0):
        return deepcopy(data)
    prepared = deepcopy(data)
    mission = _mission(prepared, mission_id)
    if not duplicate:
        from .structure_underlay import restore_footprint
        # Restore ALL source grounds before capturing any destination.
        # This preserves river/road tiles during partially overlapping moves
        # and avoids saving an adjacent building stamp as the new underlay.
        for item in originals:
            restore_footprint(mission, item)
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

"""R6.10: canonical building-door authoring and deterministic runtime actions.

A door is an existing mission object, not a new structure/terrain schema.
The ground Battle board owns collision; the object owns persistent door state.
"""
from copy import deepcopy

from .iso_structures import structure_template
from .model import Content, require, distance


def add_building_door(data, mission_id, structure_id, *, opened=False, locked=False):
    """Place a gameplay door on the existing building template entry.

    The decorative door visual remains separate. This only adds the ordinary
    object already understood by Battle and the Player.
    """
    require(type(opened) is bool and type(locked) is bool,
            "Door open/locked flags must be boolean")
    updated = deepcopy(data)
    mission = next((m for m in updated["missions"] if m["id"] == mission_id), None)
    require(mission is not None, "Unknown mission")
    structure = next((s for s in mission.get("structures", [])
                      if s["id"] == structure_id), None)
    require(structure is not None, "Unknown structure")
    clip = structure_template(structure["name"], structure["turns"],
                              door_slot=structure["door_slot"])
    entrances = [(structure["anchor"][0] + xy[0],
                  structure["anchor"][1] + xy[1])
                 for xy, tile in zip(clip.offsets, clip.terrain)
                 if tile.get("surface") == "cobble" and not tile.get("blocked")]
    require(len(entrances) == 1, "Structure has no unique walkable entrance")
    cell = entrances[0]
    require(not any(tuple(o["pos"]) == cell for o in mission.get("objects", [])),
            "An object already occupies the building entrance")
    require(not any(tuple(u["pos"]) == cell
                    for u in mission["units"]
                    if mission.get("unit_levels", {}).get(u["id"], 0) == 0),
            "A unit occupies the entrance")
    names = {o["id"] for o in mission.get("objects", [])}
    candidate = "building_door_" + structure_id
    i = 2
    while candidate in names:
        candidate = "building_door_" + structure_id + "_" + str(i)
        i += 1
    require(len(candidate) <= 64, "Building door identifier too long")
    mission.setdefault("objects", []).append({
        "id": candidate, "kind": "door", "pos": list(cell),
        "open": opened, "locked": locked})
    return Content.from_dict(updated).to_dict()


def toggle_door(battle, unit, object_id):
    """Open/close an ordinary door as a turn action with atomic Battle.execute.

    Closing is forbidden on an occupied ground cell. Upper-floor actors do not
    interact across ceilings. Locked siege gates cannot be opened this way.
    """
    require(type(object_id) is str and bool(object_id), "Choose a door ID")
    require(unit.alive and not unit.acted and not battle.status_blocks(unit, "act"),
            "Action unavailable")
    require(battle.unit_levels.get(unit.id, 0) == 0,
            "Door interaction requires ground-floor access")
    require(unit.team == "player", "Only players can operate building doors")
    door = next((o for o in battle.mission.objects if o["id"] == object_id
                 and o["kind"] == "door"), None)
    require(door is not None, "Unknown door")
    require(min(distance(c, tuple(door["pos"])) for c in unit.occupied_cells()) <= 1,
            "Door out of reach")
    require(not door.get("locked", False), "Door locked")
    new_state = not door.get("open", False)
    if not new_state:
        target = tuple(door["pos"])
        require(not any(other.alive and
                        battle.unit_levels.get(other.id, 0) == 0 and
                        target in other.occupied_cells()
                        for other in battle.units),
                "Cannot close a door on a unit")
    door["open"] = new_state
    pos = tuple(door["pos"])
    battle.board.tiles[pos].blocked = not new_state
    unit.acted = True
    if unit.cast:
        battle.emit("cast_cancelled", unit=unit.id)
    unit.cast = None
    battle.emit("door_state", unit=unit.id, door=object_id,
                pos=list(pos), open=new_state)

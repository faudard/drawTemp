"""R27.B opt-in puzzle interactions using the *existing* Mission.objects.

No secondary state store: key collection, sequence cursors, block coordinates
and pressure plate latches live in objects already included in Battle recording,
digest and GameSession snapshots. Legacy doors/switches follow their old path.
"""
from __future__ import annotations

from .model import RuleError, distance, require

PUZZLE_KINDS = frozenset({"key", "plate", "block"})
MAX_PUZZLE_OBJECTS = 64


def validate_puzzles(mission):
    """Validate cross-references before any Player loads the mission."""
    objects = mission.objects
    by_id = {obj["id"]: obj for obj in objects}
    special = [obj for obj in objects if obj["kind"] in PUZZLE_KINDS]
    require(len(special) <= MAX_PUZZLE_OBJECTS, "Too many dungeon puzzle objects")
    for obj in special:
        require(set(obj) <= ({"id", "kind", "pos", "link", "latch", "used"}
                           if obj["kind"] == "plate" else
                           {"id", "kind", "pos", "link", "used"}
                           if obj["kind"] == "key" else
                           {"id", "kind", "pos"}),
                "Unknown R27 puzzle object fields")
        require(not mission.board.tile(tuple(obj["pos"])).blocked,
                "Puzzle object must be on walkable terrain")
        if obj["kind"] == "block":
            require(not any(obj["pos"] == other["pos"] for other in objects
                            if other is not obj and other["kind"] != "plate"),
                    "Block overlaps an interactive object")
            require(not any(tuple(obj["pos"]) in unit.occupied_cells()
                            for unit in mission.units),
                    "Block overlaps an actor spawn")
        else:
            require("link" in obj and
                    obj["link"] in by_id and by_id[obj["link"]]["kind"] == "door",
                    "Key/plate must reference an existing door")
            if "used" in obj:
                require(type(obj["used"]) is bool,
                        "Puzzle used flag must be boolean")
            if obj["kind"] == "plate":
                require(type(obj.get("latch", True)) is bool,
                        "Plate latch must be boolean")
    for door in (o for o in objects if o["kind"] == "door"):
        has_key = "key" in door
        has_sequence = "sequence" in door
        linked_plates = [o for o in objects if o["kind"] == "plate"
                         and o["link"] == door["id"]]
        if has_key:
            key = by_id.get(door["key"])
            require(key is not None and key["kind"] == "key" and
                    key["link"] == door["id"],
                    "Door key must reference a matching authored key object")
        if has_sequence:
            seq = door["sequence"]
            require(isinstance(seq, list) and 2 <= len(seq) <= 8
                    and len(seq) == len(set(seq))
                    and all(type(s) is str and s in by_id
                            and by_id[s]["kind"] == "switch"
                            and by_id[s].get("link") == door["id"] for s in seq),
                    "Door sequence needs 2..8 unique linked switches")
            require(type(door.get("reset_on_error", True)) is bool,
                    "Invalid sequence reset policy")
            require(type(door.get("sequence_progress", 0)) is int and
                    0 <= door.get("sequence_progress", 0) <= len(seq),
                    "Invalid sequence cursor")
            require(all(o["id"] in seq for o in objects
                        if o["kind"] == "switch" and o.get("link") == door["id"]),
                    "Every linked switch must be in the door sequence")
        linked_switches = [o for o in objects
                           if o["kind"] == "switch"
                           and o.get("link") == door["id"]]
        require(not ((has_key and (has_sequence or linked_plates or linked_switches))
                     or (has_sequence and linked_plates)
                     or (linked_plates and linked_switches)),
                "Use one gate policy per door: key, sequence, plates or legacy lever")
    for key in (o for o in objects if o["kind"] == "key"):
        require(by_id[key["link"]].get("key") == key["id"],
                "Every authored key must be bound to its door")
    for block in (o for o in objects if o["kind"] == "block"):
        require(not any(block is not other and other["kind"] == "block" and
                        other["pos"] == block["pos"] for other in objects),
                "Overlapping puzzle blocks")


def interact(battle, unit, obj):
    """Handle optional key/sequence puzzles and preserve legacy door behaviour.

    Returns whether the object is consumed (used=True) by this interaction.
    All mutations are inside Battle.execute's existing atomic boundary.
    """
    kind = obj["kind"]
    if kind == "key":
        battle.emit("puzzle_key_collected", unit=unit.id, key=obj["id"])
        return True
    if kind == "door":
        key_id = obj.get("key")
        if key_id:
            key = next(o for o in battle.mission.objects if o["id"] == key_id)
            require(key.get("used", False),
                    "A corresponding dungeon key must be collected")
        else:
            require(not obj.get("locked", False),
                    "Gate locked: use a siege engine or its switch")
        require(not obj.get("open", False), "Door already open")
        open_door(battle, obj)
        if key_id:
            battle.emit("puzzle_key_door", door=obj["id"], key=key_id)
        return True
    require(kind == "switch", "Unsupported puzzle interaction")
    door = next(o for o in battle.mission.objects if o["id"] == obj["link"])
    if "sequence" not in door:
        # Exact historical single-lever semantics (including no extra event).
        door["open"] = True
        battle.board.tiles[tuple(door["pos"])].blocked = False
        return True
    sequence = door["sequence"]
    index = door.get("sequence_progress", 0)
    if index >= len(sequence):
        raise RuleError("Sequence was already solved")
    if obj["id"] != sequence[index]:
        require(door.get("reset_on_error", True),
                "Wrong sequence step; reset is disabled")
        door["sequence_progress"] = 0
        for switch_id in sequence:
            next(o for o in battle.mission.objects
                 if o["id"] == switch_id)["used"] = False
        battle.emit("puzzle_sequence_reset", door=door["id"],
                    switch=obj["id"])
        return False
    door["sequence_progress"] = index + 1
    battle.emit("puzzle_sequence_step", door=door["id"],
                switch=obj["id"], step=index + 1)
    if index + 1 == len(sequence):
        open_door(battle, door)
    return True


def open_door(battle, door):
    if door.get("open", False):
        return
    door["open"] = True
    battle.board.tiles[tuple(door["pos"])].blocked = False


def sync_plates(battle):
    """Pressure plates respond to physical actors/blocks at each movement step."""
    plates = [o for o in battle.mission.objects if o["kind"] == "plate"]
    if not plates:
        return
    blocks = {tuple(o["pos"]) for o in battle.mission.objects
              if o["kind"] == "block"}
    by_door = {}
    for plate in plates:
        pos = tuple(plate["pos"])
        present = pos in blocks or any(
            u.alive and battle.unit_levels.get(u.id, 0) == 0
            and pos in u.occupied_cells() for u in battle.units)
        latched = plate.get("used", False)
        if present and not latched:
            battle.emit("puzzle_plate_pressed", plate=plate["id"])
        plate["used"] = bool(present or (latched and plate.get("latch", True)))
        by_door.setdefault(plate["link"], []).append(plate)
    for door_id in sorted(by_door):
        door = next(o for o in battle.mission.objects if o["id"] == door_id)
        satisfied = all(o.get("used", False) for o in by_door[door_id])
        if satisfied:
            open_door(battle, door)
        elif door.get("open", False):
            # Do not close a door on top of an actor or moving block.
            cell = tuple(door["pos"])
            if (cell not in blocks and
                    not any(u.alive and cell in u.occupied_cells()
                            for u in battle.units)):
                door["open"] = False
                battle.board.tiles[cell].blocked = True
                battle.emit("puzzle_gate_closed", door=door_id)


def push_block(battle, unit, obj_id, direction):
    """Push exactly one tile in a cardinal direction via authenticated command."""
    require(unit.team == "player" and not unit.acted
            and not battle.status_blocks(unit, "act"),
            "Push action unavailable")
    require(isinstance(direction, (list, tuple)) and len(direction) == 2
            and all(type(n) is int for n in direction)
            and tuple(direction) in {(1, 0), (-1, 0), (0, 1), (0, -1)},
            "Push requires cardinal unit direction")
    block = next((o for o in battle.mission.objects
                  if o["id"] == obj_id and o["kind"] == "block"), None)
    require(block is not None, "Unknown puzzle block")
    src = tuple(block["pos"])
    dx, dy = direction
    require((unit.pos[0] + dx, unit.pos[1] + dy) == src
            and battle.unit_levels.get(unit.id, 0) == 0,
            "Stand directly behind the puzzle block")
    dst = (src[0] + dx, src[1] + dy)
    require(battle.board.contains(dst) and not battle.board.tile(dst).blocked,
            "Puzzle block destination blocked")
    require(not any(u.alive and dst in u.occupied_cells() for u in battle.units),
            "Puzzle block destination occupied by actor")
    require(not any(tuple(o["pos"]) == dst and
                    o["kind"] != "plate" for o in battle.mission.objects
                    if o is not block),
            "Puzzle block destination occupied by an object")
    block["pos"] = list(dst)
    unit.acted = True
    unit.cast = None
    battle.emit("puzzle_block_push", unit=unit.id, block=obj_id,
                start=list(src), end=list(dst))
    sync_plates(battle)

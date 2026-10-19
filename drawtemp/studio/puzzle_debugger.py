"""R27.B bounded symbolic puzzle debugger (no independent game-state owner).

Search models only authored key/sequence/lever/plate/block interactions and
four-direction, single-hero movement. It returns an explicit *inconclusive*
status for unsupported mechanics, not a false safety certificate.
"""
from __future__ import annotations

from collections import deque

from drawtemp.core import RuleError

MAX_DOORS = 8
MAX_KEYS = 8
MAX_SWITCHES = 8
MAX_PLATES = 8
MAX_BLOCKS = 4


def analyze_puzzle(mission, *, state_budget=50000):
    if type(state_budget) is not int or not 1 <= state_budget <= 500000:
        raise RuleError("Invalid puzzle state budget")
    objects = mission["objects"]
    doors = sorted((o for o in objects if o["kind"] == "door"), key=lambda o: o["id"])
    keys = sorted((o for o in objects if o["kind"] == "key"), key=lambda o: o["id"])
    switches = sorted((o for o in objects if o["kind"] == "switch"), key=lambda o: o["id"])
    plates = sorted((o for o in objects if o["kind"] == "plate"), key=lambda o: o["id"])
    blocks = sorted((o for o in objects if o["kind"] == "block"), key=lambda o: o["id"])
    goals = [list(g) for g in mission.get("goal", [])]
    limits = ((doors, MAX_DOORS, "doors"), (keys, MAX_KEYS, "keys"),
              (switches, MAX_SWITCHES, "switches"), (plates, MAX_PLATES, "plates"),
              (blocks, MAX_BLOCKS, "blocks"))
    for entries, limit, label in limits:
        if len(entries) > limit:
            return {"complete": False, "states": 0, "reachable_goals": [],
                    "unreachable_goals": goals, "unreachable_objects": [],
                    "warnings": [f"Analysis limited to {limit} {label}"],
                    "witness": []}
    door_bits = {o["id"]: 1 << i for i, o in enumerate(doors)}
    key_bits = {o["id"]: 1 << i for i, o in enumerate(keys)}
    switch_bits = {o["id"]: 1 << i for i, o in enumerate(switches)}
    plate_bits = {o["id"]: 1 << i for i, o in enumerate(plates)}
    door_at = {tuple(o["pos"]): o for o in doors}
    tiles = {tuple(t["pos"]): t for t in mission["board"]["tiles"]}
    dimensions = (mission["board"]["width"], mission["board"]["height"])
    starts = [tuple(u["pos"]) for u in mission["units"] if u["team"] == "player"]
    if not starts:
        return {"complete": False, "states": 0, "reachable_goals": [],
                "unreachable_goals": goals, "unreachable_objects": [],
                "warnings": ["No player spawn"], "witness": []}
    initial_doors = sum(door_bits[o["id"]] for o in doors if o.get("open", False))
    initial_keys = sum(key_bits[o["id"]] for o in keys if o.get("used", False))
    initial_switches = sum(switch_bits[o["id"]] for o in switches if o.get("used", False))
    initial_plates = sum(plate_bits[o["id"]] for o in plates if o.get("used", False))
    initial_sequence = tuple(o.get("sequence_progress", 0) for o in doors)
    initial_blocks = tuple(tuple(o["pos"]) for o in blocks)

    def pressed(plate, hero, positions, latched):
        idx = plates.index(plate)
        on = hero == tuple(plate["pos"]) or tuple(plate["pos"]) in positions
        return on or (plate.get("latch", True) and bool(latched & (1 << idx)))

    def normalized(state):
        pos, opened, collected, switches_used, cursors, positions, latched = state
        new_latched = latched
        for i, plate in enumerate(plates):
            if pos == tuple(plate["pos"]) or tuple(plate["pos"]) in positions:
                new_latched |= 1 << i
            elif not plate.get("latch", True):
                new_latched &= ~(1 << i)
        for door in doors:
            own = [p for p in plates if p["link"] == door["id"]]
            if own:
                bit = door_bits[door["id"]]
                if all(pressed(p, pos, positions, new_latched) for p in own):
                    opened |= bit
                elif pos != tuple(door["pos"]) and tuple(door["pos"]) not in positions:
                    opened &= ~bit
        return pos, opened, collected, switches_used, cursors, positions, new_latched

    def passable(cell, opened, positions):
        x, y = cell
        if x < 0 or y < 0 or x >= dimensions[0] or y >= dimensions[1]:
            return False
        if cell in positions:
            return False
        door = door_at.get(cell)
        if door is not None:
            return bool(opened & door_bits[door["id"]])
        return not tiles.get(cell, {}).get("blocked", False)

    queue = deque()
    seen = set()
    parents = {}
    for pos in starts:
        state = normalized((pos, initial_doors, initial_keys, initial_switches,
                            initial_sequence, initial_blocks, initial_plates))
        if passable(pos, state[1], state[5]) and state not in seen:
            seen.add(state)
            parents[state] = (None, "spawn")
            queue.append(state)
    visited_cells, available_objects = set(), set()
    found = {}

    def enqueue(parent, candidate, action):
        updated = normalized(candidate)
        if updated not in seen and len(seen) < state_budget:
            seen.add(updated)
            parents[updated] = (parent, action)
            queue.append(updated)

    while queue:
        state = queue.popleft()
        pos, opened, collected, switches_used, cursors, block_positions, latched = state
        visited_cells.add(pos)
        if pos in {tuple(g) for g in goals} and pos not in found:
            found[pos] = state
        for index, obj in enumerate(keys):
            target = tuple(obj["pos"])
            if abs(target[0] - pos[0]) + abs(target[1] - pos[1]) <= 1:
                available_objects.add(obj["id"])
                bit = key_bits[obj["id"]]
                if not collected & bit:
                    enqueue(state, (pos, opened, collected | bit, switches_used,
                                    cursors, block_positions, latched),
                            "collect " + obj["id"])
        for door_idx, door in enumerate(doors):
            target = tuple(door["pos"])
            if abs(target[0] - pos[0]) + abs(target[1] - pos[1]) > 1:
                continue
            bit = door_bits[door["id"]]
            if opened & bit:
                continue
            required_key = door.get("key")
            if (required_key and collected & key_bits[required_key]) or (
                    not required_key and not door.get("locked", False)
                    and not door.get("sequence") and
                    not any(p["link"] == door["id"] for p in plates)):
                enqueue(state, (pos, opened | bit, collected, switches_used,
                                cursors, block_positions, latched),
                        "open " + door["id"])
        for sw in switches:
            target = tuple(sw["pos"])
            if abs(target[0] - pos[0]) + abs(target[1] - pos[1]) > 1:
                continue
            available_objects.add(sw["id"])
            bit = switch_bits[sw["id"]]
            if switches_used & bit:
                continue
            door = next(o for o in doors if o["id"] == sw["link"])
            if "sequence" not in door:
                enqueue(state, (pos, opened | door_bits[door["id"]],
                                collected, switches_used | bit, cursors,
                                block_positions, latched), "activate " + sw["id"])
                continue
            index = doors.index(door)
            seq = door["sequence"]
            progress = cursors[index]
            steps = list(cursors)
            if progress < len(seq) and sw["id"] == seq[progress]:
                steps[index] = progress + 1
                new_open = opened | (door_bits[door["id"]]
                                     if steps[index] == len(seq) else 0)
                enqueue(state, (pos, new_open, collected, switches_used | bit,
                                tuple(steps), block_positions, latched),
                        "sequence " + sw["id"])
            elif progress < len(seq) and door.get("reset_on_error", True):
                steps[index] = 0
                reset_mask = switches_used
                for swid in seq:
                    reset_mask &= ~switch_bits[swid]
                enqueue(state, (pos, opened, collected, reset_mask,
                                tuple(steps), block_positions, latched),
                        "reset " + door["id"])
        for obj in objects:
            if obj["kind"] == "chest":
                target = tuple(obj["pos"])
                if abs(target[0] - pos[0]) + abs(target[1] - pos[1]) <= 1:
                    available_objects.add(obj["id"])
        for i, block in enumerate(blocks):
            bx, by = block_positions[i]
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                if (pos[0] + dx, pos[1] + dy) != (bx, by):
                    continue
                available_objects.add(block["id"])
                nxt = (bx + dx, by + dy)
                if (passable(nxt, opened, block_positions)
                        and not any(tuple(o["pos"]) == nxt and o["kind"] not in
                                    ("plate", "block") for o in objects)):
                    moved = list(block_positions)
                    moved[i] = nxt
                    enqueue(state, (pos, opened, collected, switches_used,
                                    cursors, tuple(moved), latched),
                            "push " + block["id"] + " " + str(nxt))
        x, y = pos
        for nxt in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if passable(nxt, opened, block_positions):
                enqueue(state, (nxt, opened, collected, switches_used,
                                cursors, block_positions, latched),
                        "walk " + str(nxt))

    # State limit is a hard cap, including candidates not enqueued once full.
    # Saturation cannot prove completeness; report conservative uncertainty.
    saturated = len(seen) >= state_budget
    solved = [g for g in goals if tuple(g) in visited_cells]
    missing = [g for g in goals if tuple(g) not in visited_cells]
    missing_objects = sorted(o["id"] for o in objects
                             if o["kind"] in ("switch", "key", "chest", "block")
                             and o["id"] not in available_objects)
    warnings = []
    if saturated:
        warnings.append("State budget reached; analysis inconclusive")
    if len(starts) != 1:
        warnings.append("Multiple player spawns analyzed independently; no coordination proof")
    if any(u["team"] == "enemy" for u in mission["units"]):
        warnings.append("Enemy AI and combat are not modeled")
    if any(u.get("footprint", (1, 1)) != [1, 1]
           and tuple(u.get("footprint", (1, 1))) != (1, 1)
           for u in mission["units"] if u["team"] == "player"):
        warnings.append("Multicell hero footprints not modeled")
    if any(o["kind"] not in ("door", "switch", "chest", "key", "plate", "block")
           for o in objects):
        warnings.append("Additional objects/actions not modeled")
    if not goals:
        warnings.append("No authored goal; exit reachability not assessed")
    if missing:
        warnings.append("Unreachable goal cells: " + str(missing))
    if missing_objects:
        warnings.append("Unreachable puzzle objects: " + ", ".join(missing_objects))
    witness = []
    if solved:
        cursor = found[tuple(solved[0])]
        while cursor is not None:
            previous, command = parents[cursor]
            witness.append(command)
            cursor = previous
        witness.reverse()
    complete = not saturated and not any(
        "not modeled" in w or "no coordination" in w for w in warnings)
    return {"complete": complete, "states": len(seen),
            "reachable_goals": solved, "unreachable_goals": missing,
            "unreachable_objects": missing_objects, "warnings": warnings,
            "witness": witness}

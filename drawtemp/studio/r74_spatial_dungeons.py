"""R74.C2: faithfully embed bounded R34 room-graph edges into R5/R27 tiles.

The spatial geometry, lock and key are real canonical Content Mission records.
Only R34's current "room-graph-v1" tree-shaped spine/branches is supported.
Nonrepresentable graphs fail closed; no implied graph edges, door bypasses,
remote services, sidecar map formats or unverified asset dependencies.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.studio.dungeon_authoring import DungeonStudio
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.puzzle_debugger import analyze_puzzle
from .r74_assisted_dungeons import (
    AssistedDungeonController, DungeonAssistError, DungeonSuggestion,
)

ROOM = 5
STEP = 9
MAIN_X = 14
MAIN_Y = 13
UPPER_Y = 3
LOWER_Y = 23
MAX_SPATIAL_ROOMS = 12
_PREFIX = re.compile(r"[a-z][a-z0-9_]{0,11}\Z")


def _digest(value):
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _edges(rooms):
    return {tuple(sorted((room["id"], other)))
            for room in rooms for other in room["neighbors"]}


def _cardinal(cell):
    x, y = cell
    return ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))


def _reachable(start, floors):
    queue = deque([start])
    visited = {start}
    while queue:
        for other in _cardinal(queue.popleft()):
            if other in floors and other not in visited:
                visited.add(other)
                queue.append(other)
    return visited


def _layout_geometry(layout):
    """Place spine on one row and ≤3 leaf branches per parent, without crossings."""
    rooms = layout["rooms"]
    if not 3 <= len(rooms) <= MAX_SPATIAL_ROOMS:
        raise DungeonAssistError(
            "spatial_limit", "R74.C2 supports 3..12 physical rooms per dungeon")
    ids = {row["id"]: row for row in rooms}
    if set(ids) != set(range(len(rooms))):
        raise DungeonAssistError("unsupported_topology", "Non-contiguous R34 IDs")
    goal = next((r["id"] for r in rooms if r["role"] == "goal"), None)
    finish = next((r["id"] for r in rooms if r["role"] == "exit"), None)
    if goal is None or finish != goal + 1 or ids[0]["role"] != "entry":
        raise DungeonAssistError("unsupported_topology", "Invalid R34 spine roles")
    main = finish + 1
    expected = {(i, i + 1) for i in range(main - 1)}
    branches = {}
    for index in range(main, len(rooms)):
        parents = [p for p in ids[index]["neighbors"] if p < goal]
        if len(parents) != 1 or len(ids[index]["neighbors"]) != 1:
            raise DungeonAssistError("unsupported_topology", "Only leaf branches supported")
        parent = parents[0]
        expected.add((parent, index))
        branches.setdefault(parent, []).append(index)
    if _edges(rooms) != expected:
        raise DungeonAssistError("unsupported_topology", "Unrepresented room graph edges")

    positions = {i: (MAIN_X + STEP * i, MAIN_Y) for i in range(main)}
    for parent, children in branches.items():
        if len(children) > (3 if parent == 0 else 2):
            raise DungeonAssistError("unsupported_topology", "Branch socket capacity")
        sockets = [(MAIN_X + STEP * parent, UPPER_Y),
                   (MAIN_X + STEP * parent, LOWER_Y)]
        if parent == 0:
            sockets.append((MAIN_X - STEP, MAIN_Y))
        for child, cell in zip(sorted(children), sockets):
            positions[child] = cell
    if len(positions) != len(rooms):
        raise DungeonAssistError("unsupported_topology", "Unplaced R34 room")
    width = max(x + ROOM for x, _ in positions.values()) + 3
    height = max(y + ROOM for _, y in positions.values()) + 3
    if width > 128 or height > 128:
        raise DungeonAssistError("spatial_limit", "R5 board exceeds 128 cells")

    room_cells = {i: {(x + dx, y + dy) for dx in range(ROOM)
                      for dy in range(ROOM)}
                  for i, (x, y) in positions.items()}
    corridors = {}
    for a, b in sorted(expected):
        x, y = positions[a]
        xx, yy = positions[b]
        if x == xx and y != yy:
            top = min(y, yy)
            floor = {(x + 2, py)
                     for py in range(top + ROOM, max(y, yy))}
        elif y == yy and x != xx:
            left = min(x, xx)
            floor = {(px, y + 2)
                     for px in range(left + ROOM, max(x, xx))}
        else:
            raise DungeonAssistError("unsupported_topology", "Diagonal room edge")
        if not floor:
            raise DungeonAssistError("unsupported_topology", "No corridor separation")
        corridors[(a, b)] = floor
    floor = set().union(*room_cells.values(), *corridors.values())

    # Independent corridor connectivity proof: mask all room cells, then each
    # corridor component must touch exactly the authored pair, never a third.
    room_ownership = {cell: rid for rid, cells in room_cells.items()
                      for cell in cells}
    remaining = set().union(*corridors.values())
    inferred = set()
    while remaining:
        start = min(remaining)
        component = _reachable(start, remaining)
        remaining.difference_update(component)
        touched = {room_ownership[neighbor]
                   for cell in component for neighbor in _cardinal(cell)
                   if neighbor in room_ownership}
        if len(touched) != 2:
            raise DungeonAssistError(
                "spatial_parity_failed", "Corridor touches wrong number of rooms")
        inferred.add(tuple(sorted(touched)))
    if inferred != expected or len(inferred) != len(corridors):
        raise DungeonAssistError(
            "spatial_parity_failed", "Physical corridor edges differ from R34")
    for i, neighbors in ((r["id"], set(r["neighbors"])) for r in rooms):
        if {b if a == i else a for a, b in inferred if i in (a, b)} != neighbors:
            raise DungeonAssistError("spatial_parity_failed", "Room adjacency drift")
    return {
        "width": width, "height": height, "positions": positions,
        "room_cells": room_cells, "corridors": corridors,
        "floors": floor, "edges": expected,
        "main": main, "goal_room": goal, "exit_room": finish,
    }


def _physical_mission(mission, proposal, geometry, index):
    """Modify a detached *canonical* R5 mission, not a parallel tileset."""
    layout = proposal.layout
    rooms = {r["id"]: r for r in layout["rooms"]}
    width, height = geometry["width"], geometry["height"]
    floor = geometry["floors"]
    locks = layout["locks"]
    door_cells = {}
    objects = []
    for lock in locks:
        edge = tuple(sorted((lock["a"], lock["b"])))
        if edge not in geometry["corridors"] or lock["key"] != "goal_key":
            raise DungeonAssistError("unsupported_lock", "Unknown lock or key")
        corridor = sorted(geometry["corridors"][edge])
        cell = corridor[len(corridor) // 2]
        if cell in door_cells:
            raise DungeonAssistError("unsupported_lock", "Overlapping doors")
        door_cells[cell] = edge
        objects.append({
            "id": "r74_goal_door", "kind": "door",
            "pos": list(cell), "locked": True, "key": "r74_goal_key",
        })
    key_rooms = [r for r in layout["rooms"] if "goal_key" in r["keys"]]
    if bool(locks) != bool(key_rooms) or len(key_rooms) > 1:
        raise DungeonAssistError("unsupported_lock", "Missing or ambiguous R34 key")
    key_cell = None
    if key_rooms:
        rx, ry = geometry["positions"][key_rooms[0]["id"]]
        key_cell = (rx + 2, ry + 2)
        objects.append({
            "id": "r74_goal_key", "kind": "key", "pos": list(key_cell),
            "link": "r74_goal_door",
        })

    # No default walkable void: every uncarved cell is an actual R5 wall.
    mission["board"]["tiles"] = [
        {
            "pos": [x, y], "surface": "stone",
            "feature": "" if (x, y) in floor else "stone_wall",
            "blocked": (x, y) not in floor or (x, y) in door_cells,
        }
        for y in range(height) for x in range(width)
    ]
    # Keep chest decoration conservative; resource budgets are not claimed
    # to match R34 until R74.C3's encounter/loot materialization gate.
    occupied = {tuple(o["pos"]) for o in objects}
    entry = geometry["positions"][0]
    goal = geometry["positions"][geometry["goal_room"]]
    exit_room = geometry["positions"][geometry["exit_room"]]
    spawn = (entry[0] + 2, entry[1] + 2)
    exit_cell = (exit_room[0] + 2, exit_room[1] + 2)
    goal_cell = (goal[0] + 2, goal[1] + 2)
    enemy_cell = (exit_room[0] + 4, exit_room[1])
    occupied.update((spawn, goal_cell, exit_cell, enemy_cell))
    for room in layout["rooms"]:
        if room["loot"] <= 0:
            continue
        x, y = geometry["positions"][room["id"]]
        chest = next(((x + dx, y + dy)
                      for dx, dy in ((1, 1), (3, 3), (1, 3), (3, 1))
                      if (x + dx, y + dy) not in occupied), None)
        if chest is not None:
            objects.append({
                "id": f"r74_chest_{room['id']}", "kind": "chest",
                "pos": list(chest), "amount": min(10000, room["loot"] * 25),
            })
            occupied.add(chest)
    mission["objects"] = objects
    player = next(u for u in mission["units"] if u["team"] == "player")
    enemy = next(u for u in mission["units"] if u["team"] == "enemy")
    player["pos"] = list(spawn)
    player["speed"] = 100
    enemy["pos"] = list(enemy_cell)
    enemy["speed"] = 1
    mission["goal"] = [list(exit_cell)]
    mission["objective"] = "extract"
    mission["reward"] = 40 * (index + 1)
    return {"entry_cell": spawn, "goal_cell": goal_cell,
            "exit_cell": exit_cell, "key_cell": key_cell,
            "door_cells": sorted(door_cells), "geometry": geometry}


def _puzzle_evidence(mission, proposal, generated):
    geometry = generated["geometry"]
    centers = {rid: (x + 2, y + 2)
               for rid, (x, y) in geometry["positions"].items()}
    walkable = set(geometry["floors"]) - set(generated["door_cells"])
    before = _reachable(generated["entry_cell"], walkable)
    if any(centers[room["id"]] not in geometry["floors"]
           for room in proposal.layout["rooms"]):
        raise DungeonAssistError("spatial_parity_failed", "Room center blocked")
    if generated["door_cells"]:
        if generated["goal_cell"] in before or generated["exit_cell"] in before:
            raise DungeonAssistError("lock_bypass", "Key door can be bypassed")
        if generated["key_cell"] not in before:
            raise DungeonAssistError("unreachable_key", "Physical key inaccessible")
    else:
        if generated["exit_cell"] not in before:
            raise DungeonAssistError("route_unproven", "Exit not walkable")
    after = _reachable(generated["entry_cell"], geometry["floors"])
    if any(center not in after for center in centers.values()):
        raise DungeonAssistError("route_unproven", "Not all R34 rooms walkable")

    def check(target):
        detached = deepcopy(mission)
        detached["goal"] = [list(target)]
        report = analyze_puzzle(detached, state_budget=50000)
        allowed = {"Enemy AI and combat are not modeled"}
        witness = report["witness"]
        if (list(target) not in report["reachable_goals"] or
                report["unreachable_goals"] or not witness or
                report["states"] >= 50000 or
                any(w not in allowed for w in report["warnings"])):
            raise DungeonAssistError(
                "physical_route_unproven", "R27 symbolic witness absent/inconclusive")
        if generated["door_cells"] and (
                "collect r74_goal_key" not in witness or
                "open r74_goal_door" not in witness):
            raise DungeonAssistError(
                "physical_route_unproven", "R27 route bypasses goal key/door")
        return {"states": report["states"], "witness": list(witness),
                "warnings": list(report["warnings"])}
    goal_witness = check(generated["goal_cell"])
    exit_witness = check(generated["exit_cell"])
    physical_edges = sorted(map(list, geometry["edges"]))
    expected_edges = sorted(map(list, _edges(proposal.layout["rooms"])))
    if physical_edges != expected_edges:
        raise DungeonAssistError("spatial_parity_failed", "Edge list mismatch")
    return {
        "seed": proposal.seed, "topology_digest": proposal.topology_digest,
        "room_count": len(centers), "physical_edges": physical_edges,
        "r34_edges": expected_edges, "width": geometry["width"],
        "height": geometry["height"],
        "room_centers": {str(rid): list(center) for rid, center in centers.items()},
        "entry": list(generated["entry_cell"]),
        "goal": list(generated["goal_cell"]),
        "exit": list(generated["exit_cell"]),
        "key": None if generated["key_cell"] is None else list(generated["key_cell"]),
        "lock_cells": [list(c) for c in generated["door_cells"]],
        "goal_witness": goal_witness, "exit_witness": exit_witness,
        "graph_parity": True, "lock_bypass_excluded": True,
        "source_room_encounters": sum(r["encounters"] for r in proposal.layout["rooms"]),
        "source_room_loot": sum(r["loot"] for r in proposal.layout["rooms"]),
        "combat_and_resource_parity": False,
        "player_export_certified": False,
        "mission_digest": _digest(mission),
    }


@dataclass(frozen=True)
class SpatialDungeonPreview:
    revision: int
    prefix: str
    seeds: tuple[int, ...]
    mission_ids: tuple[str, ...]
    campaign_id: str
    proofs: tuple[dict, ...]
    evidence_digest: str
    plan: object
    controller: object

    def to_dict(self):
        return {
            "revision": self.revision, "prefix": self.prefix,
            "seeds": list(self.seeds), "missions": list(self.mission_ids),
            "campaign": self.campaign_id, "proofs": deepcopy(self.proofs),
            "evidence_digest": self.evidence_digest, "applied": False,
            "r34_graph_parity": True,
            "physical_key_and_exit_witness": True,
            "combat_and_resource_parity": False,
            "player_export_certified": False,
        }


def prepare_spatial_dungeons(controller: AssistedDungeonController,
                             proposals, *, prefix="r74s") -> SpatialDungeonPreview:
    """Prepare three full R34-graph/R5 maps without touching live R1 history."""
    if not isinstance(controller, AssistedDungeonController):
        raise DungeonAssistError("invalid_controller", "Expected R74 controller")
    if type(prefix) is not str or _PREFIX.fullmatch(prefix) is None:
        raise DungeonAssistError("invalid_prefix", "Use a 1..12 lowercase prefix")
    if not isinstance(proposals, (list, tuple)) or len(proposals) != 3:
        raise DungeonAssistError("invalid_count", "Exactly three proposals required")
    if len({id(p) for p in proposals}) != 3 or len({
            p.topology_digest for p in proposals
            if isinstance(p, DungeonSuggestion)}) != 3:
        raise DungeonAssistError("duplicate_suggestion", "Use three distinct topologies")
    for proposal in proposals:
        controller.prepare_selection(proposal)
    original = controller.session.snapshot().to_dict()
    ids = tuple(f"{prefix}_multi_{i}" for i in range(1, 4))
    campaign = prefix + "_trilogy"
    if set(ids) & {r["id"] for r in original["content"]["missions"]}:
        raise DungeonAssistError("duplicate_mission", "Mission already exists")
    if campaign in {r["id"] for r in original["project"]["campaigns"]}:
        raise DungeonAssistError("duplicate_campaign", "Campaign already exists")

    sandbox = MapStudio(AuthoringSession.new(
        original["content"], original["project"]))
    dungeon = DungeonStudio(sandbox)
    proofs = []
    for i, (mid, proposal) in enumerate(zip(ids, proposals)):
        geometry = _layout_geometry(proposal.layout)
        dungeon.create_dungeon(
            mid, ("R74 • Archives maillées", "R74 • Galerie maillée",
                  "R74 • Sanctuaire maillé")[i],
            width=geometry["width"], height=geometry["height"],
            from_map=ids[i - 1] if i else None,
        )

        def carve(data):
            mission = next(r for r in data["missions"] if r["id"] == mid)
            _physical_mission(mission, proposal, geometry, i)
            return data
        sandbox._change(carve, kind="r74-spatial-carve", mission_id=mid)
        mission = sandbox.mission()
        # Validate AFTER canonical Content normalization to prove that the
        # actual serialized R5 coordinates, objects and walls are the truth.
        generated = {
            "geometry": geometry,
            "entry_cell": (geometry["positions"][0][0] + 2, MAIN_Y + 2),
            "goal_cell": tuple(v + 2 for v in geometry["positions"][geometry["goal_room"]]),
            "exit_cell": tuple(v + 2 for v in geometry["positions"][geometry["exit_room"]]),
            "key_cell": next((tuple(o["pos"]) for o in mission["objects"]
                              if o["kind"] == "key"), None),
            "door_cells": [tuple(o["pos"]) for o in mission["objects"]
                           if o["kind"] == "door"],
        }
        actual_floor = {tuple(t["pos"]) for t in mission["board"]["tiles"]
                        if not t["blocked"] or tuple(t["pos"]) in generated["door_cells"]}
        if actual_floor != geometry["floors"]:
            raise DungeonAssistError("spatial_parity_failed", "Actual board differs from plan")
        proof = _puzzle_evidence(mission, proposal, generated)
        proof["mission"] = mid
        proofs.append(proof)

    def add_campaign(project):
        updated = deepcopy(project)
        updated["campaigns"].append({
            "id": campaign, "name": "R74 • Trois donjons multi-salles",
            "description": "Transposition topologique R34/R5 vérifiée par R27",
            "start_mission": ids[0],
        })
        return updated
    sandbox.authoring.apply(sandbox.authoring.preview_project(
        add_campaign, kind="r74-spatial-campaign"))
    complete = sandbox.snapshot()
    plan = controller.session.preview_pair(
        lambda _content, _project: (
            deepcopy(complete["content"]), deepcopy(complete["project"])),
        kind="r74-spatial-three-dungeons",
    )
    seeds = tuple(p.seed for p in proposals)
    proof_tuple = tuple(deepcopy(proofs))
    evidence_digest = _digest({
        "prefix": prefix, "seeds": seeds, "missions": ids,
        "proofs": proof_tuple,
    })
    return SpatialDungeonPreview(
        original["revision"], prefix, seeds, ids, campaign,
        proof_tuple, evidence_digest, plan, controller,
    )


def apply_spatial_dungeons(controller: AssistedDungeonController,
                           preview: SpatialDungeonPreview):
    """One explicit R1 commit; fail on tamper, stale revision or foreign editor."""
    if (not isinstance(preview, SpatialDungeonPreview)
            or preview.controller is not controller):
        raise DungeonAssistError("foreign_preview", "Wrong preview owner")
    current = _digest({
        "prefix": preview.prefix, "seeds": preview.seeds,
        "missions": preview.mission_ids, "proofs": preview.proofs,
    })
    if current != preview.evidence_digest:
        raise DungeonAssistError("modified_preview", "Modified R27 route/provenance")
    if controller.session.revision != preview.revision:
        raise AuthoringError(
            "stale_revision", "r74-spatial-apply",
            "Editor changed since physical preview")
    transition = controller.session.apply(preview.plan)
    controller.invalidate()
    return transition

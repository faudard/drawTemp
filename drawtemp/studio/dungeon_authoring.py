"""R27 incremental dungeon authoring on the canonical R1/R5 Content documents.

A room is made of ordinary board tiles, a door/lever/chest is an existing
Mission.objects record, and a world connection is Mission.next_missions.
No parallel room/puzzle database, new save format, or separate gameplay loop.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy

from drawtemp.core import RuleError
from drawtemp.studio.map_authoring import MapStudio
from sporebound.authoring import add_blank_mission
from sporebound.campaign_graph import inspect_graph, set_link


def _mission(content, mid):
    for mission in content["missions"]:
        if mission["id"] == mid:
            return mission
    raise RuleError("Unknown map: " + str(mid))


def _position(mission, cell):
    if (not isinstance(cell, (list, tuple)) or len(cell) != 2
            or any(type(n) is not int for n in cell)):
        raise RuleError("Cell must have two integer coordinates")
    x, y = cell
    if not (0 <= x < mission["board"]["width"]
            and 0 <= y < mission["board"]["height"]):
        raise RuleError("Cell outside map")
    return (x, y)


def _identifier(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 64
            or not value.isascii() or
            not all(c.isalnum() or c in "_-" for c in value)):
        raise RuleError("Invalid object identifier (1..64 ASCII letters/digits/_/-)")
    return value


def _tile_map(mission):
    return {tuple(tile["pos"]): deepcopy(tile)
            for tile in mission["board"]["tiles"]}


def _write_tiles(mission, tiles):
    mission["board"]["tiles"] = [
        tiles[key] for key in sorted(tiles, key=lambda c: (c[1], c[0]))]


class DungeonStudio:
    """Headless facade reusing a *single* MapStudio / AuthoringSession history."""

    def __init__(self, maps: MapStudio):
        if not isinstance(maps, MapStudio):
            raise TypeError("DungeonStudio requires the active MapStudio")
        self.maps = maps

    def _change(self, transform, kind):
        return self.maps._change(
            transform, kind="r27-" + kind, mission_id=self.maps.mission_id)

    def create_dungeon(self, dungeon_id, name, *, width=16, height=16,
                       from_map=None):
        """Create a playable mission and optional world edge atomically."""
        def edit(content, project):
            updated = add_blank_mission(content, dungeon_id, name, width, height)
            if from_map is not None:
                updated = set_link(updated, from_map, dungeon_id)
            return updated, project
        plan = self.maps.authoring.preview_pair(edit, kind="r27-create-dungeon")
        result = self.maps.authoring.apply(plan)
        self.maps.mission_id = dungeon_id
        return result

    def link_maps(self, destination, *, enabled=True):
        """Use the real campaign graph; this is NOT a real-time teleport."""
        origin = self.maps.mission_id
        return self._change(
            lambda data: set_link(data, origin, destination, enabled),
            "world-link")

    def world_graph(self):
        documents = self.maps.snapshot()
        from drawtemp.core import Content
        from sporebound.tactical_rpg3 import authored_rules_for_document
        content = Content.from_dict(
            documents["content"],
            rules=authored_rules_for_document(documents["content"]))
        starts = [row["start_mission"]
                  for row in documents["project"]["campaigns"]]
        return inspect_graph(content, starts)

    def build_room(self, start, finish, *, entrance):
        """Paint a bordered, walkable room with one door opening in one edit.

        Refuses to overwrite existing authored terrain, objects or structures.
        The entrance is blocked until an actual door object is authored.
        """
        def edit(data):
            mission = _mission(data, self.maps.mission_id)
            x0, y0 = _position(mission, start)
            x1, y1 = _position(mission, finish)
            left, right = sorted((x0, x1))
            top, bottom = sorted((y0, y1))
            if right - left < 4 or bottom - top < 4:
                raise RuleError("Room must be at least 5 x 5 cells")
            if (left < 1 or top < 1
                    or right >= mission["board"]["width"] - 1
                    or bottom >= mission["board"]["height"] - 1):
                raise RuleError("Room must leave a one-cell outer margin")
            door = _position(mission, entrance)
            if not (((door[0] in (left, right)) and top < door[1] < bottom)
                    or ((door[1] in (top, bottom)) and left < door[0] < right)):
                raise RuleError("Entrance must be on a room wall, not a corner")
            footprint = {(x, y) for x in range(left, right + 1)
                         for y in range(top, bottom + 1)}
            tiles = _tile_map(mission)
            if footprint.intersection(tiles):
                raise RuleError("Room overlaps authored terrain; erase it first")
            if any(tuple(o["pos"]) in footprint
                   for o in mission.get("objects", ())):
                raise RuleError("Room overlaps an existing interactive object")
            # Structure appearance/footprint are managed by the R6 workshop.
            from sporebound.iso_structures import structure_template, structure_footprint
            for structure in mission.get("structures", ()):
                preset = structure_template(
                    structure["name"], structure["turns"],
                    door_slot=structure["door_slot"])
                if footprint.intersection(structure_footprint(
                        preset, structure["anchor"])):
                    raise RuleError("Room overlaps an R6 building")
            for unit in mission["units"]:
                w, h = unit.get("footprint", (1, 1))
                occupied = {(unit["pos"][0] + dx, unit["pos"][1] + dy)
                            for dx in range(w) for dy in range(h)}
                walls = {(x, y) for x, y in footprint
                         if x in (left, right) or y in (top, bottom)}
                if occupied.intersection(walls):
                    raise RuleError("Room wall would cover an actor")
            occupied_ids = {row["id"] for group in ("units", "objects")
                            for row in mission[group]}
            door_id = "room_door"
            suffix = 2
            while door_id in occupied_ids:
                door_id = "room_door_" + str(suffix)
                suffix += 1
            for x, y in footprint:
                wall = x in (left, right) or y in (top, bottom)
                tiles[(x, y)] = {
                    "pos": [x, y], "surface": "stone",
                    "feature": "stone_wall" if wall and (x, y) != door else "",
                    "blocked": wall,
                }
            # R1 tactical door: a real closed, locked passage, not a merely
            # cosmetic arch. The switch may be authored outside this room.
            mission["objects"].append({
                "id": door_id, "kind": "door", "pos": list(door), "locked": True})
            _write_tiles(mission, tiles)
            return data
        return self._change(edit, "build-room")

    def place_object(self, identifier, kind, cell, *, link="", amount=25,
                     locked=True):
        """Place existing battle-interactive objects; reuse R1 validation."""
        identifier = _identifier(identifier)
        if type(locked) is not bool:
            raise RuleError("Door locked must be a boolean")
        if kind not in ("door", "switch", "chest"):
            raise RuleError("Unsupported puzzle object kind")
        def edit(data):
            mission = _mission(data, self.maps.mission_id)
            position = _position(mission, cell)
            if any(o["id"] == identifier for o in mission["objects"]) or any(
                    u["id"] == identifier for u in mission["units"]):
                raise RuleError("Duplicate object/actor identifier")
            if any(tuple(o["pos"]) == position for o in mission["objects"]):
                raise RuleError("An interactive object already occupies this cell")
            tiles = _tile_map(mission)
            tile = tiles.get(position, {"pos": list(position)})
            if kind == "door":
                if (tile.get("feature") != "stone_wall"
                        or not tile.get("blocked", False)):
                    raise RuleError("Door must be placed on a room wall")
                if any(tuple(u["pos"]) == position for u in mission["units"]):
                    raise RuleError("Door cannot cover an actor spawn")
                tile["feature"] = ""
                tile["blocked"] = True
                tiles[position] = tile
                _write_tiles(mission, tiles)
                obj = {"id": identifier, "kind": "door",
                       "pos": list(position), "locked": bool(locked)}
            elif kind == "switch":
                if tile.get("blocked", False):
                    raise RuleError("Lever must be on a walkable tile")
                if not any(o["id"] == link and o["kind"] == "door"
                           for o in mission["objects"]):
                    raise RuleError("Lever must reference an existing door")
                obj = {"id": identifier, "kind": "switch",
                       "pos": list(position), "link": link}
            else:
                if type(amount) is not int or not 0 <= amount <= 10000:
                    raise RuleError("Chest amount must be within 0..10000")
                if tile.get("blocked", False):
                    raise RuleError("Chest must be on a walkable tile")
                obj = {"id": identifier, "kind": "chest",
                       "pos": list(position), "amount": amount}
            mission["objects"].append(obj)
            return data
        return self._change(edit, "place-" + kind)

    def puzzle_report(self, *, state_budget=50000):
        """Bounded static analysis of real battle doors/levers/chests and goals.

        Models a player walking four ways and interacting from adjacent cells.
        It deliberately does not certify combat AI, inventory keys, CT,
        narrative conditions, transitions or checkpoint crash recovery.
        """
        mission = self.maps.mission()
        if (any(o["kind"] in {"key", "plate", "block"} for o in mission["objects"])
                or any("sequence" in o for o in mission["objects"]
                       if o["kind"] == "door")):
            from .puzzle_debugger import analyze_puzzle
            return analyze_puzzle(mission, state_budget=state_budget)
        width, height = mission["board"]["width"], mission["board"]["height"]
        tiles = _tile_map(mission)
        objects = mission["objects"]
        doors = sorted((o for o in objects if o["kind"] == "door"),
                       key=lambda o: o["id"])
        if len(doors) > 8:
            return {"complete": False, "reachable_goals": [],
                    "unreachable_goals": deepcopy(mission["goal"]),
                    "unreachable_objects": [],
                    "warnings": ["Analysis limited to 8 doors"],
                    "states": 0}
        if type(state_budget) is not int or not 1 <= state_budget <= 500000:
            raise RuleError("Invalid state budget")
        door_bit = {o["id"]: 1 << i for i, o in enumerate(doors)}
        door_cells = {tuple(o["pos"]): door_bit[o["id"]] for o in doors}
        initial = sum(door_bit[o["id"]] for o in doors if o.get("open", False))
        starts = [tuple(u["pos"]) for u in mission["units"]
                  if u["team"] == "player"]
        if not starts:
            return {"complete": False, "reachable_goals": [],
                    "unreachable_goals": deepcopy(mission["goal"]),
                    "unreachable_objects": [],
                    "warnings": ["No player spawn"], "states": 0}

        def passable(pos, opened):
            if not (0 <= pos[0] < width and 0 <= pos[1] < height):
                return False
            if pos in door_cells and (opened & door_cells[pos]):
                return True
            return not tiles.get(pos, {}).get("blocked", False)

        queue = deque((x, y, initial) for x, y in starts
                      if passable((x, y), initial))
        seen = set(queue)
        accessible = set()
        interacted = set()
        while queue and len(seen) <= state_budget:
            x, y, opened = queue.popleft()
            accessible.add((x, y))
            for obj in objects:
                pos = tuple(obj["pos"])
                if abs(pos[0] - x) + abs(pos[1] - y) > 1:
                    continue
                kind = obj["kind"]
                if kind == "chest":
                    interacted.add(obj["id"])
                elif kind == "switch" and not obj.get("used", False):
                    interacted.add(obj["id"])
                    mask = opened | door_bit.get(obj.get("link"), 0)
                    state = (x, y, mask)
                    if mask != opened and state not in seen:
                        seen.add(state)
                        queue.append(state)
                elif kind == "door":
                    if not obj.get("locked", False):
                        interacted.add(obj["id"])
                        mask = opened | door_bit[obj["id"]]
                        state = (x, y, mask)
                        if mask != opened and state not in seen:
                            seen.add(state)
                            queue.append(state)
            for nx, ny in ((x - 1, y), (x + 1, y),
                           (x, y - 1), (x, y + 1)):
                state = (nx, ny, opened)
                if passable((nx, ny), opened) and state not in seen:
                    seen.add(state)
                    queue.append(state)
        complete = not queue
        goals = [list(g) for g in mission.get("goal", ())]
        missing_goals = [g for g in goals if tuple(g) not in accessible]
        solved_goals = [g for g in goals if tuple(g) in accessible]
        missing_objects = sorted(o["id"] for o in objects
                                 if o["kind"] in ("switch", "chest")
                                 and o["id"] not in interacted)
        warnings = []
        if not complete:
            warnings.append("State budget exceeded; result is inconclusive")
        if not goals:
            warnings.append("No authored goal; exit reachability not assessed")
        if missing_goals:
            warnings.append("Unreachable goal cells: " + str(missing_goals))
        if missing_objects:
            warnings.append("Unreachable interactables: " + ", ".join(missing_objects))
        return {"complete": complete, "reachable_goals": solved_goals,
                "unreachable_goals": missing_goals,
                "unreachable_objects": missing_objects,
                "warnings": warnings, "states": len(seen)}

    def place_puzzle(self, identifier, kind, cell, *, door_id="", latch=True):
        """Opt-in R27.B key/plate/block authored as real Mission.objects."""
        identifier = _identifier(identifier)
        if kind not in ("key", "plate", "block"):
            raise RuleError("Unknown R27.B puzzle kind")
        if type(latch) is not bool:
            raise RuleError("Plate latch must be boolean")
        def edit(data):
            mission = _mission(data, self.maps.mission_id)
            position = _position(mission, cell)
            if any(identifier == o["id"] or
                   tuple(o["pos"]) == position and o["kind"] != "plate"
                   for o in mission["objects"]):
                raise RuleError("Puzzle id/position already occupied")
            if any(identifier == u["id"] for u in mission["units"]):
                raise RuleError("Puzzle ID collides with an actor")
            tiles = _tile_map(mission)
            if tiles.get(position, {}).get("blocked", False):
                raise RuleError("Puzzle must be on a walkable tile")
            obj = {"id": identifier, "kind": kind, "pos": list(position)}
            if kind in ("key", "plate"):
                door = next((o for o in mission["objects"]
                             if o["kind"] == "door" and o["id"] == door_id), None)
                if door is None:
                    raise RuleError("Select an existing puzzle door")
                if kind == "key":
                    if "key" in door:
                        raise RuleError("Door already has a key")
                    obj["link"] = door["id"]
                    door["key"] = identifier
                    door["locked"] = True
                else:
                    obj.update(link=door["id"], latch=latch)
                    door["locked"] = True
            mission["objects"].append(obj)
            return data
        return self._change(edit, "place-puzzle-" + kind)

    def set_sequence(self, door_id, switch_ids, *, reset_on_error=True):
        """Configure an ordered set of existing linked switches atomically."""
        if (type(reset_on_error) is not bool or
                not isinstance(switch_ids, (tuple, list))):
            raise RuleError("Invalid sequence options")
        identifiers = list(switch_ids)
        if (not 2 <= len(identifiers) <= 8
                or len(set(identifiers)) != len(identifiers)):
            raise RuleError("Sequence requires 2..8 distinct switch IDs")
        def edit(data):
            mission = _mission(data, self.maps.mission_id)
            door = next((o for o in mission["objects"]
                         if o["kind"] == "door" and o["id"] == door_id), None)
            if door is None:
                raise RuleError("Unknown sequence door")
            linked = {o["id"] for o in mission["objects"]
                      if o["kind"] == "switch" and o.get("link") == door_id}
            if linked != set(identifiers):
                raise RuleError("All linked switches must appear exactly once")
            door.update(sequence=identifiers, sequence_progress=0,
                        reset_on_error=reset_on_error, locked=True)
            return data
        return self._change(edit, "configure-sequence")

    def puzzle_graph(self):
        """Read-only typed links for the Qt inspector (never a second schema)."""
        mission = self.maps.mission()
        nodes = [{"id": obj["id"], "kind": obj["kind"],
                  "pos": list(obj["pos"])}
                 for obj in mission["objects"]
                 if obj["kind"] in ("door", "switch", "chest", "key", "plate", "block")]
        edges = []
        for obj in mission["objects"]:
            if obj["kind"] in ("switch", "key", "plate"):
                edges.append({"from": obj["id"], "to": obj["link"],
                              "type": obj["kind"]})
            if obj["kind"] == "door" and "sequence" in obj:
                for index, switch in enumerate(obj["sequence"]):
                    edges.append({"from": switch, "to": obj["id"],
                                  "type": "sequence", "order": index + 1})
        return {"revision": self.maps.authoring.revision,
                "nodes": nodes, "edges": edges}

    def puzzle_debug(self, *, state_budget=50000):
        """Run a bounded detached search without altering the editor."""
        return self.puzzle_report(state_budget=state_budget)

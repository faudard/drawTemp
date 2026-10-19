"""R44.A opt-in regional WorldGraph over canonical R25 scene routes.

Only GameProject owns the authored graph. SceneRouter authorizes transitions;
GameSession/Campaign owns story flags, checkpoints and replay. This module
does not dispatch travel, mutate campaign state or introduce streaming.
"""
from __future__ import annotations

from copy import deepcopy
from heapq import heappop, heappush
import re

from .model import require
from .scene_router import SceneRouter

EXTENSION = "drawtemp.worldgraph"
VERSION = 1
MAX_REGIONS = 64
MAX_SCENES = 256
MAX_PORTALS = 512
MAX_OBJECTS = 512
BIOMES = frozenset({"fields", "village", "forest", "stone", "desert", "mountain", "coast", "swamp"})
PROJECTIONS = frozenset({"top_down", "isometric"})
OBJECT_KINDS = frozenset({"chest", "door", "npc", "switch"})
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_FLAG = re.compile(r"world44_[A-Za-z0-9_]{1,56}\Z")


def _id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _point(value):
    return (type(value) is list and len(value) == 2
            and all(type(v) is int and 0 <= v <= 100000 for v in value))


def _walkable(content, project, scene, pos):
    if scene in project.exploration:
        stage = project.exploration[scene]
        return (pos[0] < stage["width"] and pos[1] < stage["height"]
                and pos not in stage["blocked"])
    board = content.missions[scene].board
    return board.contains(tuple(pos)) and not board.tile(tuple(pos)).blocked


def _bounds(content, project, scene, pos):
    if scene in project.exploration:
        stage = project.exploration[scene]
        return pos[0] < stage["width"] and pos[1] < stage["height"]
    return content.missions[scene].board.contains(tuple(pos))


def validate_world_graph(raw, content, project):
    """Strict, versioned graph; no implicit migration or duplicate routing."""
    require(type(raw) is dict and set(raw) == {"version", "regions", "portals", "objects"}
            and type(raw["version"]) is int and raw["version"] == VERSION,
            "R44: unsupported WorldGraph schema (explicit migration required)")
    regions, portals, objects = raw["regions"], raw["portals"], raw["objects"]
    require(type(regions) is list and 1 <= len(regions) <= MAX_REGIONS
            and type(portals) is list and len(portals) <= MAX_PORTALS
            and type(objects) is list and len(objects) <= MAX_OBJECTS,
            "R44: WorldGraph exceeds catalogue limits")
    require(bool(project.scene_routes), "R44: canonical scene_routes must be configured")
    router = SceneRouter(project.scene_routes, content, project)
    scenes = {}
    region_ids = set()
    registry = project.asset_registry()
    known = set(project.exploration) | set(content.missions)
    for region in regions:
        require(type(region) is dict
                and set(region) == {"id", "title", "biome", "projection", "scenes", "palette"},
                "R44: invalid region fields")
        rid = region["id"]
        require(_id(rid) and rid not in region_ids,
                "R44: invalid or duplicate region ID")
        region_ids.add(rid)
        require(type(region["title"]) is str and 1 <= len(region["title"].strip()) <= 120,
                "R44: invalid region title")
        require(type(region["biome"]) is str and region["biome"] in BIOMES
                and type(region["projection"]) is str
                and region["projection"] in PROJECTIONS,
                "R44: unknown biome or projection")
        palette = region["palette"]
        require(type(palette) is list and len(palette) <= 16
                and len(set(map(str, palette))) == len(palette),
                "R44: invalid terrain sprite palette")
        for asset_id in palette:
            registry.require_reference(asset_id, "sprite")
        entries = region["scenes"]
        require(type(entries) is list and 1 <= len(entries) <= MAX_SCENES,
                "R44: region must contain authored scenes")
        for entry in entries:
            require(type(entry) is dict and set(entry) == {"id", "origin"},
                    "R44: invalid scene atlas entry")
            sid = entry["id"]
            require(_id(sid) and sid in known and sid not in scenes
                    and _point(entry["origin"]),
                    "R44: missing/duplicate scene or invalid atlas origin")
            scenes[sid] = {"region": rid, "projection": region["projection"],
                           "origin": list(entry["origin"])}
    require(len(scenes) <= MAX_SCENES and router.start in scenes,
            "R44: graph needs the canonical start and at most 256 scenes")
    routes = router.links
    portal_ids = set()
    for portal in portals:
        require(type(portal) is dict
                and set(portal) == {"route", "source", "travel_cost"},
                "R44: invalid portal fields")
        route_id, source = portal["route"], portal["source"]
        require(_id(route_id) and route_id in routes and route_id not in portal_ids,
                "R44: portal must reference a unique canonical route")
        portal_ids.add(route_id)
        route = routes[route_id]
        require(route["source"] in scenes and route["destination"] in scenes
                and _point(source)
                and _walkable(content, project, route["source"], source),
                "R44: portal references an unregistered or blocked scene cell")
        require(type(portal["travel_cost"]) is int
                and 1 <= portal["travel_cost"] <= 10000,
                "R44: travel cost must be 1..10000 authoring units")
    flags, object_ids = set(), set()
    for obj in objects:
        require(type(obj) is dict
                and set(obj) == {"id", "scene", "kind", "flag"},
                "R44: invalid persistent object fields")
        require(_id(obj["id"]) and (obj["scene"], obj["id"]) not in object_ids
                and obj["scene"] in scenes and obj["kind"] in OBJECT_KINDS
                and type(obj["flag"]) is str and _FLAG.fullmatch(obj["flag"])
                and obj["flag"] not in flags,
                "R44: duplicate object, invalid scene, kind or world flag")
        object_ids.add((obj["scene"], obj["id"]))
        flags.add(obj["flag"])
    # Cycles with actual return portals are legitimate; unreachable islands
    # and dangling graph references are not. Conditions are checked at runtime.
    adjacency = {scene: set() for scene in scenes}
    for item in portals:
        route = routes[item["route"]]
        adjacency[route["source"]].add(route["destination"])
    seen, pending = set(), [router.start]
    while pending:
        sid = pending.pop()
        if sid not in seen:
            seen.add(sid)
            pending.extend(sorted(adjacency[sid] - seen, reverse=True))
    require(seen == set(scenes), "R44: graph contains unreachable scenes")
    return deepcopy(raw)


class WorldGraph:
    """Immutable atlas reader and condition-aware path inspector (not a router)."""

    def __init__(self, raw, content, project):
        self.raw = validate_world_graph(raw, content, project)
        self._content, self._project = content, project
        self._router = SceneRouter(project.scene_routes, content, project)
        self._scenes = {
            entry["id"]: {**entry, "region": region["id"],
                          "projection": region["projection"]}
            for region in self.raw["regions"] for entry in region["scenes"]
        }
        self._portals = {p["route"]: p for p in self.raw["portals"]}

    def metrics(self):
        return {"regions": len(self.raw["regions"]), "scenes": len(self._scenes),
                "portals": len(self._portals), "objects": len(self.raw["objects"]),
                "budget": {"regions": MAX_REGIONS, "scenes": MAX_SCENES,
                           "portals": MAX_PORTALS, "objects": MAX_OBJECTS}}

    def atlas_position(self, scene, cell):
        require(scene in self._scenes and _point(cell)
                and _bounds(self._content, self._project, scene, cell),
                "R44: cell outside authored scene")
        meta = self._scenes[scene]
        x, y = cell
        u, v = meta["origin"]
        if meta["projection"] == "isometric":
            return [u + x - y, v + x + y]
        return [u + x, v + y]

    def scene_cell(self, scene, atlas_position):
        require(scene in self._scenes and type(atlas_position) is list
                and len(atlas_position) == 2
                and all(type(v) is int for v in atlas_position),
                "R44: invalid atlas picking position")
        meta = self._scenes[scene]
        u = atlas_position[0] - meta["origin"][0]
        v = atlas_position[1] - meta["origin"][1]
        if meta["projection"] == "isometric":
            require((u + v) % 2 == 0 and (v - u) % 2 == 0,
                    "R44: atlas point is between isometric cells")
            cell = [(u + v) // 2, (v - u) // 2]
        else:
            cell = [u, v]
        require(_point(cell) and _bounds(self._content, self._project, scene, cell),
                "R44: atlas picking outside authored scene")
        return cell

    def object_states(self, progress, scene):
        """Read only canonical Campaign flags, retained by GameSession saves."""
        require(scene in self._scenes, "R44: unknown WorldGraph scene")
        result = {}
        for obj in self.raw["objects"]:
            if obj["scene"] != scene:
                continue
            value = progress.story_flags.get(obj["flag"], False)
            require(type(value) is bool, "R44: world object flag must be boolean")
            result[obj["id"]] = {"kind": obj["kind"], "active": value,
                                 "flag": obj["flag"]}
        return result

    def inspect_portal(self, scene, route_id, progress):
        """Canonical R25 preflight: does not move a cursor or spend travel cost."""
        require(route_id in self._portals, "R44: unknown atlas portal")
        route = self._router.destination(scene, route_id, progress)
        return {"route": route, "travel_cost": self._portals[route_id]["travel_cost"],
                "source": list(self._portals[route_id]["source"])}

    def shortest_path(self, start, destination, progress):
        """Stable minimum-cost directed path through currently unlocked portals."""
        require(start in self._scenes and destination in self._scenes,
                "R44: unknown path endpoint")
        todo = [(0, (), start)]
        best = {start: (0, ())}
        while todo:
            cost, path, scene = heappop(todo)
            if best[scene] != (cost, path):
                continue
            if scene == destination:
                return {"routes": list(path), "travel_cost": cost}
            for ident in sorted(self._portals):
                route = self._router.links[ident]
                if route["source"] != scene:
                    continue
                # Conditions are evaluated using the canonical R25 reader.
                from .model import RuleError
                try:
                    self._router.destination(scene, ident, progress)
                except RuleError:
                    continue
                target = route["destination"]
                candidate = (cost + self._portals[ident]["travel_cost"],
                             path + (ident,))
                if target not in best or candidate < best[target]:
                    best[target] = candidate
                    heappush(todo, (candidate[0], candidate[1], target))
        return None


__all__ = ["EXTENSION", "WorldGraph", "validate_world_graph"]

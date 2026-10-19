"""Headless visual projection, camera, picking and culling for the Qt Quick renderer.

Gameplay remains in the R1 SDK. All coordinates refer to tile centres.
"""
from dataclasses import dataclass
from copy import deepcopy
from collections.abc import Mapping
from math import floor
import hashlib
import json


@dataclass(frozen=True)
class IsoProjection:
    width: float = 96
    height: float = 48
    height_step: float = 12

    def project(self, x, y, elevation=0):
        return (x - y) * self.width / 2, (x + y) * self.height / 2 - elevation * self.height_step

    def unproject(self, sx, sy, elevation=0):
        a, b = sx / (self.width / 2), (sy + elevation * self.height_step) / (self.height / 2)
        return (a + b) / 2, (b - a) / 2

    def pick(self, sx, sy, width, height, elevations=None):
        elevations = elevations or {}
        hits = []
        for z in {0, *elevations.values()}:
            x, y = self.unproject(sx, sy, z)
            for cx in (floor(x), floor(x) + 1):
                for cy in (floor(y), floor(y) + 1):
                    if not (0 <= cx < width and 0 <= cy < height):
                        continue
                    if elevations.get((cx, cy), 0) != z:
                        continue
                    px, py = self.project(cx, cy, z)
                    if abs(sx - px) / (self.width / 2) + abs(sy - py) / (self.height / 2) <= 1 + 1e-9:
                        hits.append((cx + cy, z, cx, cy))
        return tuple(max(hits)[-2:]) if hits else None


@dataclass
class Camera:
    width: float = 960
    height: float = 540
    zoom: float = 1
    pan_x: float = 0
    pan_y: float = 0

    def screen(self, x, y):
        return self.width / 2 + self.pan_x + x * self.zoom, self.height / 2 + self.pan_y + y * self.zoom

    def world(self, x, y):
        return (x - self.width / 2 - self.pan_x) / self.zoom, (y - self.height / 2 - self.pan_y) / self.zoom

    def center(self, x, y):
        self.pan_x, self.pan_y = -x * self.zoom, -y * self.zoom

    def zoom_at(self, factor, x, y):
        from math import isfinite
        if not isfinite(factor) or factor <= 0:
            raise ValueError("Invalid zoom")
        anchor = self.world(x, y)
        self.zoom = min(3.0, max(0.4, self.zoom * factor))
        self.pan_x = x - self.width / 2 - anchor[0] * self.zoom
        self.pan_y = y - self.height / 2 - anchor[1] * self.zoom


MATERIALS = ("grass", "dirt", "stone", "cobble", "sand", "rock", "water", "bridge")
COLORS = ("#6a9672", "#aa8968", "#9b9d95", "#b7b1a1",
          "#c5b787", "#817d76", "#528cae", "#b7a17b")


def facing_to_direction(facing):
    """Map the four canonical tactical facings to cosmetic atlas directions."""
    if not isinstance(facing, (tuple, list)) or len(facing) != 2:
        return "south"
    dx, dy = facing
    if type(dx) not in (int, float) or type(dy) not in (int, float):
        return "south"
    if abs(dx) > abs(dy):
        return "east" if dx > 0 else "west"
    return "south" if dy >= 0 else "north"


def scene_from_mission(mission, snapshot=None):
    """Detached dictionary for both Qt clients, using canonical mission + R1 snapshot."""
    battle = getattr(snapshot, "battle", None)
    if battle is not None and (battle["mission_id"] != mission.id or
                               battle["width"] != mission.board.width or
                               battle["height"] != mission.board.height):
        raise ValueError("Snapshot/mission mismatch")
    overrides = {tuple(t["pos"]): t for t in battle["tiles"]} if battle else {}
    tiles = []
    for x, y in mission.board.cells():
        original = mission.board.tile((x, y))
        t = overrides.get((x, y))
        tiles.append({"x": x, "y": y,
                      "surface": str(t["surface"] if t else original.surface),
                      "height": int(t["height"] if t else original.height),
                      "feature": str(t["feature"] if t else original.feature),
                      "blocked": bool(t["blocked"] if t else original.blocked),
                      "cover": int(t["cover"] if t else original.cover),
                      "hazard": int(t["hazard"] if t else original.hazard),
                      "goal": (x, y) in mission.goal})
    actors = []
    levels = battle.get("unit_levels", {}) if battle else mission.unit_levels
    for u in (battle["units"] if battle else mission.units):
        field = (lambda k: u[k]) if isinstance(u, Mapping) else (lambda k: getattr(u, k))
        facing = u.get("facing", (0, 1)) if isinstance(u, Mapping) else getattr(u, "facing", (0, 1))
        if (isinstance(facing, (list, tuple)) and len(facing) == 2
                and all(type(n) in (int, float) for n in facing)
                and (facing[0] or facing[1])):
            fx, fy = facing
            direction = ("east" if fx > 0 else "west") if abs(fx) > abs(fy) else (
                "south" if fy >= 0 else "north")
        else:
            direction = "south"
        actors.append({"id": str(field("id")), "name": str(field("name")), "x": float(field("pos")[0]),
                       "y": float(field("pos")[1]), "team": str(field("team")),
                       "alive": field("hp") > 0, "level": int(levels.get(field("id"), 0)),
                       "direction": facing_to_direction(
                           u.get("facing", (0, 1)) if isinstance(u, Mapping)
                           else getattr(u, "facing", (0, 1)))})
    objects = [{"id": str(o["id"]), "kind": str(o["kind"]),
                "x": int(o["pos"][0]), "y": int(o["pos"][1]),
                **({"open": bool(o.get("open", False))}
                   if o["kind"] == "door" else {}),
                **({"used": bool(o.get("used", False))}
                   if o["kind"] in ("key", "plate", "switch") else {}),
                **({"gate": "key" if "key" in o else
                            "sequence" if "sequence" in o else ""}
                   if o["kind"] == "door" and
                   ("key" in o or "sequence" in o) else {})}
               for o in (battle["objects"] if battle else mission.objects)]
    return {"mission": mission.id, "width": mission.board.width,
            "height": mission.board.height,
            "revision": int(getattr(snapshot, "revision", 0)),
            "tiles": tiles, "actors": actors, "objects": objects,
            "structures": deepcopy(mission.structures),
            "interior_floors": deepcopy(mission.interior_floors)}


def scene_from_exploration(stage, *, revision=0):
    """Adapt an R1 narrative exploration snapshot to the same R3 scene schema.

    The canonical exploration stage has no authored tactical terrain map. Its
    theme and blockers produce a presentation fallback; gameplay still uses
    the untouched SDK exploration state.
    """
    if not isinstance(stage, Mapping):
        raise ValueError("Expected a validated exploration snapshot")
    width, height = stage["width"], stage["height"]
    blocked = {tuple(cell) for cell in stage["blocked"]}
    materials = {"fields": "grass", "village": "cobble",
                 "forest": "grass", "stone": "stone"}
    surface = materials.get(stage["theme"], "grass")
    tiles = [
        {"x": x, "y": y, "height": 0, "surface": surface,
         "feature": "tree" if (x, y) in blocked and surface == "grass" else "",
         "blocked": (x, y) in blocked, "cover": 0, "hazard": 0,
         "goal": False}
        for y in range(height) for x in range(width)
    ]
    actors = [{"id": "jeanne", "name": "Jeanne", "x": stage["position"][0],
               "y": stage["position"][1], "team": "player", "alive": True,
               "level": 0, "direction": "south"}]
    actors.extend(
        {"id": actor["id"], "name": actor["name"], "x": actor["pos"][0],
         "y": actor["pos"][1], "team": "ally",
         "alive": actor["status"] == "active", "level": 0,
         "direction": "south"}
        for actor in stage.get("actors", ())
    )
    objects = [
        {"id": point["id"], "kind": "visited" if point["visited"] else "marker",
         "x": point["pos"][0], "y": point["pos"][1]}
        for point in stage["interactions"]
    ]
    return {"mission": "exploration:" + stage["scene_id"],
            "width": width, "height": height, "revision": revision,
            "tiles": tiles, "actors": actors, "objects": objects}


def fingerprint(scene):
    return hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest()


OVERLAY_COLORS = {
    "reachable": "#48c2a2",
    "path": "#76c9ee",
    "los": "#b1b9fc",
    "range": "#efb96c",
    "cover": "#85b89d",
    "danger": "#eb726f",
    "intent": "#b894ee",
    "objective": "#eed777",
}


def render_items(scene, camera, projection=IsoProjection(), selected=None,
                 *, tile_index=None, overlays=None, active_level=0,
                 actor_positions=None, cutaway=False):
    """Render common depth-sorted Qt Quick records with indexed tile culling.

    Optional overlays are cosmetic, revision-independent cells. They never
    write back to Simulation or Content. A cached TileChunkIndex can be reused
    through pan/zoom and updated only when authored terrain actually changes.
    """
    from .tile_chunks import TileChunkIndex

    index = tile_index if tile_index is not None else TileChunkIndex(scene)
    elev = index.elevations
    lo_x, hi_x, lo_y, hi_y = index.visible_bounds(camera, projection)
    overlay_by_cell = {}
    for kind, cells in (overlays or {}).items():
        if kind not in OVERLAY_COLORS:
            raise ValueError("Unknown overlay: " + str(kind))
        for cell in cells:
            if len(cell) != 2:
                raise ValueError("Overlays require [x, y] cells")
            x, y = cell
            if type(x) is not int or type(y) is not int:
                raise ValueError("Overlay coordinates must be integers")
            if 0 <= x < scene["width"] and 0 <= y < scene["height"]:
                overlay_by_cell[(x, y)] = kind

    rows = []
    for t in index.visible_tiles(camera, projection):
        x, y, z = t["x"], t["y"], t["height"]
        sx, sy = projection.project(x, y, z)
        surface = t["surface"] if t["surface"] in MATERIALS else "grass"
        atlas_index = MATERIALS.index(surface) * 2 + ((x * 17 + y * 29) & 1)
        overlay = overlay_by_cell.get((x, y), "")
        rows.append({"kind": "tile", "id": f"tile:{x}:{y}", "x": x, "y": y,
                     "sx": sx, "sy": sy, "surface": surface,
                     "color": COLORS[MATERIALS.index(surface)],
                     "atlasX": atlas_index * 96, "selected": selected == (x, y),
                     "height": z,
                     "eastDrop": max(0, z - elev.get((x + 1, y), 0)),
                     "southDrop": max(0, z - elev.get((x, y + 1), 0)),
                     "overlay": overlay,
                     "overlayColor": OVERLAY_COLORS.get(overlay, "transparent"),
                     "feature": t.get("feature", ""),
                     "blocked": t.get("blocked", False), "cover": t.get("cover", 0),
                     "hazard": t.get("hazard", 0), "goal": t.get("goal", False),
                     "zOrder": (x + y) * 100})
    for o in scene["objects"]:
        x, y = o["x"], o["y"]
        if lo_x - 1 <= x <= hi_x + 1 and lo_y - 1 <= y <= hi_y + 1:
            sx, sy = projection.project(x, y, elev.get((x, y), 0))
            rows.append({"kind": "object", "id": o["id"], "label": o["kind"],
                         "open": o.get("open", False),
                         **({"used": o["used"]} if "used" in o else {}),
                         **({"gate": o["gate"]} if "gate" in o else {}),
                         "sx": sx, "sy": sy, "zOrder": (x + y) * 100 + 30})
    for a in scene["actors"]:
        x, y = a["x"], a["y"]
        if lo_x - 1 <= x <= hi_x + 1 and lo_y - 1 <= y <= hi_y + 1:
            sx, sy = projection.project(x, y, elev.get((int(x), int(y)), 0) + a["level"] * 4)
            rows.append({"kind": "actor", "id": a["id"],
                         "label": a.get("name", a["id"]), "team": a["team"],
                         "alive": a["alive"], "sx": sx, "sy": sy,
                         "direction": a.get("direction", "south"),
                         "zOrder": (x + y) * 100 + 60})
    from .building_geometry import building_surfaces
    from .visual_compositor import automatic_cutaway
    hidden_roofs = automatic_cutaway(
        scene, selected=selected, active_level=active_level,
        positions=actor_positions)
    margin = projection.width * 2
    for part in building_surfaces(scene, projection, cutaway=cutaway,
                                  active_level=active_level,
                                  hidden_roofs=hidden_roofs):
        x0, y0 = camera.screen(part["sx"], part["sy"])
        x1, y1 = camera.screen(part["sx"] + part["spanX"],
                                part["sy"] + part["spanY"])
        if x1 >= -margin and x0 <= camera.width + margin and (
                y1 >= -margin and y0 <= camera.height + margin):
            rows.append(part)
    return sorted(rows, key=lambda r: (r["zOrder"], r["id"]))


def pick(scene, camera, sx, sy, projection=IsoProjection(), *,
         selected=None, active_level=0, actor_positions=None):
    wx, wy = camera.world(sx, sy)
    elevations = {(t["x"], t["y"]): t["height"] for t in scene["tiles"] if t["height"]}
    hits = []
    for a in scene["actors"]:
        x, y = a["x"], a["y"]
        px, py = projection.project(x, y, elevations.get((int(x), int(y)), 0) + a["level"] * 4)
        if abs(wx - px) < projection.width * .25 and py - projection.height * 1.2 < wy < py:
            hits.append(((x + y) * 100 + 60, {"kind": "actor", "id": a["id"]}))
    for o in scene["objects"]:
        px, py = projection.project(o["x"], o["y"], elevations.get((o["x"], o["y"]), 0))
        if abs(wx - px) < projection.width * .2 and py - projection.height < wy < py:
            hits.append(((o["x"] + o["y"]) * 100 + 30, {"kind": "object", "id": o["id"]}))
    if hits:
        return max(hits, key=lambda row: row[0])[1]
    from .building_geometry import building_surfaces, pick_surface
    from .visual_compositor import automatic_cutaway
    hidden_roofs = automatic_cutaway(
        scene, selected=selected, active_level=active_level,
        positions=actor_positions)
    structure_hit = pick_surface(building_surfaces(
        scene, projection, active_level=active_level,
        hidden_roofs=hidden_roofs), camera, sx, sy)
    if structure_hit is not None:
        return {"kind": "building", **structure_hit}
    cell = projection.pick(wx, wy, scene["width"], scene["height"], elevations)
    return {"kind": "tile", "cell": list(cell)} if cell else None

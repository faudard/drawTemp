"""Headless visual projection, camera, picking and culling for the Qt Quick renderer.

Gameplay remains in the R1 SDK. All coordinates refer to tile centres.
"""
from dataclasses import dataclass
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
                      "feature": str(t["feature"] if t else original.feature)})
    actors = []
    levels = battle.get("unit_levels", {}) if battle else mission.unit_levels
    for u in (battle["units"] if battle else mission.units):
        field = (lambda k: u[k]) if isinstance(u, dict) else (lambda k: getattr(u, k))
        actors.append({"id": str(field("id")), "x": float(field("pos")[0]),
                       "y": float(field("pos")[1]), "team": str(field("team")),
                       "alive": field("hp") > 0, "level": int(levels.get(field("id"), 0))})
    objects = [{"id": str(o["id"]), "kind": str(o["kind"]),
                "x": int(o["pos"][0]), "y": int(o["pos"][1])}
               for o in (battle["objects"] if battle else mission.objects)]
    return {"mission": mission.id, "width": mission.board.width,
            "height": mission.board.height,
            "revision": int(getattr(snapshot, "revision", 0)),
            "tiles": tiles, "actors": actors, "objects": objects}


def fingerprint(scene):
    return hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest()


def render_items(scene, camera, projection=IsoProjection(), selected=None):
    """Cull outside viewport; return depth-sorted QML scenegraph records."""
    elev = {(t["x"], t["y"]): t["height"] for t in scene["tiles"]}
    max_height = max(elev.values(), default=0)
    margin = projection.width * 2
    corners = [camera.world(x, y) for x in (-margin, camera.width + margin)
               for y in (-margin, camera.height + margin)]
    coords = [projection.unproject(x, y, z) for x, y in corners for z in (0, max_height)]
    minx, maxx = int(min(x for x, _ in coords)) - 3, int(max(x for x, _ in coords)) + 3
    miny, maxy = int(min(y for _, y in coords)) - 3, int(max(y for _, y in coords)) + 3
    rows = []
    for t in scene["tiles"]:
        x, y, z = t["x"], t["y"], t["height"]
        if not (minx <= x <= maxx and miny <= y <= maxy):
            continue
        sx, sy = projection.project(x, y, z)
        surface = t["surface"] if t["surface"] in MATERIALS else "grass"
        atlas_index = MATERIALS.index(surface) * 2 + ((x * 17 + y * 29) & 1)
        rows.append({"kind": "tile", "id": f"tile:{x}:{y}", "sx": sx, "sy": sy,
                     "color": COLORS[MATERIALS.index(surface)],
                     "atlasX": atlas_index * 96, "selected": selected == (x, y),
                     "zOrder": (x + y) * 100})
    for o in scene["objects"]:
        x, y = o["x"], o["y"]
        if minx - 1 <= x <= maxx + 1 and miny - 1 <= y <= maxy + 1:
            sx, sy = projection.project(x, y, elev.get((x, y), 0))
            rows.append({"kind": "object", "id": o["id"], "label": o["kind"],
                         "sx": sx, "sy": sy, "zOrder": (x + y) * 100 + 30})
    for a in scene["actors"]:
        x, y = a["x"], a["y"]
        if minx - 1 <= x <= maxx + 1 and miny - 1 <= y <= maxy + 1:
            sx, sy = projection.project(x, y, elev.get((int(x), int(y)), 0) + a["level"] * 4)
            rows.append({"kind": "actor", "id": a["id"], "team": a["team"],
                         "alive": a["alive"], "sx": sx, "sy": sy,
                         "zOrder": (x + y) * 100 + 60})
    return sorted(rows, key=lambda r: (r["zOrder"], r["id"]))


def pick(scene, camera, sx, sy, projection=IsoProjection()):
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
    cell = projection.pick(wx, wy, scene["width"], scene["height"], elevations)
    return {"kind": "tile", "cell": list(cell)} if cell else None

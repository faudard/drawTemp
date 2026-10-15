"""R6.2: screen-space building surfaces for the one R3 Qt Quick renderer.

The same four-vertex polygons are consumed by the scenegraph and by picking.
Coordinates are *world projection units*, prior to the shared camera; there
is no Tk canvas, separate renderer, approximate roof bounding box or new
persistent content model.
"""
from __future__ import annotations

from math import isfinite

from sporebound.building_visuals import BUILDINGS, building_appearance
from sporebound.iso_structures import structure_template


FACADE_COLORS = {
    "pierre": "#91918b", "torchis": "#bba98b", "brique": "#a77c69",
}
ROOF_COLORS = {
    "tuiles": "#a75d4d", "ardoise": "#535f72", "plat": "#897f71",
}
LEVEL_PALETTE = {
    "stone": "#8a8c89", "cobble": "#aca59a", "grass": "#648f67",
    "dirt": "#98795f",
}


def _in_polygon(point, vertices):
    """Pixel-accurate closed convex/concave polygon test, including edges."""
    px, py = point
    inside = False
    x0, y0 = vertices[-1]
    for x1, y1 in vertices:
        cross = (px - x0) * (y1 - y0) - (py - y0) * (x1 - x0)
        if (abs(cross) < 1e-7 and
                min(x0, x1) - 1e-7 <= px <= max(x0, x1) + 1e-7 and
                min(y0, y1) - 1e-7 <= py <= max(y0, y1) + 1e-7):
            return True
        if (y1 > py) != (y0 > py):
            intersect = x0 + (x1 - x0) * (py - y0) / (y1 - y0)
            if px < intersect:
                inside = not inside
        x0, y0 = x1, y1
    return inside


def _part(structure, name, cell, vertices, z, color, *, suffix="", floor=0):
    minx = min(v[0] for v in vertices)
    miny = min(v[1] for v in vertices)
    anchor = tuple(structure["anchor"])
    return {
        "kind": "building", "part": name, "id": "building:" + structure["id"]
        + ":" + name + ":" + suffix,
        "structure_id": structure["id"], "anchor": list(anchor),
        "cell": list(cell), "level": floor,
        "sx": minx, "sy": miny,
        "spanX": max(v[0] for v in vertices) - minx,
        "spanY": max(v[1] for v in vertices) - miny,
        "points": [[round(x-minx, 6), round(y-miny, 6)] for x, y in vertices],
        "vertices": vertices, "zOrder": z, "color": color,
    }


def building_surfaces(scene, projection, *, cutaway=False, active_level=0):
    """Build visible roof, wall faces, opening and authored floor polygons.

    Cutaway is presentation-only. Upper floors are *not* simulated navigation
    or tactical LOS and are only displayed when the roof is cut away.
    """
    structures = scene.get("structures", ())
    if not structures:
        return []
    floors = scene.get("interior_floors", ())
    results = []
    elev = {(tile["x"], tile["y"]): tile["height"] for tile in scene["tiles"]}
    for record in structures:
        clip = structure_template(record["name"], record["turns"],
                                  door_slot=record["door_slot"])
        x0, y0 = record["anchor"]
        w, h = clip.width, clip.height
        cells = [(x0 + dx, y0 + dy) for dx, dy in clip.offsets]
        # Wall stamps carry a tactical height of 2 while interior floors
        # retain the underlying ground level. Anchoring at their maximum
        # would make the whole house float above its entrance.
        base = min(elev.get(cell, 0) for cell in cells)
        attached = sorted((f for f in floors if f["structure_id"] == record["id"]),
                          key=lambda f: f["level"])
        top = base + 2.5 + len(attached)*2.0
        front = max(x+y for x, y in cells)*100
        p = lambda x, y, height: projection.project(x, y, height)
        lx, rx = x0 - .5, x0 + w - .5
        ty, by = y0 - .5, y0 + h - .5
        appearance = (building_appearance(record) if record["name"] in BUILDINGS
                      else {"facade": "pierre", "roof": "plat", "windows": []})
        facade_color = FACADE_COLORS[appearance["facade"]]
        roof_color = ROOF_COLORS[appearance["roof"]]
        # Render only the south and east walls, which face the isometric camera.
        # Each cell is an independent, real selectable facade polygon.
        for x in range(w):
            a, b = x0 + x - .5, x0 + x + .5
            vertices = [p(a, by, top), p(b, by, top),
                        p(b, by, base), p(a, by, base)]
            results.append(_part(record, "facade", (x0+x, y0+h-1),
                                 vertices, front+40, facade_color,
                                 suffix=f"s{x}"))
        for y in range(h):
            a, b = y0 + y - .5, y0 + y + .5
            vertices = [p(rx, a, top), p(rx, b, top),
                        p(rx, b, base), p(rx, a, base)]
            results.append(_part(record, "facade", (x0+w-1, y0+y),
                                 vertices, front+41, facade_color,
                                 suffix=f"e{y}"))

        windows = {tuple(pos) for pos in appearance["windows"]}
        # Windows on north/west faces are intentionally occluded until the
        # structure is rotated; a hidden surface must never be pickable.
        for dx, dy in sorted(windows):
            if dy == h-1:
                a, b = x0+dx-.2, x0+dx+.2
                verts = [p(a, by, base+.65*(top-base)),
                         p(b, by, base+.65*(top-base)),
                         p(b, by, base+.35*(top-base)),
                         p(a, by, base+.35*(top-base))]
            elif dx == w-1:
                a, b = y0+dy-.2, y0+dy+.2
                verts = [p(rx, a, base+.65*(top-base)),
                         p(rx, b, base+.65*(top-base)),
                         p(rx, b, base+.35*(top-base)),
                         p(rx, a, base+.35*(top-base))]
            else:
                continue
            results.append(_part(record, "window", (x0+dx, y0+dy),
                                 verts, front+45, "#8dc1ce",
                                 suffix=f"{dx}:{dy}"))
        door = next(((dx,dy) for (dx,dy), tile in zip(clip.offsets,clip.terrain)
                     if tile.get("surface") == "cobble" and not tile.get("blocked")),None)
        if door is not None:
            dx, dy = door
            if dy == h-1:
                a, b = x0+dx-.32, x0+dx+.32
                verts = [p(a,by,base+.58*(top-base)),
                         p(b,by,base+.58*(top-base)),
                         p(b,by,base), p(a,by,base)]
            elif dx == w-1:
                a, b = y0+dy-.32, y0+dy+.32
                verts = [p(rx,a,base+.58*(top-base)),
                         p(rx,b,base+.58*(top-base)),
                         p(rx,b,base), p(rx,a,base)]
            else:
                verts = None
            if verts is not None:
                results.append(_part(record, "door", (x0+dx,y0+dy),
                                     verts, front+46, "#675143", suffix="entry"))
        if cutaway or active_level:
            for f in attached:
                if active_level not in (0, f["level"]):
                    continue
                z = base + 1.8 + f["level"]*2.0
                for tile in f["tiles"]:
                    dx, dy = tile["pos"]
                    x, y = x0+dx, y0+dy
                    verts = [p(x,y-.5,z),p(x+.5,y,z),p(x,y+.5,z),p(x-.5,y,z)]
                    # A floor must be visible, but facade/window/door overlays
                    # remain on top so opening selection stays predictable.
                    results.append(_part(record, "floor", (x,y), verts,
                                         front+43, LEVEL_PALETTE[tile["surface"]],
                                         suffix=f"{f['level']}:{dx}:{dy}",
                                         floor=f["level"]))
        if not (cutaway or active_level):
            roof = [p(lx,ty,top),p(rx,ty,top),p(rx,by,top),p(lx,by,top)]
            results.append(_part(record, "roof", (x0,y0),roof,
                                 front+49,roof_color,suffix="main"))
    return results


def pick_surface(rows, camera, x, y):
    """Pick *only* painted polygons in reverse Qt Quick z-order.

    The renderer passes its current culled rows. No phantom hit through a roof,
    hidden floor, unseen back wall or offscreen building is allowed.
    """
    if not all(isfinite(float(v)) for v in (x,y)):
        return None
    wx, wy = camera.world(x,y)
    for row in sorted(rows, key=lambda item: (item["zOrder"],item["id"]),
                      reverse=True):
        if row["kind"] != "building":
            continue
        if _in_polygon((wx,wy),row["vertices"]):
            return {
                "structure_id": row["structure_id"],
                "anchor": row["anchor"][:],
                "cell": row["cell"][:],
                "part": row["part"],
                "level": row["level"],
            }
    return None

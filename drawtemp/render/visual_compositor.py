"""R3.C presentation-only motion and architecture cutaway contracts.

The R12 AnimationDirector owns the clip journal, R6 owns structure geometry and
R7/R4 own atlas frames. This module owns continuous projected feet and cutaway
decisions shared by both Qt clients; no game rules or UI toolkit imports.
"""
from math import isfinite, sin, pi

MOTION_KINDS = frozenset({"move", "attack", "impact", "heal", "miss",
                          "cast", "interrupt"})


def _point(raw):
    if (not isinstance(raw, (list, tuple)) or len(raw) != 2 or
            any(type(v) not in (int, float) or not isfinite(v) for v in raw)):
        return None
    return float(raw[0]), float(raw[1])


def _height(x, y, elevations, width, height):
    """Bilinear visual interpolation; gameplay continues on integer cells."""
    from math import floor
    x, y = min(max(0.0, x), width - 1), min(max(0.0, y), height - 1)
    ix, iy = int(floor(x)), int(floor(y))
    jx, jy = min(ix + 1, width - 1), min(iy + 1, height - 1)
    tx, ty = x - ix, y - iy
    a = elevations.get((ix, iy), 0)
    b = elevations.get((jx, iy), 0)
    c = elevations.get((ix, jy), 0)
    d = elevations.get((jx, jy), 0)
    return a * (1 - tx) * (1 - ty) + b * tx * (1 - ty) + c * (1 - tx) * ty + d * tx * ty


def actor_visual_position(actor, clip, phase, elevations, width, height, projection):
    """Project exactly one authoritative actor along a validated visual clip.

    Return None for unrelated/invalid clips. Results contain world-projection
    coordinates (before camera pan/zoom) and a presentation action token.
    They never update a tactical position, RNG, snapshot or save slot.
    """
    if not isinstance(actor, dict) or not isinstance(clip, dict):
        return None
    if (clip.get("actor") != actor.get("id") or
            clip.get("kind") not in MOTION_KINDS or
            type(phase) not in (int, float) or not isfinite(phase) or
            not (0 <= phase <= 1) or width < 1 or height < 1):
        return None
    start, end = _point(clip.get("start")), _point(clip.get("end"))
    if start is None or end is None:
        return None
    kind = clip["kind"]
    if kind == "move":
        t = phase * phase * (3 - 2 * phase)  # ease without overshoot
    elif kind == "attack":
        t = 0.25 * sin(pi * phase)  # strike and return
    else:
        t = 0.0
    x = start[0] + (end[0] - start[0]) * t
    y = start[1] + (end[1] - start[1]) * t
    # Clamp visual interpolation to the current board, not tactical state.
    x = min(max(x, 0.0), width - 1)
    y = min(max(y, 0.0), height - 1)
    elevation = _height(x, y, elevations, width, height)
    level = actor.get("level", 0)
    if type(level) is not int or level < 0:
        level = 0
    sx, sy = projection.project(x, y, elevation + level * 4)
    return {"sx": sx, "sy": sy, "kind": kind,
            "worldX": x, "worldY": y}


def automatic_cutaway(scene, *, selected=None, active_level=0,
                      positions=None):
    """IDs of structures whose roof must not obscure living occupants.

    Uses R6 authored structure identity/footprint when present, with no guess
    about doors, floors or tactical passability. Returns IDs, not geometry.
    """
    from sporebound.iso_structures import structure_template
    from sporebound.model import RuleError
    from collections.abc import Mapping
    if type(active_level) is not int or active_level < 0:
        raise ValueError("Active level must be a non-negative integer")
    occupants = positions or {}
    visible = set()
    for structure in scene.get("structures", ()):
        if not isinstance(structure, Mapping):
            continue
        identity = structure.get("id")
        anchor = _point(structure.get("anchor"))
        if not isinstance(identity, str) or not identity or anchor is None:
            continue
        try:
            template = structure_template(structure["name"], structure["turns"],
                                          door_slot=structure["door_slot"])
        except (KeyError, TypeError, ValueError, RuleError):
            continue
        x0, y0 = anchor
        inside = lambda x, y: x0 - .5 <= x < x0 + template.width - .5 and (
            y0 - .5 <= y < y0 + template.height - .5)
        if active_level or (selected is not None and inside(*selected)):
            visible.add(identity)
            continue
        for actor in scene.get("actors", ()):
            if not actor.get("alive", True):
                continue
            position = occupants.get(actor.get("id"))
            if position is None:
                position = (actor["x"], actor["y"])
            if inside(*position):
                visible.add(identity)
                break
    return tuple(sorted(visible))


def building_surfaces(scene, projection, *, selected=None, active_level=0,
                      actor_positions=None):
    """Visible presentation polygons for walls, roofs and authored floors.

    This is an R3 fallback for simple structures; R6's detailed surface
    geometry/picker can replace it once its authoring PR is integrated.
    Facade and roof coordinates are projected by the *same* IsoProjection.
    """
    from sporebound.iso_structures import structure_template
    from sporebound.model import RuleError

    hidden_roofs = set(automatic_cutaway(
        scene, selected=selected, active_level=active_level, positions=actor_positions))
    heights = {(t["x"], t["y"]): t["height"] for t in scene["tiles"]}
    surfaces = []
    for record in scene.get("structures", ()):
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            continue
        try:
            clip = structure_template(record["name"], record["turns"],
                                      door_slot=record["door_slot"])
        except (KeyError, TypeError, ValueError, RuleError):
            continue
        ax, ay = record["anchor"]
        if type(ax) is not int or type(ay) is not int:
            continue
        cells = [(ax + dx, ay + dy) for dx, dy in clip.offsets]
        if not cells:
            continue
        base = min(heights.get(cell, 0) for cell in cells)
        levels = sorted([f for f in scene.get("interior_floors", ())
                         if f.get("structure_id") == record["id"]],
                        key=lambda f: f["level"])
        top = base + 2.5 + 2 * len(levels)
        front = max(x + y for x, y in cells) * 100
        project = projection.project
        rx, by = ax + clip.width - .5, ay + clip.height - .5
        lx, ty = ax - .5, ay - .5

        def emit(part, corners, z, color, suffix, level=0):
            min_x = min(p[0] for p in corners)
            min_y = min(p[1] for p in corners)
            surfaces.append({
                "kind": "building", "id": "building:" + record["id"] + ":" + suffix,
                "structure_id": record["id"], "part": part, "level": level,
                "sx": min_x, "sy": min_y,
                "spanX": max(p[0] for p in corners) - min_x,
                "spanY": max(p[1] for p in corners) - min_y,
                "vertices": corners,
                "points": [[p[0] - min_x, p[1] - min_y] for p in corners],
                "color": color, "zOrder": z,
            })
        for x in range(clip.width):
            start, end = ax + x - .5, ax + x + .5
            emit("wall", [project(start, by, top), project(end, by, top),
                          project(end, by, base), project(start, by, base)],
                 front + 25, "#b59e80", "south:" + str(x))
        for y in range(clip.height):
            start, end = ay + y - .5, ay + y + .5
            emit("wall", [project(rx, start, top), project(rx, end, top),
                          project(rx, end, base), project(rx, start, base)],
                 front + 26, "#9b927e", "east:" + str(y))
        if record["id"] in hidden_roofs:
            # Floors are cosmetic decks; their gameplay collision remains R6.
            for floor in levels:
                if active_level and floor["level"] != active_level:
                    continue
                z = base + 1.8 + floor["level"] * 2
                for tile in floor.get("tiles", ()):
                    dx, dy = tile["pos"]
                    x, y = ax + dx, ay + dy
                    corners = [project(x, y-.5, z), project(x+.5, y, z),
                               project(x, y+.5, z), project(x-.5, y, z)]
                    emit("floor", corners, front + 23,
                         "#8a8c89" if tile["surface"] == "stone" else "#baad91",
                         "deck:%s:%s:%s" % (floor["level"], dx, dy),
                         floor["level"])
        else:
            emit("roof", [project(lx, ty, top), project(rx, ty, top),
                          project(rx, by, top), project(lx, by, top)],
                 front + 70, "#aa6254", "roof")
    return surfaces


def top_building_hit(rows, camera, x, y):
    """Pick the actual painted quadrilateral in reverse painter order."""
    wx, wy = camera.world(x, y)
    for row in sorted((r for r in rows if r["kind"] == "building"),
                      key=lambda r: (r["zOrder"], r["id"]), reverse=True):
        polygon = row["vertices"]
        inside = False
        x0, y0 = polygon[-1]
        for x1, y1 in polygon:
            cross = (wx - x0) * (y1 - y0) - (wy - y0) * (x1 - x0)
            if (abs(cross) <= 1e-7 and min(x0, x1) - 1e-7 <= wx <= max(x0, x1) + 1e-7
                    and min(y0, y1) - 1e-7 <= wy <= max(y0, y1) + 1e-7):
                inside = True
                break
            if (y1 > wy) != (y0 > wy):
                intersect = x0 + (x1-x0) * (wy-y0) / (y1-y0)
                if wx < intersect:
                    inside = not inside
            x0, y0 = x1, y1
        if inside:
            return {"kind": "building", "structure_id": row["structure_id"],
                    "part": row["part"], "level": row["level"]}
    return None

"""R36.B3 bounded top-down cell visibility from R26 authored opaque walls.

Diagnostic/software fallback only: no shader, shadow casting meshes, dynamic
occluder semantics, or gameplay line-of-sight authority. Geometry is detached.
"""
from __future__ import annotations

from math import hypot, isfinite

MAX_LIGHTS = 8
MAX_RADIUS_CELLS = 5
MAX_WIDTH = 128
MAX_HEIGHT = 128


def _visible(origin, target, opaque):
    """Integer Bresenham ray; target wall itself may be lit, never behind it."""
    x0, y0 = origin
    x1, y1 = target
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    error = dx - dy
    x, y = x0, y0
    while (x, y) != (x1, y1):
        twice = 2 * error
        if twice > -dy:
            error -= dy
            x += sx
        if twice < dx:
            error += dx
            y += sy
        if (x, y) != (x1, y1) and (x, y) in opaque:
            return False
    return True


def project_cell_lighting(scene, lights):
    """Return sparse string-keyed tile visibility strengths (0..1).

    Light centres come from committed, presentation-only R36 render records.
    Per-light radius is at most five cells and returns no authoritative LOS.
    """
    if (type(scene) is not dict or type(scene.get("width")) is not int or
            type(scene.get("height")) is not int or
            not 1 <= scene["width"] <= MAX_WIDTH or
            not 1 <= scene["height"] <= MAX_HEIGHT or
            type(scene.get("walls")) is not list or
            type(lights) is not list or len(lights) > MAX_LIGHTS):
        raise ValueError("Invalid bounded R36 cell lighting input")
    width, height = scene["width"], scene["height"]
    opaque = set()
    for wall in scene["walls"]:
        if (type(wall) is not list or len(wall) != 2 or
                any(type(v) is not int for v in wall) or
                not 0 <= wall[0] < width or not 0 <= wall[1] < height):
            raise ValueError("Invalid authored occlusion wall")
        opaque.add(tuple(wall))
    result = {}
    for source in lights:
        if (type(source) is not dict or
                any(type(source.get(k)) not in (float, int) or
                    not isfinite(source[k]) for k in ("x", "y", "radius", "alpha"))
                or source["radius"] < 0 or not 0 <= source["alpha"] <= 1):
            raise ValueError("Invalid 2D cosmetic light record")
        x, y = source["x"], source["y"]
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError("Visual light source outside R26 board")
        radius = min(MAX_RADIUS_CELLS, max(1, int(source["radius"] / 32)))
        origin = (int(x + .5), int(y + .5))
        for cy in range(max(0, origin[1] - radius), min(height, origin[1] + radius + 1)):
            for cx in range(max(0, origin[0] - radius), min(width, origin[0] + radius + 1)):
                distance = hypot(cx - x, cy - y)
                if distance > radius or not _visible(origin, (cx, cy), opaque):
                    continue
                strength = source["alpha"] * (1 - distance / (radius + 1))
                key = f"{cx}:{cy}"
                result[key] = round(min(1, result.get(key, 0) + strength), 5)
    return result

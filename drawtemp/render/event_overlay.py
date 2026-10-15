"""R9 event markers projected with the shared R3 isometric math.

Pure presentation-only helper: no Qt, Gameplay or duplicate tile renderer.
The Player does not ask for event markers and retains unchanged render_items.
"""
from __future__ import annotations

from .iso_scene import IsoProjection


def project_event_markers(scene, markers, *, selected_id="", projection=None,
                          max_markers=1000):
    """Convert validated canonical event cells into world-space ISO symbols.

    Using scene tile elevations avoids the flat XY overlay drift seen when the
    viewport pans, zooms or displays elevated cells. Marker order is stable.
    """
    projection = projection or IsoProjection()
    if not isinstance(markers, (list, tuple)):
        raise ValueError("Expected event marker list")
    if len(markers) > max_markers:
        raise ValueError("Event overlay exceeds the marker budget")
    heights = {(tile["x"], tile["y"]): tile["height"]
               for tile in scene["tiles"]}
    seen = set()
    projected = []
    for marker in markers:
        if not isinstance(marker, dict):
            raise ValueError("Invalid marker")
        mid = marker.get("event_id")
        kind = marker.get("kind")
        pos = marker.get("pos")
        if (not isinstance(mid, str) or not mid or
                kind not in ("trigger", "effect") or
                not isinstance(pos, (list, tuple)) or len(pos) != 2 or
                any(type(n) is not int for n in pos) or
                not (0 <= pos[0] < scene["width"] and
                     0 <= pos[1] < scene["height"])):
            raise ValueError("Event marker outside current mission")
        x, y = pos
        key = (mid, kind, x, y)
        if key in seen:
            continue
        seen.add(key)
        sx, sy = projection.project(x, y, heights.get((x, y), 0))
        projected.append({
            "event_id": mid, "kind": kind,
            "x": x, "y": y, "sx": sx, "sy": sy,
            "selected": mid == selected_id,
            "zOrder": (x + y) * 100 + 94,
        })
    return projected

"""R17.5: fail-closed render-contract comparisons for the R5 Studio and R12 Player.

Only visual semantics are compared. The R1 revision is not a pixel feature and
a live Battle can advance it without changing a tile, actor or building.
No screenshots are accepted as approved goldens by this module.
"""
from __future__ import annotations

from hashlib import sha256
import json


_SCENE_FIELDS = (
    "mission", "width", "height", "tiles", "actors", "objects",
    "structures", "interior_floors",
)
_CAMERA_FIELDS = ("zoom", "panX", "panY")


def _digest(value):
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()


def scene_visual_payload(scene):
    """Exclude journal revision; retain *all* visual terrain and world fields."""
    if not isinstance(scene, dict):
        raise ValueError("Renderer scene must be a dictionary")
    required = ("mission", "width", "height", "tiles", "actors", "objects")
    if any(field not in scene for field in required):
        raise ValueError("Incomplete canonical renderer scene")
    return {field: scene[field] for field in _SCENE_FIELDS if field in scene}


def _report_mismatch(a, b, *, limit=8):
    """Stable bounded errors: never hide order or missing scenegraph delegates."""
    if a == b:
        return []
    if isinstance(a, list) and isinstance(b, list):
        rows = []
        for i in range(max(len(a), len(b))):
            if i >= len(a) or i >= len(b) or a[i] != b[i]:
                rows.append({
                    "index": i,
                    "studio": a[i] if i < len(a) else None,
                    "player": b[i] if i < len(b) else None,
                })
                if len(rows) >= limit:
                    break
        return rows
    if isinstance(a, dict) and isinstance(b, dict):
        return [
            {"key": key, "studio": a.get(key), "player": b.get(key)}
            for key in sorted(set(a) | set(b)) if a.get(key) != b.get(key)
        ][:limit]
    return [{"studio": a, "player": b}]


def compare_controller_pair(studio, player, *, sample_cells=()):
    """Compare *real* RendererController instances, not fake renderer stubs.

    A failure returns concrete mismatches for authoring/rendering investigations.
    The caller must check report["passed"]; no tolerance silently applied.
    """
    a_scene = scene_visual_payload(studio.scene)
    b_scene = scene_visual_payload(player.scene)
    a_camera = dict(studio.cameraState)
    b_camera = dict(player.cameraState)
    a_rows, b_rows = list(studio.items), list(player.items)
    a_visible, b_visible = list(studio.displayItems), list(player.displayItems)
    a_batches, b_batches = list(studio.tileBatches), list(player.tileBatches)
    # Compare what the actual QML delegates receive, including depth ordering,
    # texture references, building polygons, atlases, overdraw and culling.
    comparisons = {
        "scene": (a_scene, b_scene),
        "camera": (a_camera, b_camera),
        "draw_order": (a_rows, b_rows),
        "visible_delegates": (a_visible, b_visible),
        "texture_batches": (a_batches, b_batches),
    }
    samples = []
    for x, y in sample_cells:
        if not (type(x) is int and type(y) is int and
                0 <= x < a_scene["width"] and 0 <= y < a_scene["height"]):
            raise ValueError("Sample must be a valid integer map cell")
        tile = next(
            (t for t in a_scene["tiles"] if (t["x"], t["y"]) == (x, y)), None)
        if tile is None:
            raise ValueError("Cannot sample an absent tile")
        sx, sy = studio.projection.project(x, y, tile["height"])
        screen_x, screen_y = studio.camera.screen(sx, sy)
        studio_hit = dict(studio.cellAt(screen_x, screen_y))
        player_hit = dict(player.cellAt(screen_x, screen_y))
        samples.append({"cell": [x, y], "screen": [screen_x, screen_y],
                        "studio": studio_hit, "player": player_hit})
    picks_match = all(row["studio"] == row["player"] for row in samples)
    failures = {
        key: _report_mismatch(left, right)
        for key, (left, right) in comparisons.items() if left != right
    }
    if not picks_match:
        failures["picking"] = [row for row in samples
                               if row["studio"] != row["player"]]
    return {
        "schema": 1, "kind": "drawtemp-r17-renderer-parity",
        "passed": not failures,
        "software_only": True,
        "studio": {name: _digest(a) for name, (a, _) in comparisons.items()},
        "player": {name: _digest(b) for name, (_, b) in comparisons.items()},
        "draw_counts": {"studio": len(a_rows), "player": len(b_rows)},
        "sample_picks": samples, "differences": failures,
    }


def assert_controller_parity(studio, player, *, sample_cells=()):
    report = compare_controller_pair(studio, player, sample_cells=sample_cells)
    if not report["passed"]:
        raise AssertionError(json.dumps(
            report["differences"], ensure_ascii=False, sort_keys=True)[:3500])
    return report

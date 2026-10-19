"""R24.F: repeatable CPU-side stress profiles for the SHARED R3 renderer.

Uses the real IsoViewport presentation functions (TileChunkIndex,
render_items) for indexed 32/64/128-tile scenes at three zooms. No fake GPU
timestamps: this only measures host-side Python indexing/culling/row creation.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import platform
import sys
from time import perf_counter_ns

from drawtemp.quality.r14 import frame_metrics
from drawtemp.render.iso_scene import Camera, IsoProjection, render_items
from drawtemp.render.tile_chunks import TileChunkIndex

SCHEMA = 1
MAP_SIZES = (32, 64, 128)
ZOOM_PX = (24, 54, 96)
MAX_SAMPLES = 60
MAX_ACTORS = 80


class ScaleProfileError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise ScaleProfileError(code, message)


def _fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")).hexdigest()


def synthetic_scene(size, *, actors=20):
    """Fixed geometry, never a hidden authored game or alternate renderer."""
    if type(size) is not int or size not in MAP_SIZES:
        _fail("invalid_size", "Supported map sizes: 32/64/128")
    if type(actors) is not int or not 0 <= actors <= MAX_ACTORS:
        _fail("invalid_actors", "Expected 0..80 actors")
    tiles = []
    for y in range(size):
        for x in range(size):
            props = ((x * 7 + y * 11) % 59) == 0
            relief = (x + 2 * y) % 37 == 0
            tiles.append({
                "x": x, "y": y, "height": 1 if relief else 0,
                "surface": "stone" if (x + y) % 5 == 0 else "grass",
                "feature": "crate" if props else "",
                "blocked": False, "cover": 15 if props else 0,
                "hazard": 0, "goal": False,
            })
    units = []
    for i in range(actors):
        x, y = (i * 19 + 3) % size, (i * 13 + 7) % size
        units.append({"id": f"stress-{i:02d}", "name": f"Stress {i}",
                      "x": x, "y": y, "team": "enemy" if i % 2 else "player",
                      "alive": True, "level": 0, "direction": "south"})
    return {"mission": "r24f-synthetic", "width": size, "height": size,
            "revision": 0, "tiles": tiles, "actors": units,
            "objects": [], "structures": [], "interior_floors": []}


def _camera(scene, zoom_px):
    camera = Camera(width=960, height=540)
    camera.zoom = zoom_px / IsoProjection().width
    center = IsoProjection().project((scene["width"] - 1) / 2,
                                     (scene["height"] - 1) / 2)
    camera.center(*center)
    return camera


def _millis(action):
    start = perf_counter_ns()
    result = action()
    return (perf_counter_ns() - start) / 1e6, result


def profile_cpu_renderer(*, sizes=MAP_SIZES, zooms=ZOOM_PX,
                         actors=20, samples=5, warmup=1,
                         max_visible_rows=20000):
    """Profile unchanged R3 drawing records; fail if visibility explodes.

    The same geometry/camera and deterministic row digest are checked across
    repeated calls. Durations are *not* reproducible across host machines.
    """
    if (type(sizes) not in (list, tuple) or not sizes or
            len(sizes) != len(set(sizes)) or
            any(type(s) is not int or s not in MAP_SIZES for s in sizes)):
        _fail("invalid_size", "Choose distinct 32/64/128 map sizes")
    if (type(zooms) not in (list, tuple) or not zooms or
            len(zooms) != len(set(zooms)) or
            any(type(z) is not int or z not in ZOOM_PX for z in zooms)):
        _fail("invalid_zoom", "Choose distinct 24/54/96 pixel zooms")
    if (type(actors) is not int or not 0 <= actors <= MAX_ACTORS or
            type(samples) is not int or not 2 <= samples <= MAX_SAMPLES or
            type(warmup) is not int or not 0 <= warmup <= 8 or
            type(max_visible_rows) is not int or
            not 1 <= max_visible_rows <= 20000):
        _fail("invalid_budget", "Invalid actors/samples/warmup/visible-row limit")
    rows = []
    for size in sizes:
        scene = synthetic_scene(size, actors=actors)
        scene_digest = _fingerprint(scene)
        index_ms, index = _millis(lambda: TileChunkIndex(scene))
        cell_count = len(index.tiles)
        if cell_count != size * size:
            _fail("invalid_index", "Chunk index lost terrain cells")
        for zoom in zooms:
            camera = _camera(scene, zoom)
            expected_digest = None
            observed = []
            total_rows = None
            for iteration in range(samples + warmup):
                def draw():
                    return render_items(scene, camera, tile_index=index)
                duration, output = _millis(draw)
                if len(output) > max_visible_rows:
                    _fail("row_budget", "More Qt presentation rows than allowed")
                # Deterministic terrain must yield identical ordered rows.
                digest = _fingerprint(output)
                if expected_digest is None:
                    expected_digest = digest
                    total_rows = len(output)
                elif expected_digest != digest:
                    _fail("nondeterministic_rows", "Visible R3 row order or contents changed")
                if iteration >= warmup:
                    observed.append(duration)
            # Actual dirty update path, not full re-creation of the index.
            changed = deepcopy(scene)
            changed["tiles"][0]["cover"] ^= 1
            update_ms, dirty = _millis(lambda: index.update(changed))
            if dirty != {(0, 0)}:
                _fail("invalid_invalidation", "Incremental chunk invalidation differs")
            unchanged_ms, unchanged = _millis(lambda: index.update(changed))
            if unchanged:
                _fail("invalid_invalidation", "Unchanged chunk index was dirty")
            # Restore original geometry and verify renderer output equivalence.
            restored = index.update(scene)
            if restored != {(0, 0)}:
                _fail("invalid_invalidation", "Failed to restore original terrain")
            if _fingerprint(render_items(scene, camera, tile_index=index)) != expected_digest:
                _fail("parity_mismatch", "Chunk update lost visible renderer parity")
            rows.append({
                "map_size": size, "zoom_px": zoom, "actors": actors,
                "scene_sha256": scene_digest,
                "index_build_ms": round(index_ms, 4),
                "dirty_update_ms": round(update_ms, 4),
                "unchanged_update_ms": round(unchanged_ms, 4),
                "terrain_tiles": cell_count,
                "indexed_chunks": len(index.chunks),
                "visible_rows": total_rows,
                "visible_rows_sha256": expected_digest,
                "measurements_ms": [round(v, 4) for v in observed],
                **frame_metrics(observed),
            })
    return {
        "schema": SCHEMA, "kind": "r24f-r3-cpu-scale",
        "scope": ("Python-side index, culling and sorted presentation rows only; "
                  "not Qt GPU upload, frameSwapped, driver FPS or VRAM"),
        "environment": {"os": platform.system(),
                        "python": sys.version.split()[0],
                        "machine": platform.machine()},
        "workload": {"sizes": list(sizes), "zooms": list(zooms),
                     "actors": actors, "samples": samples, "warmup": warmup,
                     "viewport": [960, 540], "max_visible_rows": max_visible_rows},
        "cases": rows, "software_only": True,
        "gpu_certified": False, "hardware_frame_times_available": False,
    }


def compare_cpu_scale(before, after, *, p95_tolerance=0.5,
                      allow_environment_change=False):
    """Optional host-side regression gate. Same workload/environment required.

    Must not be used as proof of the R14 GPU 60FPS hardware budget.
    """
    for report in (before, after):
        if (type(report) is not dict or report.get("schema") != SCHEMA or
                report.get("kind") != "r24f-r3-cpu-scale" or
                report.get("software_only") is not True or
                type(report.get("cases")) is not list or not report["cases"]):
            _fail("invalid_report", "Expected a complete software-only renderer profile")
    if before["workload"] != after["workload"]:
        _fail("incompatible_workload", "Profile workloads must be identical")
    if not allow_environment_change and before["environment"] != after["environment"]:
        _fail("incompatible_environment", "Profiles must use the same host class")
    if (type(p95_tolerance) not in (int, float) or
            not isfinite(p95_tolerance) or not 0 <= p95_tolerance <= 5):
        _fail("invalid_budget", "Invalid p95 growth tolerance")
    old = {(row["map_size"], row["zoom_px"]): row for row in before["cases"]}
    new = {(row["map_size"], row["zoom_px"]): row for row in after["cases"]}
    if len(old) != len(before["cases"]) or len(new) != len(after["cases"]) or set(old) != set(new):
        _fail("incompatible_workload", "Case matrix changed")
    issues = []
    comparisons = []
    for key in sorted(old):
        first, latest = old[key], new[key]
        if (first["scene_sha256"] != latest["scene_sha256"] or
                first["visible_rows_sha256"] != latest["visible_rows_sha256"] or
                first["visible_rows"] != latest["visible_rows"]):
            _fail("incompatible_scene", "Scene or visible rows changed")
        ratio = ((latest["p95_ms"] - first["p95_ms"]) /
                 max(first["p95_ms"], 0.0001))
        if ratio > p95_tolerance:
            issues.append(f"{key[0]}x{key[0]} zoom={key[1]} CPU p95 regressed")
        comparisons.append({"map_size": key[0], "zoom_px": key[1],
                            "p95_growth": round(ratio, 4)})
    return {"schema": SCHEMA, "kind": "r24f-cpu-scale-comparison",
            "passed": not issues, "issues": issues,
            "comparisons": comparisons, "gpu_certified": False}


def save_cpu_scale_report(path, report):
    if type(report) is not dict or report.get("kind") != "r24f-r3-cpu-scale":
        _fail("invalid_report", "Expected R24.F CPU scale report")
    output = Path(path)
    if output.is_symlink():
        _fail("unsafe_path", "Cannot write a symlinked report")
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    return output

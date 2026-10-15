"""Reproducible R3 CPU projection benchmark (NOT a GPU FPS certification).

Records visible items and p50/p95/p99 CPU times for pan/zoom using the shared
chunk index. Materialized Qt Quick nodes and actual GPU frame timings are
deliberately outside this headless metric.
"""
import argparse
import json
import math
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter

from drawtemp.render import Camera, IsoProjection, TileChunkIndex, render_items


def make_scene(size):
    return {"mission": "benchmark", "width": size, "height": size,
            "revision": 0, "tiles": [
                {"x": x, "y": y, "height": (x // 12 + y // 16) % 4,
                 "surface": ("grass", "dirt", "stone", "water")[(x // 8 + y // 8) % 4],
                 "feature": "", "blocked": False, "cover": 0, "hazard": 0,
                 "goal": False}
                for y in range(size) for x in range(size)
            ], "actors": [], "objects": []}


def quantile(values, fraction):
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def measure(size, frames):
    scene = make_scene(size)
    projection = IsoProjection()
    camera = Camera(width=960, height=640)
    index = TileChunkIndex(scene)
    elapsed, counts = [], []
    for frame in range(frames):
        # Deterministic tour through the map and camera zoom levels.
        cell = (size * (0.2 + 0.6 * (frame % 17) / 16),
                size * (0.2 + 0.6 * (frame % 11) / 10))
        camera.zoom = (0.6, 1.0, 1.6, 2.4)[frame % 4]
        camera.center(*projection.project(*cell))
        started = perf_counter()
        items = render_items(scene, camera, projection, tile_index=index)
        elapsed.append((perf_counter() - started) * 1000)
        counts.append(len(items))
    return {"map": f"{size}x{size}", "frames": frames,
            "visible_min": min(counts), "visible_max": max(counts),
            "cpu_ms_p50": round(statistics.median(elapsed), 3),
            "cpu_ms_p95": round(quantile(elapsed, .95), 3),
            "cpu_ms_p99": round(quantile(elapsed, .99), 3)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=80)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not 5 <= args.frames <= 2000:
        parser.error("--frames must be in 5..2000")
    result = {"type": "CPU projection only, not GPU",
              "python": platform.python_version(), "os": platform.platform(),
              "backend": "headless", "resolution": "960x640",
              "profiles": [measure(s, args.frames) for s in (32, 64, 128)]}
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

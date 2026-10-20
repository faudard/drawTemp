"""R52.C1 deterministic headless CPU culling benchmark, not a GPU claim.

Usage:
  python scripts/benchmark_r52_c1.py --frames 80 --size 128 --output r52c1.json
Measures the SAME shared rendering/projection code with bounded cache on/off.
No implicit release gate or claimed speedup; inspect p95/p99 across platforms.
"""
import argparse
import json
import math
import platform
from pathlib import Path
from statistics import median
from time import perf_counter

from drawtemp.render.iso_scene import (Camera, IsoProjection, TopDownProjection,
                                       SideProjection, render_items)
from drawtemp.render.tile_chunks import TileChunkIndex


PROJECTIONS = {"isometric": IsoProjection, "top_down": TopDownProjection,
               "side": SideProjection}


def percentile(samples, percent):
    if not samples or not 0 <= percent <= 100:
        raise ValueError("Percentile requires observations and 0..100 range")
    values = sorted(samples)
    return round(values[max(0, math.ceil(percent / 100 * len(values)) - 1)], 4)


def scene_for_benchmark(size):
    if type(size) is not int or not 16 <= size <= 256:
        raise ValueError("Benchmark map must be 16..256 cells wide")
    return {
        "mission": "r52c1-benchmark", "width": size, "height": size,
        "revision": 0,
        "tiles": [{
            "x": x, "y": y, "height": 2 if (x+y) % 19 == 0 else 0,
            "surface": ("grass", "stone", "dirt")[(x//8 + y//8) % 3],
            "feature": "", "blocked": False, "cover": 0, "hazard": 0,
            "goal": False,
        } for y in range(size) for x in range(size)],
        "actors": [], "objects": [], "structures": [], "interior_floors": [],
    }


def sample(size, frames, mode, *, cache_enabled):
    if mode not in PROJECTIONS:
        raise ValueError("Unknown projection")
    if type(frames) is not int or not 5 <= frames <= 2000:
        raise ValueError("Frames must be in 5..2000")
    scene = scene_for_benchmark(size)
    index = TileChunkIndex(scene, visibility_budget=256 * 1024 if cache_enabled else 1)
    camera = Camera(width=960, height=640)
    projection = PROJECTIONS[mode]()
    elapsed = []
    counts = []
    digests = []
    for i in range(frames):
        # Repeated view at i+1 exercises reuse; every fourth pair moves/zooms.
        j = i // 2
        x = size * (0.25 + 0.5 * ((j % 11) / 10))
        y = size * (0.25 + 0.5 * ((j % 7) / 6))
        camera.zoom = (0.7, 1, 1.7, 2.4)[(j // 2) % 4]
        camera.center(*projection.project(x, y))
        t0 = perf_counter()
        rows = render_items(scene, camera, projection, tile_index=index)
        elapsed.append((perf_counter() - t0) * 1000)
        counts.append(len(rows))
        # Keep parity evidence tied to actual scene records, not timings.
        digests.append((len(rows),
                        tuple(row["id"] for row in rows[:3]),
                        tuple(row["id"] for row in rows[-3:])))
    stats = index.visibility_stats
    return {
        "mode": mode, "cache_enabled": cache_enabled,
        "map": "%dx%d" % (size, size), "frames": frames,
        "visible_min": min(counts), "visible_max": max(counts),
        "cpu_ms_p50": round(median(elapsed), 4),
        "cpu_ms_p95": percentile(elapsed, 95),
        "cpu_ms_p99": percentile(elapsed, 99),
        "cache": stats,
        "output_signature": digests,
    }


def benchmark(size=128, frames=80):
    profiles = []
    for mode in PROJECTIONS:
        baseline = sample(size, frames, mode, cache_enabled=False)
        optimized = sample(size, frames, mode, cache_enabled=True)
        if optimized.pop("output_signature") != baseline.pop("output_signature"):
            raise RuntimeError("R52 cache changed shared render records: " + mode)
        profiles.append({
            "mode": mode,
            "baseline": baseline, "bounded_cache": optimized,
            "ratio_p95_cached_vs_baseline": (
                round(optimized["cpu_ms_p95"] / baseline["cpu_ms_p95"], 3)
                if baseline["cpu_ms_p95"] > 0 else None),
        })
    return {
        "type": "R52.C1 headless CPU projection and culling only",
        "map": "%dx%d" % (size, size),
        "frames": frames,
        "environment": {
            "python": platform.python_version(), "os": platform.platform(),
            "backend": "headless", "qt": False,
        },
        "physical_gpu_verified": False, "renderer_parity": True,
        "profiles": profiles,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=80)
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not 5 <= args.frames <= 2000:
        parser.error("--frames must be in 5..2000")
    if not 16 <= args.size <= 256:
        parser.error("--size must be in 16..256")
    data = benchmark(args.size, args.frames)
    output = json.dumps(data, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

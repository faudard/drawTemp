"""R35.10 opt-in profiling of 256 spatial NPCs and cached portal legs.

Run from the repository root:
    python -m tools.bench_r35_living_world

Numbers are measurements, not claimed pass/fail budgets. Pin machine,
Python version and commit SHA before comparing two reports.
"""
from __future__ import annotations

import json
import statistics
import sys
from time import perf_counter_ns
import tracemalloc

from sporebound.living_world import LivingWorld
from tests_standalone.test_r35_transfers import two_village_world


def benchmark(npcs=256, samples=200):
    if type(npcs) is not int or not 1 <= npcs <= 256:
        raise ValueError("NPCs must be in 1..256")
    if type(samples) is not int or not 20 <= samples <= 10000:
        raise ValueError("Samples must be in 20..10000")
    spec, stages = two_village_world()
    prototype = spec["npcs"][0]
    spec["npcs"] = [
        {"id": "courier_" + str(i), "schedule": [
            dict(stop) for stop in prototype["schedule"]]}
        for i in range(npcs)]
    tracemalloc.start()
    setup_start = perf_counter_ns()
    world = LivingWorld(spec, set(stages), exploration=stages)
    build_ns = perf_counter_ns() - setup_start
    _, setup_peak_bytes = tracemalloc.get_traced_memory()
    measurements = []
    # Warm up runtime caches and interpreter code paths before sampling.
    for _ in range(20):
        world.view({})
    for i in range(samples):
        world.advance(1)
        start = perf_counter_ns()
        result = world.view({})
        measurements.append(perf_counter_ns() - start)
        if len(result["npcs"]) != npcs:
            raise AssertionError("Projection dropped NPC identities")
    _, total_peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    ordered = sorted(measurements)
    def percentile(p):
        return ordered[min(len(ordered)-1, int((len(ordered)-1)*p))] / 1_000_000
    return {
        "python": sys.version.split()[0],
        "npc_count": npcs,
        "sample_count": samples,
        "build_ms": round(build_ns / 1_000_000, 3),
        "projection_ms": {
            "p50": round(percentile(.50), 4),
            "p95": round(percentile(.95), 4),
            "p99": round(percentile(.99), 4),
            "max": round(max(measurements) / 1_000_000, 4)},
        "setup_peak_bytes": setup_peak_bytes,
        "total_peak_bytes": total_peak_bytes,
        "method": "headless, no GPU; tracemalloc included in measurements",
        "validated": False,
    }


def main():
    print(json.dumps(benchmark(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

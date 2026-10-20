"""R36.C1 bounded CPU-side renderer telemetry (NOT a GPU benchmark).

Record the actual Qt renderer's scene-publish duration and scenegraph-item
counts without affecting ticks or gameplay. Wall-time percentiles are
observational and must be measured on real target hardware before release.
"""
from __future__ import annotations

from collections import deque
from math import ceil, isfinite

MAX_SAMPLES = 4096
MAX_PARTICLES = 128
MAX_LIGHTS = 8
MAX_ACTORS = 33
MAX_FX = 96


class R36FrameBudget:
    def __init__(self, *, capacity=600):
        if type(capacity) is not int or not 1 <= capacity <= MAX_SAMPLES:
            raise ValueError("Invalid R36 profiling sample capacity")
        self._frames = deque(maxlen=capacity)
        self._last_tick = -1

    def record(self, *, tick, duration_ns, items, actors, particles, lights,
               fx):
        """Measure one render submission, never advance the simulation."""
        values = (tick, duration_ns, items, actors, particles, lights, fx)
        if (any(type(value) is not int for value in values) or
                tick < self._last_tick or duration_ns < 0 or
                not 0 <= items <= 20000 or not 0 <= actors <= MAX_ACTORS or
                not 0 <= particles <= MAX_PARTICLES or
                not 0 <= lights <= MAX_LIGHTS or not 0 <= fx <= MAX_FX):
            raise ValueError("Invalid R36 scene-publish telemetry")
        self._last_tick = tick
        self._frames.append({
            "tick": tick,
            "cpu_ns": duration_ns,
            "items": items,
            "actors": actors,
            "particles": particles,
            "lights": lights,
            "fx": fx,
        })

    def report(self):
        """Nearest-rank p50/p95/p99 of CPU submission latency, no FPS fiction."""
        rows = list(self._frames)
        if not rows:
            return {"samples": 0, "cpu_ms": None, "max_items": 0,
                    "max_actors": 0, "max_particles": 0,
                    "max_lights": 0, "max_fx": 0, "sample_clock": "logical_tick"}
        durations = sorted(row["cpu_ns"] for row in rows)

        def percentile(p):
            return round(durations[max(0, ceil(len(durations) * p) - 1)]
                         / 1_000_000, 4)

        return {
            "samples": len(rows),
            "cpu_ms": {"p50": percentile(.50), "p95": percentile(.95),
                       "p99": percentile(.99), "max": round(durations[-1] / 1_000_000, 4)},
            "max_items": max(row["items"] for row in rows),
            "max_actors": max(row["actors"] for row in rows),
            "max_particles": max(row["particles"] for row in rows),
            "max_lights": max(row["lights"] for row in rows),
            "max_fx": max(row["fx"] for row in rows),
            "sample_clock": "logical_tick",
        }

    def reset(self):
        self._frames.clear()
        self._last_tick = -1

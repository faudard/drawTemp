"""R36.C1 bounded CPU render-submit telemetry tests; no fabricated GPU FPS."""
from __future__ import annotations

import unittest

from drawtemp.render.r36_frame_budget import R36FrameBudget


class R36RenderTelemetryTests(unittest.TestCase):
    def test_nearest_rank_percentiles_and_bounds(self):
        measured = R36FrameBudget(capacity=200)
        for tick in range(1, 101):
            measured.record(
                tick=tick, duration_ns=tick * 1_000_000,
                items=250, actors=2, particles=8, lights=1, fx=3)
        result = measured.report()
        self.assertEqual(result["samples"], 100)
        self.assertEqual(result["cpu_ms"],
                         {"p50": 50., "p95": 95., "p99": 99., "max": 100.})
        self.assertEqual(result["max_items"], 250)
        self.assertEqual(result["max_particles"], 8)
        self.assertEqual(result["max_lights"], 1)
        self.assertEqual(result["sample_clock"], "logical_tick")
        self.assertEqual(measured.report(), result)
        measured.reset()
        self.assertEqual(measured.report()["samples"], 0)
        self.assertIsNone(measured.report()["cpu_ms"])

    def test_ring_buffer_caps_memory_and_allows_duplicate_redraws(self):
        recorder = R36FrameBudget(capacity=3)
        for i in range(80):
            recorder.record(tick=i // 4, duration_ns=i * 1000, items=3,
                            actors=1, particles=0, lights=0, fx=0)
        report = recorder.report()
        self.assertEqual(report["samples"], 3)
        self.assertEqual(report["cpu_ms"]["max"], 0.079)

    def test_refuses_unsafe_counts_or_rewinding_without_reset(self):
        recorder = R36FrameBudget()
        invalid = [
            {"tick": -1}, {"tick": True}, {"duration_ns": -1},
            {"duration_ns": 2.5}, {"items": 20001}, {"actors": 34},
            {"particles": 129}, {"lights": 9}, {"fx": 97},
        ]
        expected = {"tick": 1, "duration_ns": 123000,
                    "items": 30, "actors": 1, "particles": 2,
                    "lights": 1, "fx": 3}
        for edit in invalid:
            data = {**expected, **edit}
            with self.subTest(data=data), self.assertRaises(ValueError):
                recorder.record(**data)
        self.assertEqual(recorder.report()["samples"], 0)
        recorder.record(**expected)
        with self.assertRaises(ValueError):
            recorder.record(**{**expected, "tick": 0})
        self.assertEqual(recorder.report()["samples"], 1)
        for capacity in (0, 4097, True):
            with self.assertRaises(ValueError):
                R36FrameBudget(capacity=capacity)


if __name__ == "__main__":
    unittest.main()

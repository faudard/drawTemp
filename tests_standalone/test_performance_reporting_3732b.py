"""3.7.32B: defensive report comparison and opt-in Tk trace contracts."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.compare_profile_scale_3732 import compare, markdown, measurements
from scripts.summarize_ui_trace_3732 import summarize
from sporebound import performance_trace


def example_report(p50=5.0, p95=8.0, p99=10.0):
    return {
        "schema": "drawtemp-performance-scale-v1",
        "source_sha": "baseline",
        "environment": {
            "platform": "linux-reference", "python": "3.12",
            "architecture": "x86_64", "logical_cpus": 8, "tk_patchlevel": 8.6,
        },
        "parameters": {
            "phase": "all", "sizes": [32], "cells": [24], "frames": 100,
            "samples": 100, "resources": 200, "events": 160,
            "short_saves": 5, "long_saves": 60, "assets": False,
            "quick": False,
        },
        "headless": [{
            "operation": "studio_index_search",
            "p50_ms": p50, "p95_ms": p95, "p99_ms": p99,
            "rss_bytes": 12_000_000,
        }],
        "gui": {
            "editor": [{
                "map": "32", "cell_size": 24, "assets": False,
                "modes": {
                    "retained": {"operations": {
                        "selection": {
                            "p50_ms": p50, "p95_ms": p95, "p99_ms": p99,
                        },
                    }},
                },
            }],
            "player": [{
                "mission": "p0_01_lame", "actors": 80,
                "cell_size": 24, "pan": False,
                "p50_ms": p50, "p95_ms": p95,
                "p99_ms": p99, "canvas_items": 123,
            }],
        },
    }


class ReportComparisonTests(unittest.TestCase):
    def test_flatten_all_existing_benchmark_paths(self):
        rows = measurements(example_report())
        self.assertEqual(len(rows), 3)
        self.assertIn("headless/studio_index_search", rows)
        self.assertTrue(any(x.startswith("editor/map=32/cell=24") for x in rows))
        self.assertTrue(any(x.startswith("player/mission=p0_01_lame") for x in rows))

    def test_identical_runs_have_zero_deltas(self):
        a = example_report()
        b = deepcopy(a)
        b["source_sha"] = "candidate"
        report = compare(a, b)
        self.assertFalse(report["blocked"])
        self.assertTrue(report["compatible"])
        self.assertEqual(len(report["comparisons"]), 3)
        self.assertTrue(all(
            row["latency"]["p95_ms"]["delta_ms"] == 0
            for row in report["comparisons"]))
        self.assertIn("p95", markdown(report))

    def test_optional_gate_only_blocks_above_both_budgets(self):
        a, b = example_report(), example_report(5, 9, 12)
        self.assertEqual(compare(a, b)["blocked"], [])
        self.assertTrue(compare(
            a, b, block_p95_pct=10, block_min_ms=0.2)["blocked"])
        self.assertFalse(compare(
            a, b, block_p95_pct=10, block_min_ms=2.0)["blocked"])
        self.assertTrue(compare(a, b, block_p99_pct=5)["blocked"])

    def test_refuse_different_environment_or_scenario(self):
        a, b = example_report(), example_report()
        b["environment"]["python"] = "3.14"
        with self.assertRaisesRegex(ValueError, "Environment mismatch"):
            compare(a, b)
        inspection = compare(a, b, allow_host_mismatch=True)
        self.assertFalse(inspection["compatible"])
        b = example_report()
        b["parameters"]["cells"] = [54]
        with self.assertRaisesRegex(ValueError, "parameters differ"):
            compare(a, b)
        b = example_report()
        b["gui"]["editor"] = []
        with self.assertRaisesRegex(ValueError, "Scenario mismatch"):
            compare(a, b)

    def test_reject_unknown_schema_and_absent_samples(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            measurements({"schema": "other"})
        with self.assertRaisesRegex(ValueError, "No comparable"):
            measurements({"schema": "drawtemp-performance-scale-v1"})
        with self.assertRaisesRegex(ValueError, "Missing percentile"):
            measurements({"schema": "drawtemp-performance-scale-v1",
                          "headless": [{"operation": "x"}]})


class FakeWidget:
    def __init__(self):
        self.callbacks = []

    def after_idle(self, callback):
        self.callbacks.append(callback)


class UiTraceTests(unittest.TestCase):
    def test_tracing_disabled_does_not_schedule_or_write(self):
        widget = FakeWidget()
        with patch.object(performance_trace, "TRACE_PATH", ""):
            self.assertIsNone(performance_trace.begin_ui())
            performance_trace.finish_ui("map.refresh", None, widget)
        self.assertEqual(widget.callbacks, [])

    def test_opt_in_jsonl_records_numeric_counts_without_editor_data(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "perf" / "ui.jsonl"
            widget = FakeWidget()
            with patch.object(performance_trace, "TRACE_PATH", str(path)):
                start = performance_trace.begin_ui()
                performance_trace.finish_ui(
                    "workspace.refresh", start, widget,
                    counts={"resources": 120, "title": "private project"})
                self.assertFalse(path.exists())
                self.assertEqual(len(widget.callbacks), 1)
                widget.callbacks.pop()()
            row = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(row["operation"], "workspace.refresh")
            self.assertGreaterEqual(row["callback_to_idle_ms"],
                                    row["callback_ms"])
            self.assertEqual(row["counts"], {"resources": 120})
            self.assertNotIn("private project", json.dumps(row))

    def test_relative_trace_path_is_ignored(self):
        widget = FakeWidget()
        with patch.object(performance_trace, "TRACE_PATH", "relative.jsonl"):
            performance_trace.finish_ui(
                "map.refresh", performance_trace.begin_ui(), widget)
            widget.callbacks.pop()()



class UiSummaryTests(unittest.TestCase):
    def test_bucket_by_scene_complexity_and_percentiles(self):
        samples = []
        for count in (32 * 32, 64 * 64):
            for i in range(5):
                samples.append(json.dumps({
                    "schema": "drawtemp-ui-trace-v1",
                    "operation": "map.refresh",
                    "counts": {"map_cells": count, "canvas_items": 5 + i},
                    "callback_ms": 1 + i,
                    "callback_to_idle_ms": 2 + i,
                    "queued_idle_ms": 1,
                }))
        report = summarize(samples)
        self.assertEqual(len(report["groups"]), 2)
        self.assertEqual([g["complexity_value"] for g in report["groups"]],
                         [32 * 32, 64 * 64])
        for group in report["groups"]:
            self.assertEqual(group["samples"], 5)
            self.assertFalse(group["sufficient_for_tail_exploration"])
            self.assertIn("p99_ms", group["timings"]["callback_to_idle_ms"])

    def test_invalid_trace_records_are_refused(self):
        with self.assertRaisesRegex(ValueError, "No valid"):
            summarize([])
        with self.assertRaisesRegex(ValueError, "Unexpected trace schema"):
            summarize([json.dumps({"schema": "bad"})])
        with self.assertRaisesRegex(ValueError, "Missing scene complexity"):
            summarize([json.dumps({"schema": "drawtemp-ui-trace-v1",
                                   "operation": "map.refresh"})])


if __name__ == "__main__":
    unittest.main()

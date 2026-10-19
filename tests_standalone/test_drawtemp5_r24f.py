"""R24.F: repeatable CPU renderer / bounded multi-seed R13 Battle Lab gates."""
from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content
from drawtemp.quality.r24f_scale import (
    ScaleProfileError, synthetic_scene, profile_cpu_renderer,
    compare_cpu_scale, save_cpu_scale_report,
)
from drawtemp.sdk import SDK_FEATURES, MassiveSimulationJob, compare_massive_runs
from drawtemp.sdk.r24f_mass_lab import save_massive_report
from sporebound.model import RuleError


def asterion():
    return Content.load(files("drawtemp").joinpath("creator_examples/asterion.json"))


class R24FMassLabTests(unittest.TestCase):
    def test_native_replay_seeds_are_repeatable_and_source_unmodified(self):
        content = asterion()
        baseline = deepcopy(content.to_dict())
        self.assertIn("massive-simulation.v1", SDK_FEATURES)
        def once():
            job = MassiveSimulationJob(
                content, "signal_depot", seeds=(1, 17, 221),
                max_commands=9)
            snapshots = []
            while not job.finished:
                progress = job.step()
                self.assertTrue(progress["replay_verified"])
                self.assertEqual(progress["completed"], len(snapshots) + 1)
                snapshots.append(progress)
            self.assertIsNone(job.step())
            self.assertEqual(job.remaining, 0)
            result = job.report()
            self.assertEqual(result["completed"], 3)
            self.assertEqual(result["status"], "completed")
            self.assertTrue(result["all_replays_verified"])
            self.assertEqual([r["seed"] for r in result["samples"]], [1, 17, 221])
            self.assertEqual(sum(result["outcomes"].values()), 3)
            self.assertEqual(len(result["telemetry"]["per_seed"]), 3)
            self.assertTrue(all(x is not None for key, x in result["telemetry"].items()
                                if key.endswith(("_p50", "_p95", "_p99"))))
            return result
        first, second = once(), once()
        self.assertEqual(content.to_dict(), baseline)
        self.assertEqual(first["deterministic_sha256"], second["deterministic_sha256"])
        self.assertEqual(first["samples"], second["samples"])
        self.assertTrue(compare_massive_runs(first, second)["passed"])

    def test_cancel_is_cooperative_and_incomplete_reports_never_pass_gate(self):
        content = asterion()
        before = content.to_dict()
        job = MassiveSimulationJob(content, "signal_depot", seeds=(1, 2, 3),
                                   max_commands=6)
        first = job.step()
        self.assertEqual(first["completed"], 1)
        job.cancel()
        self.assertIsNone(job.step())
        report = job.report()
        self.assertEqual(report["status"], "cancelled")
        self.assertEqual(report["completed"], 1)
        self.assertEqual(report["seeds_completed"], [1])
        self.assertEqual(content.to_dict(), before)
        with self.assertRaises(RuleError):
            compare_massive_runs(report, report)
        with TemporaryDirectory() as folder:
            destination = Path(folder) / "cancelled.json"
            save_massive_report(destination, report)
            self.assertEqual(json.loads(destination.read_text())["status"], "cancelled")
            with self.assertRaises(FileExistsError):
                save_massive_report(destination, report)

    def test_invalid_budgets_and_comparison_mismatch_fail_closed(self):
        content = asterion()
        for kwargs in (
            {"seeds": ()}, {"seeds": (1, 1)}, {"seeds": (True,)},
            {"seeds": (-1,)}, {"seeds": (2**32,)},
            {"max_commands": 0}, {"max_commands": 1501},
            {"seeds": tuple(range(100)), "max_commands": 600},
            {"max_total_commands": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(RuleError):
                MassiveSimulationJob(content, "signal_depot", **kwargs)
        with self.assertRaises(RuleError):
            MassiveSimulationJob(content, "not_a_mission")
        first = MassiveSimulationJob(content, "signal_depot",
                                     seeds=(1,), max_commands=5).run()
        other = deepcopy(first)
        other["seeds_requested"] = [99]
        with self.assertRaises(RuleError):
            compare_massive_runs(first, other)
        other = deepcopy(first)
        other["samples"][0]["digest"] = "f" * 64
        self.assertFalse(compare_massive_runs(first, other)["passed"])

    def test_no_ui_dependency_in_massive_sdk(self):
        program = """
import sys
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("tkinter", "PySide6", "PyQt5", "PyQt6"):
            raise RuntimeError("Unexpected UI: " + fullname)
sys.meta_path.insert(0, Guard())
from drawtemp.sdk import MassiveSimulationJob
from drawtemp.quality.r24f_scale import synthetic_scene
from drawtemp.core import Content
from importlib.resources import files
content = Content.load(files("drawtemp").joinpath("creator_examples/asterion.json"))
report = MassiveSimulationJob(content, "signal_depot", seeds=(1,), max_commands=5).run()
assert report["all_replays_verified"]
assert synthetic_scene(32)["width"] == 32
"""
        result = subprocess.run([sys.executable, "-c", program],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=75)
        self.assertEqual(result.returncode, 0, result.stderr)


class R24FRendererScaleTests(unittest.TestCase):
    def test_32_64_128_real_r3_cpu_profiles_no_gpu_claim(self):
        report = profile_cpu_renderer(
            sizes=(32, 64, 128), zooms=(24, 54, 96),
            actors=12, samples=2, warmup=0)
        self.assertEqual(len(report["cases"]), 9)
        self.assertEqual({r["map_size"] for r in report["cases"]}, {32, 64, 128})
        self.assertFalse(report["gpu_certified"])
        self.assertFalse(report["hardware_frame_times_available"])
        self.assertTrue(report["software_only"])
        for row in report["cases"]:
            self.assertEqual(row["terrain_tiles"], row["map_size"] ** 2)
            self.assertGreater(row["visible_rows"], 0)
            self.assertLessEqual(row["visible_rows"], 20000)
            self.assertGreaterEqual(row["p99_ms"], row["p95_ms"])
            self.assertGreaterEqual(row["p95_ms"], row["p50_ms"])
            self.assertEqual(len(row["visible_rows_sha256"]), 64)
        self.assertTrue(compare_cpu_scale(report, deepcopy(report))["passed"])

    def test_r3_scene_and_index_are_presentation_only(self):
        scene = synthetic_scene(32, actors=80)
        original = deepcopy(scene)
        report = profile_cpu_renderer(
            sizes=(32,), zooms=(96,), actors=80, samples=2, warmup=1)
        self.assertEqual(len(report["cases"]), 1)
        self.assertEqual(scene, original)
        self.assertEqual(len(scene["actors"]), 80)

    def test_fail_closed_for_invalid_workload_gpu_and_regressions(self):
        for kwargs in (
            {"sizes": (16,)}, {"zooms": (12,)},
            {"actors": 81}, {"samples": 1}, {"samples": 61},
            {"warmup": -1}, {"max_visible_rows": 0},
            {"sizes": (32, 32)},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ScaleProfileError):
                profile_cpu_renderer(**kwargs)
        report = profile_cpu_renderer(
            sizes=(32,), zooms=(96,), actors=1, samples=2, warmup=0)
        slower = deepcopy(report)
        slower["cases"][0]["p95_ms"] = max(report["cases"][0]["p95_ms"] * 5, 1.0)
        verdict = compare_cpu_scale(report, slower, p95_tolerance=0.1)
        self.assertFalse(verdict["passed"])
        other = deepcopy(report)
        other["workload"]["actors"] = 2
        with self.assertRaises(ScaleProfileError):
            compare_cpu_scale(report, other)
        other = deepcopy(report)
        other["environment"]["os"] = "not-the-same"
        with self.assertRaises(ScaleProfileError):
            compare_cpu_scale(report, other)
        with TemporaryDirectory() as folder:
            output = Path(folder) / "r24f.json"
            save_cpu_scale_report(output, report)
            self.assertEqual(json.loads(output.read_text())["kind"], "r24f-r3-cpu-scale")
            with self.assertRaises(FileExistsError):
                save_cpu_scale_report(output, report)

    def test_cli_real_asterion_results_and_cancel_exit_code(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as folder:
            report_path = Path(folder) / "report.json"
            args = [
                sys.executable, "-m", "drawtemp.quality.r24f_cli",
                "--mode", "both",
                "--sizes", "32", "--zooms", "96", "--samples", "2",
                "--seeds", "2", "--command-limit", "5",
                "--report", str(report_path),
            ]
            first = subprocess.run(args, cwd=root, capture_output=True,
                                   text=True, timeout=90)
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["massive_battle_lab"]["status"], "completed")
            self.assertEqual(len(report["renderer_cpu"]["cases"]), 1)
            self.assertFalse(report["release_certified"])
            second = subprocess.run(args, cwd=root, capture_output=True,
                                    text=True, timeout=90)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(json.loads(report_path.read_text()), report)
            cancel = subprocess.run([
                sys.executable, "-m", "drawtemp.quality.r24f_cli",
                "--mode", "battle", "--seeds", "3", "--command-limit", "5",
                "--cancel-after", "1",
            ], cwd=root, capture_output=True, text=True, timeout=90)
            self.assertEqual(cancel.returncode, 3, cancel.stderr + cancel.stdout)


if __name__ == "__main__":
    unittest.main()

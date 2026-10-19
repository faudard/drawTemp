"""R30.F: measured CPU timing, defensive evidence, asset budget and opt-in regression."""
from copy import deepcopy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr

from drawtemp.quality.r30_scale import (
    SCHEMA, OPS, ScaleError, _stats, collect_profile, compare_profiles,
    main, validate_report, _asset_inventory, _load_report,
)
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project


class ScaleProfilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = collect_profile(samples=3, warmups=0)

    def test_actual_authoring_projection_catalog_and_assets_are_measured(self):
        report = self.reference
        self.assertIs(validate_report(report), report)
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual([x["operation"] for x in report["metrics"]], list(OPS))
        self.assertEqual(report["workload"]["samples"], 3)
        self.assertTrue(all(row["samples"] == 3 for row in report["metrics"]))
        self.assertTrue(all(row["tail_exploratory"] for row in report["metrics"]))
        self.assertTrue(all(row["p50_ms"] <= row["p95_ms"] <=
                            row["p99_ms"] <= row["max_ms"]
                            for row in report["metrics"]))
        self.assertTrue(all(row["python_traced_peak_bytes"] >= 0
                            for row in report["metrics"]))
        self.assertEqual(report["gate"]["status"], "informational")
        self.assertFalse(report["gate"]["gpu_certified"])
        self.assertFalse(report["gate"]["player_certified"])

    def test_reject_fake_performance_claim_or_missing_operation(self):
        for update in (
            lambda r: r["gate"].update(gpu_certified=True),
            lambda r: r["gate"].update(status="certified"),
            lambda r: r["metrics"].pop(),
            lambda r: r["metrics"][0].update(samples=1000),
            lambda r: r["metrics"][0].update(p99_ms=-1),
            lambda r: r["metrics"][0].update(p95_ms=100_000),
            lambda r: r["metrics"][0].update(tail_exploratory=False),
        ):
            report = deepcopy(self.reference)
            update(report)
            with self.assertRaises(ScaleError):
                validate_report(report)

    def test_percentiles_are_measured_interpolation_not_fps(self):
        stats = _stats([1, 2, 3, 4, 100])
        self.assertEqual(stats["p50_ms"], 3)
        self.assertEqual(stats["max_ms"], 100)
        self.assertGreater(stats["p99_ms"], stats["p95_ms"])
        self.assertTrue(stats["tail_exploratory"])
        for values in ([], [-1], [float("inf")], [float("nan")]):
            with self.assertRaises(ScaleError):
                _stats(values)

    def test_no_implicit_disk_writes_for_canonical_project(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "game.json"
            content, project = reference_project()
            AuthoringSession.new(content, project).save_as(path)
            game = path.with_name("game.game.json")
            original = path.read_bytes(), game.read_bytes()
            report = collect_profile(content_path=path, samples=3, warmups=0)
            self.assertTrue(report["workload"]["disk_project"])
            self.assertEqual(report["asset_budget"]["bytes"], 0)
            self.assertTrue(report["asset_budget"]["bytes_verified"])
            self.assertEqual((path.read_bytes(), game.read_bytes()), original)
            self.assertEqual(report["workload"]["project_sha256"],
                             self.reference["workload"]["project_sha256"])

    def test_invalid_inputs_rejected_without_running_workload(self):
        for value in (True, 0, 1, 2, -1, 300, 3.5):
            with self.subTest(samples=value), self.assertRaises(ScaleError):
                collect_profile(samples=value, warmups=0)
        for value in (True, -1, 21, "2"):
            with self.subTest(warmups=value), self.assertRaises(ScaleError):
                collect_profile(samples=3, warmups=value)

    def test_compare_same_host_only_and_identical_workload(self):
        same = compare_profiles(self.reference, deepcopy(self.reference))
        self.assertFalse(same["blocked"])
        self.assertTrue(same["comparable_hosts"])
        self.assertEqual(len(same["changes"]), len(OPS))
        baseline = deepcopy(self.reference)
        changed = deepcopy(self.reference)
        # Simulated measurements ONLY in tests, not output as live evidence.
        changed["metrics"][0].update(
            p50_ms=10.0, p95_ms=20.0, p99_ms=30.0, max_ms=40.0)
        baseline["metrics"][0].update(
            p50_ms=1.0, p95_ms=2.0, p99_ms=3.0, max_ms=4.0)
        result = compare_profiles(baseline, changed,
                                  max_p95_growth_pct=20, min_delta_ms=1)
        self.assertTrue(result["blocked"])
        self.assertTrue(result["changes"][0]["regressed"])
        self.assertFalse(compare_profiles(
            baseline, changed, max_p95_growth_pct=20,
            min_delta_ms=100)["blocked"])
        changed["environment"]["hostname"] = "another-runner"
        with self.assertRaisesRegex(ScaleError, "environment"):
            compare_profiles(baseline, changed)
        unsafe = compare_profiles(baseline, changed, allow_host_mismatch=True)
        self.assertFalse(unsafe["comparable_hosts"])
        changed["workload"]["project_sha256"] = "f" * 64
        with self.assertRaisesRegex(ScaleError, "workloads"):
            compare_profiles(baseline, changed, allow_host_mismatch=True)

    def test_reject_missing_fake_assets_and_binary_import(self):
        content, project = reference_project()
        document = project.to_dict()
        inventory = _asset_inventory(document, None)
        self.assertEqual(inventory["bytes"], 0)
        self.assertFalse(inventory["bytes_verified"])
        with self.assertRaises(ScaleError):
            _asset_inventory({"assets": {"schema": 1, "entries": [
                {"kind": "sound", "id": "x", "path": "../escape.wav"}
            ]}}, None)

    def test_explicit_cli_writes_one_report_only_and_does_not_overwrite(self):
        with TemporaryDirectory() as folder:
            target = Path(folder) / "cpu.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                status = main(["--samples", "3", "--warmups", "0",
                               "--output", str(target)])
            self.assertEqual(status, 0)
            observed = _load_report(target)
            self.assertEqual(observed["schema"], SCHEMA)
            first = target.read_bytes()
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                status = main(["--samples", "3", "--warmups", "0",
                               "--output", str(target)])
            self.assertEqual(status, 1)
            self.assertEqual(target.read_bytes(), first)
            self.assertFalse((Path(folder) / "cpu-2.json").exists())


if __name__ == "__main__":
    unittest.main()

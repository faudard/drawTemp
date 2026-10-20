"""R76.C contracts: empirical stats, R15 bundle identity and NO-GO status.

Test fixtures may stub measured child probes; these are not benchmark evidence.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from drawtemp.export.r15 import export_game
from drawtemp.export.templates import create_template
from drawtemp.quality.r76_bench import (
    BenchmarkError, _bundle_inventory, _measure_once, _revision, _series,
    collect, compare, inspect_external_gpu, main, validate_report,
)

REV = "a" * 40


class R76CBenchTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        project = create_template("jeanne", self.root / "authoring")
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        native = "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"
        (self.runtime / native).write_bytes(b"TEST FIXTURE, NOT A REAL PLAYER")
        self.bundle = self.root / "bundle"
        export_game(project / "game.json", self.runtime, self.bundle)
        self.inventory = _bundle_inventory(self.bundle)

    @staticmethod
    def _sample(_bundle, _content, *, timeout=30):
        return 15.0, {
            "assets": 5, "missions": 1,
            "python_peak_bytes": 2048, "process_peak_rss_bytes": None,
        }

    def _collect(self, *, corpus="r76-jeanne"):
        with patch("drawtemp.quality.r76_bench._measure_once",
                   side_effect=self._sample) as probe:
            report = collect(self.bundle, revision=REV, samples=5,
                             warmups=1, corpus=corpus)
            self.assertEqual(probe.call_count, 6)
            return report

    def test_measured_inventory_and_percentile_contracts(self):
        self.assertGreater(self.inventory["bundle_bytes"], 0)
        self.assertEqual(self.inventory["content_relative"], "game/game.json")
        report = self._collect()
        self.assertEqual(validate_report(report), report)
        self.assertEqual(report["bundle"]["manifest_sha256"],
                         sha256((self.bundle / "manifest.json").read_bytes()).hexdigest())
        self.assertEqual(report["measurements"]["project_load_process_ms"]["p95"], 15)
        self.assertEqual(report["measurements"]["project_load_process_ms"]["p99"], 15)
        self.assertTrue(report["measurements"]["project_load_process_ms"]["tail_exploratory"])
        self.assertIsNone(report["measurements"]["process_peak_rss_bytes"])
        self.assertIsNone(report["gate"]["gpu_memory_bytes"])
        self.assertFalse(report["gate"]["release_certified"])
        self.assertFalse(report["gate"]["native_player_verified"])

    def test_statistical_variance_and_bad_samples_are_rejected(self):
        result = _series([2, 4, 6, 8, 10])
        self.assertGreater(result["variance"], 0)
        self.assertEqual(result["p50"], 6)
        self.assertAlmostEqual(result["p95"], 9.6)
        self.assertAlmostEqual(result["p99"], 9.92)
        with self.assertRaises(BenchmarkError):
            _series([1, 2, 3])
        with self.assertRaises(BenchmarkError):
            _series([1, 2, 3, 4, float("nan")])

    def test_same_corpus_compare_and_guard_regression(self):
        original = self._collect()
        candidate = deepcopy(original)
        candidate["bundle"]["bundle_bytes"] -= 2
        candidate["bundle"]["game_bytes"] -= 2
        candidate["measurements"]["project_load_process_ms"] = _series(
            [21.0] * 5)
        comparison = compare(original, candidate, max_p95_growth_pct=15)
        self.assertEqual(comparison["bundle_delta_bytes"], -2)
        self.assertTrue(comparison["latency_regressed"])
        self.assertTrue(comparison["bundle_reduction_observed"])
        self.assertFalse(comparison["release_certified"])
        candidate["revision"] = "b" * 40
        with self.assertRaisesRegex(BenchmarkError, "Incomparable"):
            compare(original, candidate)

    def test_mismatched_corpus_content_and_host_block_comparison(self):
        original = self._collect()
        for key, value in [
            ("corpus", "different"),
            ("environment", {**original["environment"], "os": "Different OS"}),
            ("bundle", {**original["bundle"], "content_sha256": "0" * 64}),
            ("workload", {**original["workload"], "samples": 6}),
        ]:
            changed = deepcopy(original)
            changed[key] = value
            with self.assertRaises(BenchmarkError):
                compare(original, changed)

    def test_invalid_certification_claims_and_percentile_forgery_rejected(self):
        report = self._collect()
        report["gate"]["physical_gpu_observed"] = True
        with self.assertRaisesRegex(BenchmarkError, "manufacture"):
            validate_report(report)
        report = self._collect()
        report["measurements"]["project_load_process_ms"]["p99"] = -1.0
        with self.assertRaises(BenchmarkError):
            validate_report(report)

    def test_bundle_tampering_blocks_collection_before_process_launch(self):
        (self.bundle / "game" / "game.json").write_bytes(b"tampered")
        with patch("drawtemp.quality.r76_bench._measure_once") as timed:
            with self.assertRaises(Exception):
                collect(self.bundle, revision=REV, samples=5)
            timed.assert_not_called()

    def test_runtime_drift_during_sampling_rejected(self):
        original_measure = self._sample
        calls = []
        def mutate(bundle, content, *, timeout=30):
            calls.append(1)
            if len(calls) == 2:
                (self.bundle / "Player" /
                 ("DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer")).write_bytes(b"tampered")
            return original_measure(bundle, content, timeout=timeout)
        with patch("drawtemp.quality.r76_bench._measure_once",
                   side_effect=mutate):
            with self.assertRaises(Exception):
                collect(self.bundle, revision=REV, samples=5, warmups=0)

    def test_no_untrusted_revision_or_unverified_gpu_file(self):
        with self.assertRaises(BenchmarkError):
            _revision("unverified")
        bad = self.root / "gpu.json"
        bad.write_text(json.dumps({"schema": 1, "device": {
            "os": "Linux", "gpu": "GPU", "driver": "demo", "qt": "6.8.3",
            "backend": "software", "software": True, "resolution": [640, 480],
        }, "scenes": []}), encoding="utf-8")
        with self.assertRaises(ValueError):
            inspect_external_gpu(bad)

    def test_one_real_python_subprocess_sample_is_not_a_native_player_test(self):
        elapsed, sample = _measure_once(
            self.bundle, self.inventory["content_relative"])
        self.assertGreater(elapsed, 0)
        self.assertGreater(sample["python_peak_bytes"], 0)
        self.assertGreater(sample["missions"], 0)
        self.assertGreaterEqual(sample["assets"], 0)

    def test_cli_output_is_create_only_and_not_a_release_certificate(self):
        result_path = self.root / "report.json"
        with patch("drawtemp.quality.r76_bench._measure_once",
                   side_effect=self._sample):
            self.assertEqual(main(["collect", "--bundle", str(self.bundle),
                                   "--revision", REV, "--samples", "5",
                                   "--warmups", "0", "--output", str(result_path)]), 0)
            self.assertEqual(main(["collect", "--bundle", str(self.bundle),
                                   "--revision", REV, "--samples", "5",
                                   "--warmups", "0", "--output", str(result_path)]), 1)
        data = json.loads(result_path.read_text())
        self.assertEqual(data["revision"], REV)
        self.assertFalse(data["gate"]["release_certified"])


if __name__ == "__main__":
    unittest.main()

"""R23.B acceptance: no invented endurance, human sign-off or accessibility."""
from __future__ import annotations

from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from drawtemp.quality.r23b import (
    accessibility_settings_probe, aggregate_ci, capture_ci_evidence,
    summarize_human_reports, verify_soak, write_json,
)
from sporebound.game_session import digest
from sporebound.playtest_telemetry import PlaytestRecorder

REV = "b" * 40


def case(seed):
    return {
        "seed": seed, "commands": 8, "checkpoint_sequence": 2,
        "final_digest": "a" * 64, "campaign_digest": "c" * 64,
        "max_checkpoint_bytes": 2048,
    }


def synthetic_soak():
    """Only a contract fixture; CI also runs a *real* R8.13 soak per platform."""
    cases = [case(1)]
    return {
        "version": 1, "gate": "R8.13", "verified": True,
        "iterations": 1, "commands_per_iteration": 8,
        "elapsed_seconds": 4.3,
        "operation_seconds": {"p50": 0.1, "p95": 0.2, "p99": 0.3, "max": 0.4},
        "python_peak_tracemalloc_bytes": 100000,
        "cases": cases, "report_digest": digest(cases),
    }


def evidence(platform):
    return {
        "schema": 1, "kind": "drawtemp-r23b-ci",
        "revision": REV, "platform": platform, "python": "3.12.0",
        "mode": "headless-ci-smoke",
        "endurance": synthetic_soak(),
        "accessibility_settings": accessibility_settings_probe(),
        "hardware_gpu": "not-asserted", "human_playtest": "not-asserted",
        "hours_long_soak": "not-asserted",
    }


class R23BAcceptanceTests(unittest.TestCase):
    def test_settings_probe_validates_persistence_rebind_and_rejects_bad_values(self):
        result = accessibility_settings_probe()
        self.assertTrue(result["persisted"])
        self.assertEqual(result["scale_percent"], 150)
        self.assertEqual(result["remapped_execute"], "<F1>")
        self.assertEqual(result["gui_keyboard_traversal"], "not-asserted")

    def test_soak_rejects_forged_flags_truncated_cases_and_bad_percentiles(self):
        clean = synthetic_soak()
        self.assertEqual(verify_soak(clean), clean)
        variants = [
            {"verified": False},
            {"cases": []},
            {"report_digest": "0" * 64},
            {"operation_seconds": {"p50": .5, "p95": .3, "p99": .2, "max": .1}},
        ]
        for change in variants:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    verify_soak(dict(clean, **change))
        changed = deepcopy(clean)
        changed["cases"][0]["commands"] = 9
        changed["report_digest"] = digest(changed["cases"])
        with self.assertRaises(ValueError):
            verify_soak(changed)

    def test_full_os_matrix_remains_no_go(self):
        reports = [evidence(osname) for osname in ("Linux", "Windows", "macOS")]
        result = aggregate_ci(reports, revision=REV)
        self.assertEqual(result["decision"], "NO-GO")
        self.assertFalse(result["release_certified"])
        self.assertEqual(set(result["matrix"]), {"Linux", "Windows", "macOS"})
        self.assertEqual(result["checks"]["R23.6"]["status"], "partial")
        self.assertEqual(result["checks"]["R23.7"]["status"], "partial")
        self.assertEqual(result["checks"]["R23.8"]["status"], "blocked")
        self.assertEqual(result["playtests"]["reports"], 0)

    def test_missing_duplicate_or_mismatched_sha_is_rejected(self):
        docs = [evidence(osname) for osname in ("Linux", "Windows", "macOS")]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            aggregate_ci(docs[:2], revision=REV)
        duplicate = deepcopy(docs)
        duplicate[-1]["platform"] = "Linux"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            aggregate_ci(duplicate, revision=REV)
        wrong = deepcopy(docs)
        wrong[1]["revision"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "Wrong revision"):
            aggregate_ci(wrong, revision=REV)

    def test_no_gpu_a11y_or_human_claim_can_be_injected(self):
        docs = [evidence(osname) for osname in ("Linux", "Windows", "macOS")]
        for field in ("hardware_gpu", "human_playtest", "hours_long_soak"):
            corrupted = deepcopy(docs)
            corrupted[0][field] = "certified"
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, "Unverified"):
                aggregate_ci(corrupted, revision=REV)
        corrupted = deepcopy(docs)
        corrupted[0]["accessibility_settings"]["screen_reader"] = "pass"
        with self.assertRaisesRegex(ValueError, "accessibility"):
            aggregate_ci(corrupted, revision=REV)

    def test_explicit_opt_in_human_file_is_counted_but_not_retest_certified(self):
        recorder = PlaytestRecorder()
        report = recorder.report()
        result = summarize_human_reports([report])
        self.assertEqual(result["reports"], 1)
        self.assertEqual(result["observed_sessions"], 0)
        self.assertEqual(result["retests"], "not-asserted")
        matrix = [evidence(osname) for osname in ("Linux", "Windows", "macOS")]
        assessment = aggregate_ci(matrix, revision=REV, human_reports=[report])
        self.assertEqual(assessment["checks"]["R23.8"]["status"], "partial")
        self.assertEqual(assessment["decision"], "NO-GO")
        with self.assertRaises(ValueError):
            summarize_human_reports([dict(report, opt_in=False)])

    def test_evidence_write_is_valid_json_without_hidden_claims(self):
        with TemporaryDirectory() as folder:
            target = Path(folder) / "subfolder" / "assessment.json"
            write_json(target, aggregate_ci(
                [evidence(osname) for osname in ("Linux", "Windows", "macOS")],
                revision=REV))
            self.assertTrue(target.read_text(encoding="utf-8").endswith("\n"))
            self.assertIn('"NO-GO"', target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

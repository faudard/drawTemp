"""R23.F accept/reject the candidate rehearsal; never auto-release."""
from __future__ import annotations

from copy import deepcopy
import unittest

from drawtemp.quality.r23f import (
    CandidateError, JOURNEY_CHECKS, candidate_assessment, verify_journey,
)
from scripts.r23f_acceptance import run_journey

REV = "e" * 40
PLATFORMS = ("Linux", "Windows", "macOS")


def row(platform):
    return {
        "schema": 1, "kind": "drawtemp-r23f-authoring-player",
        "revision": REV, "platform": platform,
        "journey": "real-api-headless-acceptance",
        "manifest_sha256": "a" * 64,
        "checks": {k: "passed" for k in JOURNEY_CHECKS},
        "runtime": "synthetic-native-stub", "native_gui_qa": "not-asserted",
        "signed": False, "elapsed_seconds": 1.23,
    }


def dossier():
    return {
        "kind": "drawtemp-r23e-release-dossier",
        "revision": REV, "decision": "NO-GO", "certified": False,
        "r23d": "linked-same-sha",
        "rights_matrix": {osname: {} for osname in PLATFORMS},
    }


class CandidateAcceptanceTests(unittest.TestCase):
    def test_real_studio_api_export_relocated_player_save_resume(self):
        actual = run_journey(revision=REV, platform="Linux")
        self.assertEqual(verify_journey(
            actual, revision=REV, platform="Linux"), actual)
        self.assertEqual(actual["runtime"], "synthetic-native-stub")
        self.assertEqual(set(actual["checks"]), set(JOURNEY_CHECKS))
        self.assertEqual(set(actual["checks"].values()), {"passed"})

    def test_three_os_and_rights_still_no_go(self):
        report = candidate_assessment(
            revision=REV, journeys=[row(p) for p in PLATFORMS],
            r23e=dossier())
        self.assertEqual(report["candidate"], "5.5.0-rc0")
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["release_certified"])
        self.assertFalse(report["candidate_ready_for_publication"])
        self.assertFalse(report["tag_allowed"])
        self.assertEqual(report["upstream"]["R23.B"], "not-provided")
        self.assertEqual(report["gates"]["R23.10"]["status"], "blocked")
        self.assertEqual(report["gates"]["R23.12"]["status"], "blocked")
        self.assertEqual(len(report["gates"]), 12)

    def test_missing_os_repeated_os_or_different_revision_rejected(self):
        rows = [row(p) for p in PLATFORMS]
        with self.assertRaisesRegex(CandidateError, "Missing"):
            candidate_assessment(revision=REV, journeys=rows[:2],
                                 r23e=dossier())
        duplicate = deepcopy(rows)
        duplicate[2]["platform"] = "Windows"
        with self.assertRaisesRegex(CandidateError, "Duplicate"):
            candidate_assessment(revision=REV, journeys=duplicate,
                                 r23e=dossier())
        stale = deepcopy(rows)
        stale[2]["revision"] = "f" * 40
        with self.assertRaises(CandidateError):
            candidate_assessment(revision=REV, journeys=stale, r23e=dossier())
        with self.assertRaisesRegex(CandidateError, "stale"):
            candidate_assessment(revision=REV, journeys=rows,
                                 r23e=dict(dossier(), revision="b" * 40))

    def test_forged_full_native_coverage_is_rejected(self):
        for mutate in (
            {"runtime": "real-native-hardware"},
            {"native_gui_qa": "passed"},
            {"signed": True},
            {"journey": "full-ui-certification"},
            {"checks": {**row("Linux")["checks"], "tamper_rejected": "skipped"}},
            {"manifest_sha256": "not-a-sha"},
        ):
            sample = dict(row("Linux"), **mutate)
            with self.subTest(mutate=mutate), self.assertRaises(CandidateError):
                verify_journey(sample, revision=REV, platform="Linux")

    def test_explicit_same_sha_r23b_is_partial_not_release_signoff(self):
        b = {
            "kind": "drawtemp-r23b-assessment", "revision": REV,
            "decision": "NO-GO", "release_certified": False,
            "matrix": {p: {} for p in PLATFORMS},
        }
        report = candidate_assessment(
            revision=REV, journeys=[row(p) for p in PLATFORMS],
            r23e=dossier(), r23b=b)
        self.assertEqual(report["upstream"]["R23.B"], "linked-same-sha")
        self.assertEqual(report["gates"]["R23.6"]["status"], "partial")
        self.assertFalse(report["tag_allowed"])
        with self.assertRaises(CandidateError):
            candidate_assessment(revision=REV,
                                 journeys=[row(p) for p in PLATFORMS],
                                 r23e=dossier(),
                                 r23b=dict(b, revision="f" * 40))


if __name__ == "__main__":
    unittest.main()

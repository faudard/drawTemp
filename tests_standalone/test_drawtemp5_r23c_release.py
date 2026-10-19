"""R23.C release attestation is fail closed, even with three green native smokes."""
from __future__ import annotations

from copy import deepcopy
import unittest

from drawtemp.quality.r23c_release import aggregate_release, REQUIRED_CHECKS

REV = "d" * 40


def check(platform):
    return {
        "schema": 1, "kind": "drawtemp-r23c-clean-runner",
        "revision": REV, "platform": platform,
        "archive_sha256": "a" * 64,
        "runner": "github-hosted-ephemeral-offscreen",
        "native_installer": "not-asserted",
        "signing": "not-asserted",
        "checks": {key: "passed" for key in REQUIRED_CHECKS},
    }


class ReleaseDecisionTests(unittest.TestCase):
    def matrix(self):
        return [check(platform) for platform in ("Linux", "Windows", "macOS")]

    def test_three_clean_runners_are_partial_not_full_release(self):
        summary = aggregate_release(self.matrix(), revision=REV)
        self.assertEqual(summary["decision"], "NO-GO")
        self.assertFalse(summary["certified"])
        self.assertEqual(len(summary["checks"]), 12)
        self.assertEqual(summary["checks"]["R23.1"]["status"], "partial")
        self.assertEqual(summary["checks"]["R23.12"]["status"], "blocked")
        self.assertEqual(summary["checks"]["R23.10"]["status"], "blocked")

    def test_missing_duplicate_wrong_sha_and_forged_signatures_rejected(self):
        matrix = self.matrix()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            aggregate_release(matrix[:-1], revision=REV)
        bad = deepcopy(matrix)
        bad[0]["platform"] = bad[1]["platform"]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            aggregate_release(bad, revision=REV)
        bad = deepcopy(matrix)
        bad[0]["revision"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "mismatched"):
            aggregate_release(bad, revision=REV)
        bad = deepcopy(matrix)
        bad[0]["signing"] = "passed"
        with self.assertRaisesRegex(ValueError, "unsupported claim"):
            aggregate_release(bad, revision=REV)

    def test_failed_native_studio_or_tamper_fails_whole_matrix(self):
        for gate in REQUIRED_CHECKS:
            bad = self.matrix()
            bad[1]["checks"][gate] = "skipped"
            with self.subTest(gate=gate), self.assertRaisesRegex(
                    ValueError, "Missing actual clean runner"):
                aggregate_release(bad, revision=REV)

    def test_optional_upstream_requires_same_sha_and_no_go(self):
        a = {
            "kind": "drawtemp-r23-release-ledger",
            "revision": REV, "decision": "NO-GO", "certified": False,
            "native_matrix": {"Linux": {}, "Windows": {}, "macOS": {}},
        }
        b = {
            "kind": "drawtemp-r23b-assessment",
            "revision": REV, "decision": "NO-GO", "release_certified": False,
            "matrix": {"Linux": {}, "Windows": {}, "macOS": {}},
        }
        accepted = aggregate_release(self.matrix(), revision=REV, r23a=a, r23b=b)
        self.assertEqual(accepted["upstream"],
                         {"R23.A": "partial-evidence", "R23.B": "partial-evidence"})
        self.assertEqual(accepted["checks"]["R23.6"]["status"], "partial")
        self.assertEqual(accepted["checks"]["R23.4"]["status"], "partial")
        self.assertEqual(accepted["decision"], "NO-GO")
        broken = dict(b, revision="1" * 40)
        with self.assertRaisesRegex(ValueError, "R23.B ledger"):
            aggregate_release(self.matrix(), revision=REV, r23a=a, r23b=broken)


if __name__ == "__main__":
    unittest.main()

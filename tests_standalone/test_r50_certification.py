"""Tests for R50.A reporting only; never an R50 release authorization."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r50_certification import (
    FAMILIES, PLATFORMS, build_ledger, main, required_evidence,
)

REVISION = "a" * 40


class R50CertificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "records").mkdir()
        (self.root / "artifacts").mkdir()

    def add_record(self, *, name="one", requirement="R40",
                   scope="upstream_gate", platform="agnostic",
                   family="agnostic", outcome="passed", revision=REVISION):
        data = (name + "-proof").encode("utf-8")
        path = self.root / "artifacts" / (name + ".log")
        path.write_bytes(data)
        record = {
            "kind": "drawtemp-r50-evidence",
            "schema": 1,
            "revision": revision,
            "requirement": requirement,
            "scope": scope,
            "platform": platform,
            "family": family,
            "outcome": outcome,
            "artifact": "artifacts/" + name + ".log",
            "sha256": sha256(data).hexdigest(),
        }
        (self.root / "records" / (name + ".json")).write_text(
            json.dumps(record), encoding="utf-8")
        return record

    def test_missing_matrix_never_authorizes_release(self):
        report = build_ledger(REVISION, self.root)
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["tag_allowed"])
        self.assertFalse(report["release_certified"])
        self.assertEqual(report["reported_slots"], 0)
        self.assertEqual(report["expected_slots"], len(required_evidence()))
        self.assertEqual(len(report["missing"]), len(required_evidence()))
        self.assertEqual(report["requirements"]["R50.1"]["status"],
                         "generated-unapproved")
        self.assertEqual(report["requirements"]["R50.7"]["required"], 3)

    def test_matrix_requires_six_genres_and_three_os(self):
        matrix = set(required_evidence())
        self.assertEqual({row[3] for row in matrix if row[0] == "R50.3"},
                         set(FAMILIES))
        self.assertEqual({row[2] for row in matrix if row[0] == "R50.7"},
                         set(PLATFORMS))
        self.assertEqual({row[3] for row in matrix if row[0] == "R50.4"},
                         set(FAMILIES[:5]))
        self.assertEqual(len(matrix), len(required_evidence()))

    def test_checksum_is_verified_but_test_claim_is_not_certified(self):
        self.add_record()
        report = build_ledger(REVISION, self.root)
        self.assertEqual(report["invalid"], [])
        self.assertEqual(report["reported_slots"], 1)
        self.assertEqual(report["requirements"]["R40"]["status"],
                         "reported-unverified")
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["tag_allowed"])

    def test_tampered_and_stale_evidence_do_not_count(self):
        record = self.add_record(revision="b" * 40)
        report = build_ledger(REVISION, self.root)
        self.assertEqual(report["reported_slots"], 0)
        self.assertIn("different commit", report["invalid"][0]["reason"])
        record["revision"] = REVISION
        (self.root / "records" / "one.json").write_text(
            json.dumps(record), encoding="utf-8")
        (self.root / "artifacts" / "one.log").write_bytes(b"tampered")
        report = build_ledger(REVISION, self.root)
        self.assertEqual(report["reported_slots"], 0)
        self.assertIn("checksum mismatch", report["invalid"][0]["reason"])

    def test_path_traversal_and_unknown_scope_fail_closed(self):
        record = self.add_record()
        record["artifact"] = "artifacts/../../secrets.log"
        (self.root / "records" / "one.json").write_text(
            json.dumps(record), encoding="utf-8")
        self.assertIn("safe path",
                      build_ledger(REVISION, self.root)["invalid"][0]["reason"])
        record["artifact"] = "artifacts/one.log"
        record["scope"] = "gpu_physical_faked"
        (self.root / "records" / "one.json").write_text(
            json.dumps(record), encoding="utf-8")
        self.assertIn("Unsupported requirement",
                      build_ledger(REVISION, self.root)["invalid"][0]["reason"])

    def test_duplicate_claims_and_json_keys_are_rejected(self):
        record = self.add_record()
        self.add_record(name="two")
        report = build_ledger(REVISION, self.root)
        self.assertEqual(report["reported_slots"], 1)
        self.assertEqual(len(report["invalid"]), 1)
        self.assertIn("Duplicate evidence", report["invalid"][0]["reason"])
        (self.root / "records" / "one.json").write_text(
            json.dumps(record)[:-1] + ', "schema": 1}', encoding="utf-8")
        report = build_ledger(REVISION, self.root)
        self.assertTrue(any("Duplicate JSON object key" in e["reason"]
                            for e in report["invalid"]))

    def test_failed_check_is_visible_and_not_promoted(self):
        self.add_record(outcome="failed")
        report = build_ledger(REVISION, self.root)
        self.assertEqual(report["requirements"]["R40"]["status"],
                         "reported-failure")
        self.assertTrue(any("failed checks" in item
                            for item in report["blockers"]))
        self.assertFalse(report["tag_allowed"])

    def test_symlinked_artifact_is_rejected(self):
        self.add_record()
        path = self.root / "artifacts" / "one.log"
        other = self.root / "other.log"
        other.write_bytes(path.read_bytes())
        path.unlink()
        try:
            path.symlink_to(other)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        report = build_ledger(REVISION, self.root)
        self.assertEqual(report["reported_slots"], 0)
        self.assertIn("linked evidence", report["invalid"][0]["reason"])

    def test_invalid_revision_cannot_produce_report(self):
        for revision in ("master", "A" * 40, "a" * 39):
            with self.subTest(revision=revision):
                with self.assertRaisesRegex(ValueError, "exact 40"):
                    build_ledger(revision, self.root)

    def test_cli_writes_explicit_no_go_and_enforce_fails(self):
        output = self.root / "output" / "r50.json"
        argv = ["--revision", REVISION, "--evidence-dir", str(self.root),
                "--output", str(output)]
        self.assertEqual(main(argv), 0)
        self.assertEqual(json.loads(output.read_text())["decision"], "NO-GO")
        self.assertEqual(main(argv + ["--enforce"]), 1)


if __name__ == "__main__":
    unittest.main()

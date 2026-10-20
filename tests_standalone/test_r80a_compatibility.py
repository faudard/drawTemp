"""R80.A evidence inventory regressions; never interpret as 12.0 release tests."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.quality.r80_compatibility import CHECKS, build_audit, main, probe_public_sdk

REVISION = "a" * 40


class CompatibilityAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "records").mkdir()
        (self.root / "artifacts").mkdir()

    def add_record(self, name="proof", check="sdk_public_api", outcome="passed"):
        content = (name + "-test-output").encode("utf-8")
        (self.root / "artifacts" / (name + ".log")).write_bytes(content)
        record = {"kind": "drawtemp-r80a-compatibility-proof", "schema": 1,
                  "revision": REVISION, "check": check, "outcome": outcome,
                  "artifact": "artifacts/" + name + ".log",
                  "sha256": sha256(content).hexdigest()}
        self.write_record(name, record)
        return record

    def write_record(self, name, record):
        (self.root / "records" / (name + ".json")).write_text(
            json.dumps(record), encoding="utf-8")

    def audit(self):
        return build_audit(REVISION, self.root)

    def test_no_evidence_is_explicit_no_go_and_sdk_probe_is_real(self):
        report = self.audit()
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["release_certified"])
        self.assertFalse(report["tag_allowed"])
        self.assertEqual(report["missing"], list(CHECKS))
        self.assertEqual(report["sdk"]["api_version"], [1, 0])
        self.assertEqual(report["sdk"]["api_status"], "provisional")
        self.assertTrue(report["sdk"]["compatible_requests_enforced"])
        self.assertEqual(len(report["sdk"]["contract_sha256"]), 64)

    def test_valid_checksum_is_only_a_self_report(self):
        self.add_record()
        report = self.audit()
        self.assertEqual([x["check"] for x in report["reported_checks"]], ["sdk_public_api"])
        self.assertNotIn("sdk_public_api", report["missing"])
        self.assertEqual(report["decision"], "NO-GO")

    def test_tampered_and_stale_records_are_not_counted(self):
        record = self.add_record()
        record["revision"] = "b" * 40
        self.write_record("proof", record)
        self.assertIn("Stale", self.audit()["invalid"][0]["reason"])
        record["revision"] = REVISION
        self.write_record("proof", record)
        (self.root / "artifacts" / "proof.log").write_bytes(b"tampered")
        self.assertIn("checksum mismatch", self.audit()["invalid"][0]["reason"])

    def test_duplicate_checks_and_duplicate_json_keys_are_rejected(self):
        record = self.add_record()
        self.add_record(name="second")
        report = self.audit()
        self.assertEqual(len(report["reported_checks"]), 1)
        self.assertIn("Duplicate compatibility check", report["invalid"][0]["reason"])
        self.write_record("second", {**record, "check": "asset_rights_and_hashes"})
        path = self.root / "records" / "proof.json"
        path.write_text(json.dumps(record)[:-1] + ', "check": "sdk_public_api"}', encoding="utf-8")
        self.assertTrue(any("Duplicate JSON key" in row["reason"] for row in self.audit()["invalid"]))

    def test_path_traversal_and_unknown_check_fail_closed(self):
        record = self.add_record()
        record["artifact"] = "artifacts/../../secret.txt"
        self.write_record("proof", record)
        self.assertIn("safe artifacts/", self.audit()["invalid"][0]["reason"])
        record["artifact"] = "artifacts/proof.log"
        record["check"] = "pretend_gpu_certification"
        self.write_record("proof", record)
        self.assertIn("Unknown compatibility check", self.audit()["invalid"][0]["reason"])

    def test_symlinked_asset_and_parent_are_rejected(self):
        self.add_record()
        source = self.root / "artifacts" / "proof.log"
        target = self.root / "elsewhere.log"
        target.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unsupported")
        self.assertIn("linked", self.audit()["invalid"][0]["reason"].lower())
        source.unlink()
        source.write_bytes(target.read_bytes())
        (self.root / "artifacts").rename(self.root / "real-artifacts")
        (self.root / "artifacts").symlink_to(self.root / "real-artifacts", target_is_directory=True)
        self.assertTrue(self.audit()["invalid"])

    def test_failed_proof_is_visible(self):
        self.add_record(outcome="failed")
        self.assertEqual(self.audit()["failed"], ["sdk_public_api"])
        self.assertTrue(any("failed" in x for x in self.audit()["blockers"]))

    def test_invalid_revision_and_outcomes_are_rejected(self):
        for rev in ("master", "A" * 40, "a" * 39, True):
            with self.subTest(revision=rev), self.assertRaises(ValueError):
                build_audit(rev, self.root)
        row = self.add_record()
        row["outcome"] = True
        self.write_record("proof", row)
        self.assertIn("outcome", self.audit()["invalid"][0]["reason"])

    def test_only_approved_record_structure_is_allowed(self):
        row = self.add_record()
        row["critical"] = False
        self.write_record("proof", row)
        self.assertIn("Unknown or missing", self.audit()["invalid"][0]["reason"])

    def test_probe_failure_never_turns_green(self):
        with patch("drawtemp.quality.r80_compatibility.probe_public_sdk", side_effect=ValueError("broken")):
            report = self.audit()
        self.assertIsNone(report["sdk"])
        self.assertEqual(report["sdk_error"], "broken")
        self.assertEqual(report["decision"], "NO-GO")

    def test_complete_self_report_still_cannot_certify(self):
        for i, check in enumerate(CHECKS):
            self.add_record(name="proof" + str(i), check=check)
        report = self.audit()
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["invalid"], [])
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["tag_allowed"])

    def test_cli_json_and_enforcement(self):
        output = self.root / "out" / "audit.json"
        args = ["--revision", REVISION, "--evidence-dir", str(self.root),
                "--output", str(output)]
        self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["decision"], "NO-GO")
        self.assertEqual(main(args + ["--enforce"]), 1)


if __name__ == "__main__":
    unittest.main()

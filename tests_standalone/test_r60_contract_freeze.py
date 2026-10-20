"""R60.A regression tests: hashes, versioning, replay parity and fail-closed release."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.quality.r60_freeze import FreezeError, build_report, main
from drawtemp.sdk.reference import reference_project

REV = "a" * 40
BASELINE = Path(__file__).resolve().parents[1] / "docs/drawtemp5/reference-baseline.json"


class R60FreezeTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        golden = self.root / "docs/drawtemp5/reference-baseline.json"
        golden.parent.mkdir(parents=True)
        golden.write_bytes(BASELINE.read_bytes())
        self.golden = json.loads(golden.read_text(encoding="utf-8"))
        self.content_path = self.root / "corpus/jeanne.json"
        self.project_path = self.root / "corpus/jeanne.game.json"
        self.content_path.parent.mkdir()
        content, project = reference_project()
        self.content = content.to_dict()
        self.project = project.to_dict()
        self.save_pair(self.content, self.project)

    def save_pair(self, content, project):
        self.content_path.write_text(json.dumps(content), encoding="utf-8")
        self.project_path.write_text(json.dumps(project), encoding="utf-8")
        self.manifest = {
            "schema": 1,
            "pairs": [{
                "id": "jeanne-r0", "content": "corpus/jeanne.json",
                "project": "corpus/jeanne.game.json",
                "content_sha256": sha256(self.content_path.read_bytes()).hexdigest(),
                "project_sha256": sha256(self.project_path.read_bytes()).hexdigest(),
            }],
        }
        (self.root / "fixtures.json").write_text(
            json.dumps(self.manifest), encoding="utf-8")

    def audit(self, manifest="fixtures.json", runner=None):
        return build_report(self.root, REV, manifest=manifest,
                            parity_runner=runner or (lambda: self.golden))

    def test_canonical_pair_is_read_only_and_not_release_authorization(self):
        before = (self.content_path.read_bytes(), self.project_path.read_bytes())
        report = self.audit()
        self.assertTrue(report["sdk_contract_frozen"])
        self.assertTrue(report["regressions_passed"])
        self.assertEqual(report["r0_reference"]["status"], "passed")
        self.assertEqual(report["historical_pairs"][0]["source_versions"], [1, 1])
        self.assertEqual(report["historical_pairs"][0]["proposed_changes"], [])
        self.assertEqual(report["release_decision"], "NO-GO")
        self.assertFalse(report["tag_allowed"])
        self.assertFalse(report["release_certified"])
        self.assertEqual(
            (self.content_path.read_bytes(), self.project_path.read_bytes()), before)

    def test_v0_envelope_only_is_an_explicit_preview(self):
        content = dict(self.content)
        project = dict(self.project)
        content.pop("version")
        project.pop("version")
        self.save_pair(content, project)
        before = self.content_path.read_bytes()
        report = self.audit()
        item = report["historical_pairs"][0]
        self.assertEqual(item["source_versions"], [0, 0])
        self.assertEqual(item["canonical_versions"], [1, 1])
        self.assertEqual(len(item["proposed_changes"]), 2)
        self.assertEqual(item["strategy"], "read_only_v0_envelope_preview")
        self.assertEqual(before, self.content_path.read_bytes())

    def test_unknown_schema_cannot_be_silently_upgraded(self):
        content = dict(self.content, version=10)
        self.save_pair(content, self.project)
        report = self.audit()
        self.assertFalse(report["regressions_passed"])
        self.assertEqual(report["historical_pairs"], [])
        self.assertIn("historical_corpus:", report["preflight_errors"][0])
        self.assertEqual(report["release_decision"], "NO-GO")

    def test_hash_pinning_rejects_mutated_source(self):
        self.content_path.write_bytes(self.content_path.read_bytes() + b" ")
        report = self.audit()
        self.assertFalse(report["regressions_passed"])
        self.assertIn("Historical fixture changed", report["preflight_errors"][0])

    def test_path_traversal_and_symlink_fail_closed(self):
        row = self.manifest["pairs"][0]
        row["content"] = "../elsewhere.json"
        row["project"] = "../elsewhere.game.json"
        (self.root / "fixtures.json").write_text(
            json.dumps(self.manifest), encoding="utf-8")
        self.assertIn("repository-relative", self.audit()["preflight_errors"][0])
        row["content"] = "corpus/jeanne.json"
        row["project"] = "corpus/jeanne.game.json"
        (self.root / "fixtures.json").write_text(
            json.dumps(self.manifest), encoding="utf-8")
        elsewhere = self.root / "new.json"
        elsewhere.write_bytes(self.content_path.read_bytes())
        self.content_path.unlink()
        try:
            self.content_path.symlink_to(elsewhere)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported")
        self.assertIn("Linked", self.audit()["preflight_errors"][0])

    def test_duplicate_fixtures_and_json_keys_rejected(self):
        self.manifest["pairs"].append(dict(self.manifest["pairs"][0]))
        (self.root / "fixtures.json").write_text(
            json.dumps(self.manifest), encoding="utf-8")
        self.assertIn("duplicate fixture", self.audit()["preflight_errors"][0])
        (self.root / "fixtures.json").write_text(
            '{"schema":1,"schema":1,"pairs":[]}', encoding="utf-8")
        self.assertIn("Duplicate JSON key", self.audit()["preflight_errors"][0])

    def test_baseline_drift_detected(self):
        drift = dict(self.golden)
        drift["result"] = "defeat"
        report = self.audit(runner=lambda: drift)
        self.assertFalse(report["regressions_passed"])
        self.assertEqual(report["r0_reference"]["status"], "blocked")
        self.assertTrue(any("reference" in x.lower()
                            for x in report["preflight_errors"]))

    def test_sdk_contract_drift_detected(self):
        with patch("drawtemp.sdk.capabilities", return_value={
            "api_version": [2, 0], "status": "stable",
            "content_schema": 10, "project_schema": 1,
            "game_session_schema": 1,
        }):
            report = self.audit()
        self.assertFalse(report["sdk_contract_frozen"])
        self.assertFalse(report["regressions_passed"])
        self.assertTrue(any("content_schema" in err
                            for err in report["contract_errors"]))
        self.assertEqual(report["release_decision"], "NO-GO")

    def test_no_corpus_never_claims_historical_coverage(self):
        report = self.audit(manifest=None)
        self.assertEqual(report["historical_pairs"], [])
        self.assertTrue(any("fixture pairs" in b for b in report["blockers"]))
        self.assertFalse(report["release_certified"])

    def test_invalid_revision_rejected_and_cli_fails_closed(self):
        for revision in ("master", "A" * 40, "b" * 39):
            with self.subTest(revision=revision):
                with self.assertRaises(FreezeError):
                    self.audit_with_revision(revision)
        self.assertEqual(main(["--root", str(self.root), "--revision", "master"]), 2)

    def audit_with_revision(self, revision):
        return build_report(self.root, revision, parity_runner=lambda: self.golden)


if __name__ == "__main__":
    unittest.main()

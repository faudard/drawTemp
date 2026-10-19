"""R17.13: negative release gates, provenance, SHA and reproducible notes."""
from hashlib import sha256
from importlib.resources import files
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r14 import evidence_report
from drawtemp.quality.r17_release_evidence import (
    EvidenceError, RELEASE_GATES, REQUIRED_CHECKS,
    build_dossier, index_artifacts, inspect_checks, inspect_cross,
    inspect_r14, main, release_notes,
)


REV = "a" * 40


def github_runs(revision=REV, *, status="completed", conclusion="success"):
    runs = [
        {"id": n, "name": name, "head_sha": revision, "status": status,
         "conclusion": conclusion, "run_attempt": 1,
         "started_at": "2026-10-19T10:00:00Z",
         "html_url": "https://github.com/example/actions/" + str(n)}
        for n, name in enumerate(REQUIRED_CHECKS, 1)
    ]
    return {"total_count": len(runs), "check_runs": runs}


def cross_preview():
    return {
        "player": {"replay_verified": True, "trigger_count": 1},
        "preflight": {"passed": True},
        "content_sha256": "b" * 64,
        "project_sha256": "c" * 64,
        "asset_sha256": "d" * 64,
        "r17_12_certified": False,
    }


class R1713EvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def json(self, name, contents):
        path = self.root / name
        path.write_text(json.dumps(contents), encoding="utf-8")
        return path

    def test_default_dossier_blocked_with_every_p0_gate(self):
        report = build_dossier(revision=REV, generated_utc="2026-10-19T00:00:00Z")
        self.assertFalse(report["release_ready"])
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(set(report["gates"]), set(RELEASE_GATES))
        self.assertTrue(all(row["status"] != "pass" for row in report["gates"].values()))
        self.assertIn("release", release_notes(report).lower())
        self.assertGreaterEqual(len(report["blocking_reasons"]), 13)

    def test_artifact_uses_measured_sha_and_refuses_symlink(self):
        source = self.root / "evidence.png"
        data = b"measured bytes, not a screenshot"
        source.write_bytes(data)
        items = index_artifacts({"capture": source})
        self.assertEqual(items["capture"]["sha256"], sha256(data).hexdigest())
        self.assertEqual(items["capture"]["size_bytes"], len(data))
        source.write_bytes(data + b"changed")
        self.assertNotEqual(index_artifacts({"capture": source})["capture"]["sha256"],
                            items["capture"]["sha256"])
        with self.assertRaises(EvidenceError):
            index_artifacts({"unsafe/name": source})
        with self.assertRaises(EvidenceError):
            index_artifacts({"missing": self.root / "404"})
        symlink = self.root / "alias"
        try:
            symlink.symlink_to(source)
        except OSError:
            pass
        else:
            with self.assertRaises(EvidenceError):
                index_artifacts({"alias": symlink})

    def test_git_checks_must_be_for_exact_commit_and_complete(self):
        green = github_runs()
        good = inspect_checks(green, REV)
        self.assertTrue(good["all_required_success"])
        self.assertFalse(good["missing"])
        with self.assertRaises(EvidenceError):
            inspect_checks(green, "e" * 40)
        partial = dict(green)
        partial["total_count"] += 1
        self.assertFalse(inspect_checks(partial, REV)["complete"])
        blocked = github_runs()
        blocked["check_runs"][0]["status"] = "queued"
        blocked["check_runs"][0]["conclusion"] = None
        self.assertFalse(inspect_checks(blocked, REV)["all_required_success"])
        blocked["check_runs"].pop()
        blocked["total_count"] = len(blocked["check_runs"])
        self.assertEqual(len(inspect_checks(blocked, REV)["missing"]), 1)

    def test_stale_successful_attempt_never_overrides_queued_rerun(self):
        x = github_runs()
        again = dict(x["check_runs"][0])
        again.update(id=9999, run_attempt=2, status="in_progress",
                     conclusion=None, started_at="2026-10-19T11:00:00Z")
        x["check_runs"].append(again)
        x["total_count"] += 1
        self.assertFalse(inspect_checks(x, REV)["all_required_success"])

    def test_even_green_ci_never_authenticates_release(self):
        checks = self.json("checks.json", github_runs())
        report = build_dossier(revision=REV, checks=checks)
        self.assertTrue(report["components"]["checks"]["all_required_success"])
        self.assertEqual(report["gates"]["R17.8"]["status"], "partial")
        self.assertFalse(report["independent_release_approval"])
        self.assertFalse(report["release_ready"])

    def test_cross_report_is_only_partial_even_when_all_claims_are_true(self):
        checks = self.json("checks.json", github_runs())
        cross = self.json("r1712.json", cross_preview())
        report = build_dossier(revision=REV, checks=checks, cross=cross)
        self.assertTrue(report["components"]["cross_workshop"]["contract_valid"])
        self.assertEqual(report["gates"]["R17.12"]["status"], "partial")
        self.assertFalse(report["release_ready"])
        forged = cross_preview()
        forged["r17_12_certified"] = True
        self.assertFalse(inspect_cross(forged)["contract_valid"])

    def test_r14_valid_contract_cannot_attest_hardware_identity(self):
        report = evidence_report({})
        r14 = self.json("r14.json", report)
        result = build_dossier(revision=REV, r14=r14)
        self.assertTrue(result["components"]["r14"]["contract_valid"])
        self.assertFalse(result["components"]["r14"]["hardware_independently_attested"])
        self.assertEqual(result["gates"]["R17.9"]["status"], "blocked")
        wrong = evidence_report({})
        wrong["p0_certified"] = True
        self.assertFalse(inspect_r14(wrong)["contract_valid"])

    def test_unverified_asset_rights_remain_blocked(self):
        content = Path(str(files("sporebound").joinpath("content/jeanne.json")))
        result = build_dossier(revision=REV, content_path=content)
        self.assertFalse(result["components"]["asset_rights"]["independent_legal_review"])
        self.assertEqual(result["gates"]["R17.6"]["status"], "blocked")
        self.assertFalse(result["release_ready"])

    def test_uploaded_review_json_does_not_become_approval(self):
        fake = self.json("review.json", {"approved": True, "signed": True})
        result = build_dossier(revision=REV, review=fake)
        self.assertTrue(result["components"]["external_review"]["recorded"])
        self.assertFalse(result["components"]["external_review"]["authenticated"])
        self.assertFalse(result["release_ready"])

    def test_cli_outputs_draft_and_require_ready_fails_closed(self):
        check = self.json("checks.json", github_runs())
        notes = self.root / "RELEASE_NOTES.md"
        report = self.root / "evidence.json"
        args = ["--revision", REV, "--checks-json", str(check),
                "--artifact", "log=" + str(check),
                "--report", str(report), "--notes", str(notes)]
        self.assertEqual(main(args), 0)
        produced = json.loads(report.read_text(encoding="utf-8"))
        self.assertFalse(produced["release_ready"])
        self.assertIn("BLOCKED", notes.read_text(encoding="utf-8"))
        self.assertIn(sha256(check.read_bytes()).hexdigest(),
                      notes.read_text(encoding="utf-8"))
        self.assertEqual(main(args + ["--require-ready"]), 1)

    def test_invalid_revision_is_rejected(self):
        for sha in ("", "fake", "A"*40, "a"*39, "g"*40):
            with self.subTest(sha=sha), self.assertRaises(EvidenceError):
                build_dossier(revision=sha)


if __name__ == "__main__":
    unittest.main()

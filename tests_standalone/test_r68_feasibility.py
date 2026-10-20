"""Headless R68.A contract: never infer product support from local probes."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r68_feasibility import (
    EvidenceError, ENVIRONMENTS, KIND, REQUIREMENTS, build_report, load_evidence,
)

REVISION = "a" * 40


class R68FeasibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        files = {
            "pyproject.toml": """[project.optional-dependencies]\nqt6 = ["PySide6==6.8.3; python_version == '3.12'"]\n""",
            "drawtemp/player/qt_app.py": "def f():\n    from PySide6.QtCore import QTimer\n",
            "drawtemp/player/action_app.py": "from PySide6.QtQml import QQmlApplicationEngine\n",
            "drawtemp/export/publication_matrix.py": "PC_TARGETS = ('linux-x86_64',)\n",
        }
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def evidence(self, target="android", missing=(), revision=REVISION):
        dossier = self.root / "proofs" / target
        dossier.mkdir(parents=True, exist_ok=True)
        checks = {}
        for name in REQUIREMENTS[target]:
            if name in missing:
                continue
            artifact = dossier / (name + ".json")
            artifact.write_text(json.dumps({"check": name}), encoding="utf-8")
            checks[name] = {"status": "passed", "artifact": artifact.name,
                            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}
        manifest = dossier / "evidence.json"
        manifest.write_text(json.dumps({
            "schema": 1, "kind": KIND, "revision": revision,
            "target": target, "environment": ENVIRONMENTS[target],
            "checks": checks,
        }), encoding="utf-8")
        return manifest

    def test_no_external_proof_is_no_go(self):
        report = build_report(self.root, revision=REVISION)
        self.assertEqual(set(report["platforms"]), {"android", "ios", "web"})
        self.assertFalse(report["release_certified"])
        self.assertEqual(report["missing_sources"], [])
        self.assertIn("PySide6.QtCore", report["source_inventory"]["drawtemp/player/qt_app.py"]["qt_imports"])
        for row in report["platforms"].values():
            self.assertEqual(row["decision"], "NO-GO")
            self.assertFalse(row["player_supported"])

    def test_complete_evidence_is_only_manual_review(self):
        evidence = self.evidence("android")
        report = build_report(self.root, revision=REVISION, evidence=[evidence])
        android = report["platforms"]["android"]
        self.assertEqual(android["decision"], "MANUAL_REVIEW_REQUIRED")
        self.assertTrue(android["evidence_complete_for_manual_review"])
        self.assertFalse(android["release_certified"])
        self.assertFalse(android["player_supported"])
        self.assertEqual(report["platforms"]["ios"]["decision"], "NO-GO")

    def test_incomplete_evidence_is_no_go(self):
        report = build_report(self.root, revision=REVISION,
                              evidence=[self.evidence("web", missing=("storage",))])
        self.assertEqual(report["platforms"]["web"]["missing_checks"], ["storage"])
        self.assertEqual(report["platforms"]["web"]["decision"], "NO-GO")

    def test_tampering_artifact_is_rejected(self):
        path = self.evidence("ios")
        (path.parent / "launch.json").write_text("tampered", encoding="utf-8")
        with self.assertRaises(EvidenceError):
            load_evidence(path, REVISION)

    def test_revision_mismatch_is_rejected(self):
        with self.assertRaises(EvidenceError):
            load_evidence(self.evidence(), "b" * 40)

    def test_artifact_traversal_is_rejected(self):
        path = self.evidence()
        data = json.loads(path.read_text(encoding="utf-8"))
        data["checks"]["launch"]["artifact"] = "../launch.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(EvidenceError):
            load_evidence(path, REVISION)

    def test_duplicate_json_keys_are_rejected(self):
        path = self.evidence()
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('"schema": 1,', '"schema": 1, "schema": 1,'),
                        encoding="utf-8")
        with self.assertRaises(EvidenceError):
            load_evidence(path, REVISION)

    def test_duplicate_platform_dossiers_are_rejected(self):
        path = self.evidence()
        with self.assertRaises(EvidenceError):
            build_report(self.root, revision=REVISION, evidence=[path, path])

    def test_evidence_without_revision_is_rejected(self):
        with self.assertRaises(EvidenceError):
            build_report(self.root, evidence=[self.evidence()])


if __name__ == "__main__":
    unittest.main()

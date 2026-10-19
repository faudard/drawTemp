"""R20.D: source staging, immutable legacy data and fail-closed release rules.

The expensive nine-battle E2E is run separately by the dedicated CI job.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from drawtemp.export.r15 import ExportError, preflight
from scripts.certify_r20d_jeanne import CASES, certify, require
from scripts.prepare_r20d_jeanne_demo import (
    CONTENT_NAME, PROJECT_NAME, PROJECT, SOURCE, prepare, stage_pair
)
from sporebound.game_project import GameProject
from sporebound.model import Content


class JeanneR20DReleaseTests(unittest.TestCase):
    def test_route_matrix_joins_both_prologues_and_three_endings(self):
        self.assertEqual(set(CASES), {
            "archives_secours", "otages_poursuite",
            "foi_secours", "archives_poursuite"})
        self.assertEqual({x["prologue"] for x in CASES.values()},
                         {"secourir", "poursuivre"})
        self.assertEqual({x["dilemma"] for x in CASES.values()},
                         {"prendre_archives", "liberer_otages"})
        self.assertEqual({x["companion"] for x in CASES.values()},
                         {"engager_etienne", "engager_agnes"})
        self.assertEqual({x["conclusion"] for x in CASES.values()},
                         {"preuves", "temoins", "libre_arbitre"})

    def test_staging_creates_unchanged_canonical_content_pair(self):
        source_sha = SOURCE.read_bytes()
        project_sha = PROJECT.read_bytes()
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "source"
            target.mkdir()
            report = stage_pair(target)
            self.assertTrue(report["preflight_passed"])
            self.assertFalse(report["native_runtime_included"])
            self.assertFalse(report["release_certified"])
            self.assertEqual((target / CONTENT_NAME).read_bytes(), source_sha)
            self.assertEqual((target / PROJECT_NAME).read_bytes(), project_sha)
            self.assertTrue(preflight(target / CONTENT_NAME)["passed"])
            content = Content.load(target / CONTENT_NAME)
            project = GameProject.load(target / PROJECT_NAME, content)
            self.assertEqual(project.title, GameProject.load(PROJECT, content).title)
            self.assertEqual(report["project_sha256"], __import__("hashlib").sha256(
                project_sha).hexdigest())
            with self.assertRaises(ExportError):
                stage_pair(target)
        # Neither an external manifest nor a "demo" stage rewrites original
        # gameplay content or the two separately-versioned Jeanne projects.
        self.assertEqual(SOURCE.read_bytes(), source_sha)
        self.assertEqual(PROJECT.read_bytes(), project_sha)

    def test_developer_bundle_has_explicit_warning_and_no_release_claim(self):
        with TemporaryDirectory() as tmp:
            destination = Path(tmp) / "developer-demo"
            result = prepare(destination)
            self.assertEqual(result["kind"], "r20d-developer-pair")
            self.assertFalse(result["release_certified"])
            self.assertTrue((destination / CONTENT_NAME).is_file())
            report = json.loads((destination / "r20d-preflight.json").read_text())
            self.assertFalse(report["native_runtime_included"])
            self.assertFalse(report["release_certified"])
            with self.assertRaises(ExportError):
                prepare(destination)

    def test_native_candidate_requires_real_r14_evidence_not_file_placeholder(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            output = directory / "publish"
            with self.assertRaises(ExportError):
                prepare(output, native_runtime=directory / "fake-runtime")
            self.assertFalse(output.exists())
            with self.assertRaises(ExportError):
                prepare(output, r14_report=directory / "fake-r14.json")
            self.assertFalse(output.exists())
            # Even if the caller supplies an alleged R14 report, the source
            # pair has no auto-granted license rights: preflight blocks native.
            if not (SOURCE.parent / "asset-licenses.json").exists():
                with self.assertRaises(ExportError):
                    prepare(output, native_runtime=directory,
                            r14_report=directory / "fake-r14.json")
                self.assertFalse(output.exists())

    def test_unknown_route_cannot_be_counted_as_certified(self):
        with self.assertRaises(ValueError):
            certify(names=["nonexistent"])
        with patch("scripts.certify_r20d_jeanne.run_case",
                   side_effect=AssertionError("blocked checkpoint")):
            report = certify(names=["archives_secours"])
        self.assertFalse(report["passed"])
        self.assertFalse(report["release_certified"])
        self.assertIn("blocked checkpoint", report["cases"][0]["error"])
        self.assertTrue(report["not_evidenced"])

    def test_check_requires_actual_victory(self):
        with self.assertRaises(AssertionError):
            require(False, "Tactical result not victorious")


if __name__ == "__main__":
    unittest.main()

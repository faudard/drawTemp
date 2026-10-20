"""R49.B1: no-JSON Creator status, honest genre gates and path safety."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.studio.genre_workflow import preview_genre_project, create_genre_project
from drawtemp.studio.r49_creator_ux import creator_preflight_text
from drawtemp.export.r15 import ExportError
from drawtemp.export.templates import create_template


class CreatorPresentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_available_genres_show_a_clear_no_json_preflight(self):
        for genre in ("srpg", "narrative"):
            with self.subTest(genre=genre):
                report = preview_genre_project(genre, self.root / genre)
                self.assertTrue(report["passed"])
                rendered = creator_preflight_text(report)
                self.assertIn("Création disponible", rendered)
                self.assertIn("Content + GameProject", rendered)
                self.assertIn("aucune écriture", rendered)
                self.assertNotIn('{"', rendered)
                self.assertFalse((self.root / genre).exists())

    def test_blocked_modes_do_not_falsely_claim_availability(self):
        for genre in ("action_adventure", "classic_rpg", "hybrid"):
            with self.subTest(genre=genre):
                report = preview_genre_project(genre, self.root / genre)
                self.assertFalse(report["passed"])
                rendered = creator_preflight_text(report)
                self.assertIn("Création bloquée", rendered)
                self.assertIn("Points à corriger", rendered)
                for issue in report["errors"]:
                    self.assertIn(issue, rendered)
                self.assertNotIn("Création disponible", rendered)

    def test_invalid_presenter_input_is_refused(self):
        valid = preview_genre_project("srpg", self.root / "new")
        for changes in (
            {"status": "certified"},
            {"passed": "yes"},
            {"passed": True, "errors": ["bad"]},
            {"status": "blocked-dependency", "passed": True},
            {"passed": False, "errors": []},
            {"proposed_profile": {}},
            {"label": None},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                creator_preflight_text({**valid, **changes})
        with self.assertRaises(TypeError):
            creator_preflight_text(None)

    def test_broken_symlink_destination_is_never_overwritten(self):
        target = self.root / "reserved"
        missing = self.root / "not-present"
        try:
            target.symlink_to(missing, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Symlinks not permitted on this runner: " + str(exc))
        self.assertTrue(target.is_symlink())
        self.assertFalse(target.exists())
        report = preview_genre_project("srpg", target)
        self.assertFalse(report["passed"])
        self.assertIn("existe", " ".join(report["errors"]))
        with self.assertRaises(ValueError):
            create_genre_project("srpg", target)
        with self.assertRaises(ExportError):
            create_template("tactical", target)
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.readlink(), missing)
        self.assertFalse(missing.exists())


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "Qt unavailable")
class CreatorWizardPresentationQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_preflight_is_readable_and_unavailable_genre_cannot_be_created(self):
        from drawtemp.studio.genre_wizard_qt import GenreProjectWizard
        with TemporaryDirectory() as folder:
            wizard = GenreProjectWizard()
            self.addCleanup(wizard.deleteLater)
            wizard.destination.setText(str(Path(folder) / "game"))
            wizard.genre.setCurrentIndex(wizard.genre.findData("classic_rpg"))
            self.assertFalse(wizard.create_button.isEnabled())
            self.assertIn("Création bloquée", wizard.report.toPlainText())
            self.assertNotIn('"status":', wizard.report.toPlainText())
            wizard.genre.setCurrentIndex(wizard.genre.findData("srpg"))
            self.assertTrue(wizard.create_button.isEnabled())
            self.assertIn("Création disponible", wizard.report.toPlainText())
            wizard.close()


if __name__ == "__main__":
    unittest.main()

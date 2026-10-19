"""R28.A: genre-aware Creator checks, including optional Qt offscreen."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.r15 import preflight
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.genre_workflow import (
    GENRES, create_genre_project, genre_preset, preview_genre_project,
)


class GenreWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_five_distinct_genres_and_explicit_capabilities(self):
        self.assertEqual([g.key for g in GENRES],
                         ["srpg", "action_adventure", "classic_rpg",
                          "narrative", "hybrid"])
        self.assertEqual(genre_preset("srpg").combat, "TACTICAL_CT")
        with self.assertRaises(ValueError):
            genre_preset("unknown")

    def test_preview_is_read_only_and_blocks_unimplemented_modes(self):
        for key in ("action_adventure", "classic_rpg", "hybrid"):
            target = self.root / key
            report = preview_genre_project(key, target)
            self.assertFalse(report["passed"])
            self.assertIn("blocked", report["status"])
            self.assertIn("NOT_WRITTEN", report["proposed_profile"]["persistence"])
            with self.assertRaises(ValueError):
                create_genre_project(key, target)
            self.assertFalse(target.exists())

    def test_tactical_and_narrative_use_canonical_creator(self):
        for key in ("srpg", "narrative"):
            with self.subTest(genre=key):
                target = self.root / key
                result = preview_genre_project(key, target)
                self.assertTrue(result["passed"], result)
                self.assertFalse(target.exists())
                folder = create_genre_project(key, target)
                self.assertEqual(folder, target)
                self.assertTrue(preflight(folder / "game.json")["passed"])
                self.assertTrue((folder / "game.game.json").is_file())
                # No second profile file, shadow engine, or rewritten schema.
                self.assertEqual(
                    sorted(path.name for path in folder.iterdir()),
                    ["game.game.json", "game.json"])
                self.assertEqual(AuthoringSession.open(folder / "game.json").revision, 0)

    def test_never_overwrite_existing_project_or_empty_destination(self):
        path = self.root / "existing"
        path.mkdir()
        sentinel = path / "keep.txt"
        sentinel.write_text("unchanged", encoding="utf-8")
        for dest in (path, "", "  "):
            self.assertFalse(preview_genre_project("srpg", dest)["passed"])
            with self.assertRaises(ValueError):
                create_genre_project("srpg", dest)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")
        self.assertEqual(sorted(x.name for x in path.iterdir()), ["keep.txt"])


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "Qt unavailable")
class GenreWizardQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_wizard_only_enables_creation_for_supported_modes(self):
        from drawtemp.studio.genre_wizard_qt import GenreProjectWizard
        with TemporaryDirectory() as folder:
            dialog = GenreProjectWizard()
            dialog.destination.setText(str(Path(folder) / "new_game"))
            self.assertEqual(dialog.genre.count(), 5)
            for key in ("action_adventure", "classic_rpg", "hybrid"):
                dialog.genre.setCurrentIndex(dialog.genre.findData(key))
                self.assertFalse(dialog.create_button.isEnabled())
            for key in ("srpg", "narrative"):
                dialog.genre.setCurrentIndex(dialog.genre.findData(key))
                self.assertTrue(dialog.create_button.isEnabled())
            dialog.genre.setCurrentIndex(dialog.genre.findData("srpg"))
            dialog.create()
            self.assertTrue(dialog.created_content_path.is_file())
            self.assertTrue(preflight(dialog.created_content_path)["passed"])
            dialog.close()


if __name__ == "__main__":
    unittest.main()

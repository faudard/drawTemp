"""Regression tests for the compact Studio new-project flow."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.sdk.authoring import AuthoringSession


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 unavailable")
class SimpleProjectDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.simple_project_dialog import SimpleProjectDialog
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = QSettings(
            str(self.root / "studio.ini"), QSettings.Format.IniFormat)
        self.dialog = SimpleProjectDialog(
            parent_directory=self.root, settings=self.settings)
        self.addCleanup(self.dialog.close)

    def test_three_fields_default_title_and_derived_location(self):
        dialog = self.dialog
        self.assertEqual(dialog.folder_name.text(), "Project1")
        self.assertEqual(dialog.game_title.text(), "Project1")
        self.assertEqual(dialog.location.text(), str(self.root / "Project1"))
        dialog.folder_name.setText("MonJeu")
        self.assertEqual(dialog.game_title.text(), "MonJeu")
        self.assertEqual(dialog.location.text(), str(self.root / "MonJeu"))
        dialog.game_title.setText("La grande aventure")
        dialog.game_title.textEdited.emit("La grande aventure")
        dialog.folder_name.setText("AutreDossier")
        self.assertEqual(dialog.game_title.text(), "La grande aventure")
        self.assertEqual(dialog.location.text(), str(self.root / "AutreDossier"))

    def test_directory_browse_and_manual_path_are_consistent(self):
        games = self.root / "games"
        games.mkdir()
        self.dialog.folder_name.setText("RPG1")
        with patch(
            "drawtemp.studio.simple_project_dialog.QFileDialog.getExistingDirectory",
            return_value=str(games),
        ):
            self.dialog.browse_directory()
        self.assertEqual(self.dialog.location.text(), str(games / "RPG1"))
        self.dialog.location.setText(str(games / "RPG2"))
        self.dialog._location_edited()
        self.assertEqual(self.dialog.folder_name.text(), "RPG2")
        self.assertEqual(self.dialog.location.text(), str(games / "RPG2"))

    def test_invalid_names_and_existing_destinations_cannot_overwrite(self):
        from PySide6.QtWidgets import QDialogButtonBox
        ok = self.dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        for bad in ("", "../oops", "CON", "a:b", "trailing.", "bad\\name"):
            with self.subTest(name=bad):
                self.dialog.folder_name.setText(bad)
                self.assertFalse(ok.isEnabled())
        self.dialog.folder_name.setText("AlreadyThere")
        target = self.root / "AlreadyThere"
        target.mkdir()
        (target / "keep.txt").write_text("protected", encoding="utf-8")
        self.dialog._update_validation()
        self.assertFalse(ok.isEnabled())
        self.dialog.create()
        self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"),
                         "protected")
        self.assertIsNone(self.dialog.created_content_path)

    def test_cancel_has_no_side_effects(self):
        from PySide6.QtWidgets import QDialog
        self.dialog.reject()
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Rejected)
        self.assertFalse((self.root / "Project1").exists())

    def test_create_generates_valid_project_and_remembers_parent(self):
        from PySide6.QtWidgets import QDialog
        self.dialog.folder_name.setText("Cendreval")
        self.dialog.game_title.setText("Les Cendres")
        with patch("drawtemp.studio.simple_project_dialog.QMessageBox.warning") as warning:
            self.dialog.create()
        warning.assert_not_called()
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)
        path = self.root / "Cendreval" / "game.json"
        self.assertEqual(self.dialog.created_content_path, path)
        self.assertTrue(path.is_file())
        self.assertTrue(path.with_name("game.game.json").is_file())
        snapshot = AuthoringSession.open(path).snapshot()
        self.assertEqual(snapshot.project["title"], "Les Cendres")
        self.assertEqual(self.settings.value("projects/parent_directory"),
                         str(self.root))
        self.assertFalse(snapshot.dirty)

    def test_next_unused_name_is_suggested(self):
        from drawtemp.studio.simple_project_dialog import SimpleProjectDialog
        (self.root / "Project1").mkdir()
        second = SimpleProjectDialog(
            parent_directory=self.root, settings=self.settings)
        try:
            self.assertEqual(second.folder_name.text(), "Project2")
        finally:
            second.close()


if __name__ == "__main__":
    unittest.main()

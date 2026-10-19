"""R22.1 Project Wizard: non-destructive preview, canonical creation and Qt handoff."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.export.r15 import ExportError, preflight
from drawtemp.export.templates import TEMPLATES, create_template
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.project_wizard import (
    ProjectSpec, create_project, project_preview,
)


class ProjectWizardTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_preview_never_creates_directories(self):
        destination = self.root / "nested" / "new-project"
        report = project_preview(ProjectSpec("blank", destination, title="Premier jeu"))
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["content"], str(destination / "game.json"))
        self.assertFalse(destination.parent.exists())

    def test_all_templates_create_configured_canonical_projects(self):
        for kind in TEMPLATES:
            with self.subTest(template=kind):
                spec = ProjectSpec(kind, self.root / kind, title="Mon propre RPG",
                                   subtitle="Prologue", language="en",
                                   save_slots=5, fullscreen=True)
                path = create_project(spec)
                snapshot = AuthoringSession.open(path).snapshot().to_dict()
                manifest = snapshot["project"]
                self.assertEqual(manifest["title"], "Mon propre RPG")
                self.assertEqual(manifest["subtitle"], "Prologue")
                self.assertEqual(manifest["options"]["language"], "en")
                self.assertIs(manifest["options"]["fullscreen"], True)
                self.assertEqual(manifest["save_slots"], 5)
                self.assertGreater(len(snapshot["content"]["missions"]), 0)
                self.assertTrue(preflight(path)["passed"])

    def test_bad_spec_fails_before_disk_write(self):
        invalid = (
            {"title": " "},
            {"title": "X" * 121},
            {"subtitle": "X" * 241},
            {"language": "de"},
            {"save_slots": 0},
            {"save_slots": True},
            {"fullscreen": "yes"},
            {"template": "missing"},
            {"destination": ""},
        )
        for n, changes in enumerate(invalid):
            with self.subTest(changes=changes):
                spec = ProjectSpec("blank", self.root / f"invalid-{n}", **changes) if (
                    "template" not in changes and "destination" not in changes
                ) else ProjectSpec(changes.get("template", "blank"),
                                   changes.get("destination", self.root / f"invalid-{n}"))
                report = project_preview(spec)
                self.assertFalse(report["passed"])
                with self.assertRaises(ExportError):
                    create_project(spec)
                self.assertFalse((self.root / f"invalid-{n}").exists())

    def test_existing_directory_is_never_replaced(self):
        target = self.root / "created"
        target.mkdir()
        sentinel = target / "retain.txt"
        sentinel.write_text("important", encoding="utf-8")
        spec = ProjectSpec("tactical", target)
        self.assertFalse(project_preview(spec)["passed"])
        with self.assertRaises(ExportError):
            create_project(spec)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "important")

    def test_r15_template_factory_also_rejects_invalid_options(self):
        with self.assertRaises(ExportError):
            create_template("blank", self.root / "invalid", title=" ")
        self.assertFalse((self.root / "invalid").exists())


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class ProjectWizardQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_preview_create_and_accept(self):
        from PySide6.QtWidgets import QDialog
        from drawtemp.studio.r15_creator import CreatorDialog
        with TemporaryDirectory() as folder:
            path = Path(folder) / "demo"
            dialog = CreatorDialog()
            dialog.template.setCurrentText("blank")
            dialog.destination.setText(str(path))
            dialog.game_title.setText("Aventure test")
            self.assertTrue(dialog.preview()["passed"])
            self.assertFalse(path.exists())
            with patch("drawtemp.studio.r15_creator.QMessageBox.information"):
                dialog.execute()
            self.assertEqual(dialog.result(), QDialog.Accepted)
            self.assertEqual(dialog.created_content_path, path / "game.json")
            self.assertEqual(AuthoringSession.open(dialog.created_content_path).
                             snapshot().project["title"], "Aventure test")
            dialog.close()

    def test_shell_loads_new_session_and_resets_workspace(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as folder:
            content = create_project(ProjectSpec("blank", Path(folder) / "demo"))
            settings = QSettings(str(Path(folder) / "settings.ini"), QSettings.IniFormat)
            shell = StudioWindow(settings=settings)
            shell.navigate("maps")
            old_session = shell.session
            self.assertIn("new", shell.commands)
            self.assertTrue(shell._load_document(content))
            self.assertIsNot(shell.session, old_session)
            self.assertEqual(shell.content_path, content)
            self.assertEqual(set(shell.pages), {"project"})
            shell.close()


if __name__ == "__main__":
    unittest.main()

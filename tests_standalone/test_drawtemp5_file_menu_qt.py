"""Native Studio File menu and non-destructive Close Project GUI regressions."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class FileMenuQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow

        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        settings = QSettings(str(self.root / "studio.ini"), QSettings.IniFormat)
        self.window = StudioWindow(settings=settings)

    def tearDown(self):
        with patch.object(self.window, "_confirm_leave", return_value=True):
            self.window.close()

    def test_file_menu_has_four_native_mnemonic_actions_and_save_icon(self):
        from PySide6.QtGui import QKeySequence

        file_menu = self.window.menuBar().actions()[0].menu()
        self.assertEqual(file_menu.title(), "&File")
        self.assertEqual(file_menu.objectName(), "studio-file-menu")
        self.assertEqual(file_menu.actions(), [
            self.window.commands[key]
            for key in ("new_project", "open", "close", "save")
        ])
        self.assertEqual(
            [action.text() for action in file_menu.actions()],
            ["&New Project…", "&Open Project…", "&Close Project", "&Save Project"])
        for key, shortcut in (("new_project", "Ctrl+N"),
                              ("open", "Ctrl+O"), ("save", "Ctrl+S")):
            self.assertEqual(self.window.commands[key].shortcut(),
                             QKeySequence(shortcut))
        self.assertFalse(self.window.commands["save"].icon().isNull())
        self.assertTrue(self.window.commands["save"].isIconVisibleInMenu())
        self.assertFalse(self.window.commands["close"].isEnabled())

    def test_close_project_cancels_then_returns_to_home_without_deleting_files(self):
        from drawtemp.studio.project_wizard import ProjectSpec, create_project

        content = create_project(ProjectSpec("blank", self.root / "example"))
        with patch.object(self.window, "_confirm_leave", return_value=True):
            self.assertTrue(self.window.open_path(content))
        self.assertEqual(self.window.content_path, content)
        self.assertTrue(self.window.commands["close"].isEnabled())
        with patch.object(self.window, "_confirm_leave", return_value=False):
            self.assertFalse(self.window.close_project())
        self.assertEqual(self.window.content_path, content)

        self.window.commands["close"].trigger()
        self.assertIsNone(self.window.content_path)
        self.assertEqual(set(self.window.pages), {"project"})
        self.assertEqual(self.window._active_workspace, "project")
        self.assertFalse(self.window.commands["close"].isEnabled())
        self.assertIsNone(self.window._onboarding_key)
        self.assertTrue(content.is_file())
        self.assertIn(str(content), self.window.settings.value("files/recent", []))
        self.assertFalse(self.window.close_project())

    def test_advanced_project_commands_and_game_actions_remain_available(self):
        titles = [action.menu().title() for action in
                  self.window.menuBar().actions() if action.menu() is not None]
        self.assertEqual(
            titles, ["&File", "&Edit", "&Display", "&Workspaces", "&Tools", "&Game"])
        self.assertIn("&Game", titles)
        tools = next(action.menu() for action in self.window.menuBar().actions()
                     if action.menu() and action.menu().title() == "&Tools")
        advanced = next(action.menu() for action in tools.actions()
                        if action.menu() and action.menu().title() == "Advanced Project")
        self.assertIn(self.window.commands["new"], advanced.actions())
        self.assertIn(self.window.commands["new_template"], advanced.actions())
        self.assertIn(self.window.commands["save_as"], advanced.actions())
        self.assertEqual(self.window.recent_menu.title(), "Recent Projects")
        display = next(action.menu() for action in self.window.menuBar().actions()
                       if action.menu() and action.menu().title() == "&Display")
        self.assertIn("Theme", [action.menu().title() for action in
                                display.actions() if action.menu()])
        self.assertIsNotNone(self.window.recent_menu)


if __name__ == "__main__":
    unittest.main()

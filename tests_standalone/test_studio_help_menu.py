"""Qt regression tests for Help > Docs / Tutorial / About.

The tutorial catalog is a visible placeholder only, with no runnable lessons.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class HelpMenuQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_tutorial_dialog_lists_examples_but_cannot_start_lessons(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QDialog
        from drawtemp.studio.help_dialogs import (
            TUTORIAL_CATALOG, TutorialSelectorDialog,
        )
        dialog = TutorialSelectorDialog()
        try:
            self.assertEqual(dialog.windowTitle(), "Tutorial Selector")
            self.assertEqual(dialog.tutorial_list.count(), len(TUTORIAL_CATALOG))
            self.assertGreaterEqual(dialog.tutorial_list.count(), 18)
            self.assertEqual(dialog.tutorial_list.currentRow(), 0)
            self.assertEqual(
                dialog.tutorial_list.item(0).data(Qt.ItemDataRole.UserRole),
                "first_steps",
            )
            self.assertIn("carte", dialog.tutorial_list.item(1).text())
            self.assertFalse(dialog.start_button.isEnabled())
            from PySide6.QtWidgets import QLabel, QPushButton
            notice = dialog.findChild(QLabel, "tutorial-selector-notice")
            self.assertIsNotNone(notice)
            self.assertIn("à venir", notice.text())
            close = dialog.findChild(QPushButton, "tutorial-selector-close")
            self.assertIsNotNone(close)
            close.click()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        finally:
            dialog.close()

    def test_docs_action_uses_real_docs_url_and_handles_browser_failure(self):
        from drawtemp.studio.help_dialogs import DOCS_URL, open_docs
        self.assertEqual(
            DOCS_URL, "https://github.com/faudard/drawTemp/tree/master/docs")
        with patch("drawtemp.studio.help_dialogs.QDesktopServices.openUrl",
                   return_value=True) as browser:
            self.assertTrue(open_docs())
            self.assertEqual(browser.call_args.args[0].toString(), DOCS_URL)
        with patch("drawtemp.studio.help_dialogs.QDesktopServices.openUrl",
                   return_value=False), patch(
                "drawtemp.studio.help_dialogs.QMessageBox.warning") as warning:
            self.assertFalse(open_docs())
            warning.assert_called_once()

    def test_about_uses_real_distribution_version(self):
        from drawtemp.studio.help_dialogs import show_about
        with patch("drawtemp.studio.help_dialogs.metadata.version",
                   return_value="2.0.0a1"), patch(
                "drawtemp.studio.help_dialogs.QMessageBox.about") as about:
            show_about()
            self.assertIn("2.0.0a1", about.call_args.args[2])

    def test_studio_menu_order_and_actions(self):
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QMenu
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as folder:
            window = StudioWindow(
                settings=QSettings(
                    str(Path(folder) / "settings.ini"), QSettings.Format.IniFormat))
            try:
                menu = window.menuBar().findChild(QMenu, "studio-help-menu")
                self.assertIsNotNone(menu)
                self.assertEqual(
                    [a.text() for a in menu.actions() if not a.isSeparator()],
                    ["Docs", "Tutorial…", "About"],
                )
                for key in ("help_docs", "help_tutorial", "help_about"):
                    self.assertIn(key, window.commands)
                original_revision = window.session.revision
                original_content = window.content_path
                with patch("drawtemp.studio.help_dialogs.TutorialSelectorDialog"
                           ) as dialog:
                    window.commands["help_tutorial"].trigger()
                    dialog.assert_called_once_with(window)
                    dialog.return_value.exec.assert_called_once()
                with patch("drawtemp.studio.help_dialogs.QDesktopServices.openUrl",
                           return_value=True) as browser:
                    window.commands["help_docs"].trigger()
                    browser.assert_called_once()
                with patch("drawtemp.studio.help_dialogs.QMessageBox.about"
                           ) as about:
                    window.commands["help_about"].trigger()
                    about.assert_called_once()
                self.assertEqual(window.session.revision, original_revision)
                self.assertEqual(window.content_path, original_content)
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()

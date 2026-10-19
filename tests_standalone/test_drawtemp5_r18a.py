"""R18.A Studio UX: headless navigation policy and optional offscreen shell gate."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r18_navigation import (
    EN, LABELS, WORKSPACES, recent_projects, workspace_host,
)


class NavigationPolicyTests(unittest.TestCase):
    def test_all_roadmap_destinations_have_stable_labels(self):
        self.assertEqual(len(WORKSPACES), 10)
        self.assertEqual(set(WORKSPACES), set(LABELS))
        self.assertEqual(set(WORKSPACES), set(EN))
        self.assertEqual(workspace_host("construction"), "maps")
        for destination in WORKSPACES:
            self.assertEqual(workspace_host(destination),
                             "maps" if destination == "construction" else destination)
        with self.assertRaises(ValueError):
            workspace_host("unknown")

    def test_recent_projects_normalize_deduplicate_and_bound(self):
        with TemporaryDirectory() as folder:
            first = Path(folder) / "one.json"
            second = Path(folder) / "two.json"
            result = recent_projects(
                [first, first, str(second), "", None] + [
                    Path(folder) / (str(n) + ".json") for n in range(12)],
                selected=second)
            self.assertEqual(result[:2], [str(second.resolve()), str(first.resolve())])
            self.assertEqual(len(result), 8)
            self.assertEqual(recent_projects(str(first)), [str(first.resolve())])

    def test_navigation_policy_has_no_gui_dependency(self):
        import subprocess
        import sys
        script = (
            "import sys; from drawtemp.studio.r18_navigation import WORKSPACES; "
            "assert len(WORKSPACES)==10; "
            "assert 'PySide6' not in sys.modules; "
            "assert 'tkinter' not in sys.modules"
        )
        subprocess.run([sys.executable, "-c", script], check=True)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class QtStudioNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def window(self, folder):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        settings = QSettings(str(Path(folder) / "studio.ini"), QSettings.IniFormat)
        session = AuthoringSession.new(*reference_project())
        return StudioWindow(session, settings=settings)

    def test_global_destinations_context_and_publication(self):
        from PySide6.QtWidgets import QComboBox, QWidget
        with TemporaryDirectory() as folder:
            window = self.window(folder)
            try:
                self.assertEqual(set(window.commands).intersection(
                    {"new", "open", "save_as", "playtest", "export",
                     "preferences"}), {"new", "open", "save_as",
                                      "playtest", "export", "preferences"})
                # Stand in for the GPU-dependent map editor: the R18 navigation
                # test checks shared ownership and mode switching, not rendering.
                fake_map = QWidget()
                fake_map.mode = QComboBox()
                fake_map.mode.addItems(["Carte", "Construction"])
                window.workspace_tabs.addWidget(fake_map)
                window.pages["maps"] = fake_map
                window._models["maps"] = fake_map
                window.navigate("construction")
                self.assertIs(window.pages["construction"], fake_map)
                self.assertEqual(fake_map.mode.currentIndex(), 1)
                self.assertEqual(window._active_workspace, "construction")
                window.navigate("maps")
                self.assertEqual(fake_map.mode.currentIndex(), 0)
                self.assertIs(window.pages["maps"], window.pages["construction"])
                window.navigate("publication")
                self.assertIs(window.workspace_tabs.currentWidget(),
                              window.pages["publication"])
                self.assertTrue(window.commands["go_publication"].isChecked())
                window.layout_preset("analysis")
                self.assertEqual(window.settings.value("window/preset"), "analysis")
            finally:
                window.close()

    def test_open_recent_and_failed_file_do_not_replace_live_session(self):
        with TemporaryDirectory() as folder:
            window = self.window(folder)
            try:
                path = Path(folder) / "game.json"
                source = AuthoringSession.new(*reference_project())
                source.save_as(path)
                self.assertTrue(window.open_path(path))
                self.assertEqual(window.content_path, path)
                self.assertEqual(window.settings.value("files/recent")[0],
                                 str(path.resolve()))
                old = window.session
                with patch.object(window, "report_error") as report:
                    self.assertFalse(window.open_path(Path(folder) / "missing.json"))
                    report.assert_called_once()
                self.assertIs(window.session, old)
                self.assertEqual(window.content_path, path)
                self.assertTrue(window.save_document())
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()

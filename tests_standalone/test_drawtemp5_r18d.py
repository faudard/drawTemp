"""R18.D: first-project tutorial, accessibility and Studio→Player E2E."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r18_onboarding import (
    STEP_IDS, completed_steps, journey_steps, next_step, normalize_completed,
    project_key,
)


class JourneyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.session = AuthoringSession.new(*reference_project())

    def test_no_fictional_completion_for_in_memory_reference(self):
        steps = journey_steps(
            self.session.snapshot(), ("map", "actor", "save", "playtest"))
        self.assertEqual([s.identifier for s in steps], list(STEP_IDS))
        self.assertTrue(all(not step.done for step in steps))
        self.assertEqual(next_step(steps).identifier, "project")
        self.assertFalse(steps[1].available)
        self.assertFalse(steps[2].available)

    def test_project_scoped_evidence_and_real_resource_blockers(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "game.json"
            steps = journey_steps(
                self.session.snapshot(), ["map", "save"], content_path=path)
            self.assertTrue(steps[0].done)
            self.assertTrue(steps[1].done)
            self.assertFalse(steps[2].done)
            self.assertTrue(steps[3].done)
            self.assertTrue(steps[4].available)
            self.assertEqual(next_step(steps).identifier, "actor")
            self.assertEqual(completed_steps(("playtest",), project_open=False),
                             frozenset())
            self.assertEqual(project_key(path), project_key(path.resolve()))
            self.assertNotEqual(project_key(path), project_key(Path(folder) / "other.json"))
            self.assertEqual(normalize_completed(["save", "unknown", "save"]),
                             frozenset({"save"}))
            self.assertEqual(journey_steps(
                self.session.snapshot(), content_path=path, language="en"
            )[1].title, "Explore the Map workspace")

    def test_no_qt_import_on_headless_onboarding(self):
        script = (
            "import sys; from drawtemp.studio.r18_onboarding import journey_steps; "
            "assert 'PySide6' not in sys.modules; "
            "assert 'tkinter' not in sys.modules"
        )
        subprocess.run([sys.executable, "-c", script], check=True)

    def test_canonical_studio_pair_loads_in_real_player_and_resumes(self):
        from drawtemp.player.qt_app import build_controller
        with TemporaryDirectory() as folder:
            path = Path(folder) / "game.json"
            self.session.save_as(path)
            player = build_controller(content_path=path,
                                      save_dir=Path(folder) / "saves")
            self.assertEqual(player.state()["screen"], "title")
            active = player.new_game()
            self.assertNotEqual(active["screen"], "title")
            player.save(1)
            disk = (Path(folder) / "saves" / "slot_1.json").read_bytes()
            old_revision = player.state()["revision"]
            player.title()
            loaded = player.continue_game()
            self.assertEqual(loaded["revision"], old_revision)
            self.assertEqual((Path(folder) / "saves" / "slot_1.json").read_bytes(),
                             disk)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 unavailable")
class StudioGuideQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def window(self, folder):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        return StudioWindow(
            AuthoringSession.new(*reference_project()),
            settings=QSettings(str(Path(folder) / "studio.ini"),
                               QSettings.IniFormat))

    def _fake_map_and_actor(self, window):
        # Navigation proof without running an OpenGL renderer in this test.
        # The dedicated R18.B CI separately tests the real R5/R6 viewport.
        from PySide6.QtWidgets import QComboBox, QWidget
        map_widget = QWidget()
        map_widget.mode = QComboBox()
        map_widget.mode.addItems(["Carte", "Construction"])
        window.workspace_tabs.addWidget(map_widget)
        window.pages["maps"] = map_widget
        actor_widget = QWidget()
        window.workspace_tabs.addWidget(actor_widget)
        window.pages["actors"] = actor_widget

    def test_project_to_map_to_actor_save_playtest_and_persist(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "game.json"
            AuthoringSession.new(*reference_project()).save_as(path)
            window = self.window(folder)
            try:
                self.assertEqual(window.guide_list.count(), 5)
                self.assertTrue(window.guide_panel.isVisibleTo(window.pages["project"]))
                self.assertIn("0/5", window.guide_title.text())
                self.assertFalse(window._onboarding_done)
                self.assertTrue(window.open_path(path))
                self.assertIn("project", window._onboarding_done)
                self._fake_map_and_actor(window)
                window.navigate("maps")
                window.navigate("actors")
                self.assertEqual(window._onboarding_done,
                                 {"project", "map", "actor"})
                self.assertTrue(window.save_document())
                self.assertIn("save", window._onboarding_done)
                self.assertFalse("playtest" in window._onboarding_done)
                with patch("drawtemp.studio.qt_shell.QProcess.startDetached",
                           return_value=(True, 117)):
                    self.assertTrue(window.playtest())
                self.assertEqual(window._onboarding_done, set(STEP_IDS))
                self.assertFalse(window.guide_next_button.isEnabled())
                window.hide_guide()
                self.assertTrue(window._onboarding_hidden)
                window.open_guide()
                self.assertFalse(window._onboarding_hidden)
                self.assertEqual(window._active_workspace, "project")
                self.assertTrue(window.guide_next_button.hasFocus())
            finally:
                window.close()
            reopened = self.window(folder)
            try:
                self.assertTrue(reopened.open_path(path))
                self.assertEqual(reopened._onboarding_done, set(STEP_IDS))
                self.assertEqual(reopened.guide_list.count(), 5)
            finally:
                reopened.close()

    def test_failed_open_or_launch_is_not_a_completed_milestone(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "game.json"
            AuthoringSession.new(*reference_project()).save_as(path)
            window = self.window(folder)
            try:
                with patch.object(window, "report_error"):
                    self.assertFalse(window.open_path(Path(folder) / "missing.json"))
                self.assertFalse(window._onboarding_done)
                self.assertIsNone(window.content_path)
                self.assertTrue(window.open_path(path))
                with patch("drawtemp.studio.qt_shell.QProcess.startDetached",
                           return_value=(False, 0)), patch.object(window, "report_error"):
                    self.assertFalse(window.playtest())
                self.assertNotIn("playtest", window._onboarding_done)
                self.assertIn("save", window._onboarding_done)
            finally:
                window.close()

    def test_empty_state_and_keyboard_accessibility(self):
        with TemporaryDirectory() as folder:
            window = self.window(folder)
            try:
                self.assertEqual(window.commands["guide"].shortcut().toString(),
                                 "Ctrl+Shift+G")
                self.assertEqual(window.guide_next_button.objectName(),
                                 "r18-guide-next")
                self.assertTrue(window.guide_list.accessibleName())
                self.assertTrue(window.guide_hint.accessibleName())
                self.assertTrue(window.guide_panel.accessibleName())
                window.navigate("cinematics")
                current = window.pages["cinematics"]
                self.assertIsNotNone(
                    current.findChild(type(window.guide_hint), "r18-empty-workspace"))
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()

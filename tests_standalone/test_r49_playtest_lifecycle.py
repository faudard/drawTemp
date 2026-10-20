"""R49.B3 supervised process lifecycle and Studio return tests.

No real game/window is required by the Qt smoke: it replaces only the hardcoded
Player executable invocation with a short local Python process. The real Player
binary, graphics, sound and game actions still need manual release-gate tests.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from drawtemp.studio.r49_playtest import (
    ACTIVE, TERMINAL, EditorReturnContext, PlaytestRun,
)


def context():
    return EditorReturnContext(
        "maps", (("maps", "", "village"), ("actors", "village", "guard")),
        "resources", "/tmp/studio-test/game.json", 12345,
    )


class PlaytestLifecycleContractsTests(unittest.TestCase):
    def test_launch_and_clean_exit_are_distinct_events(self):
        run = PlaytestRun()
        run.begin(context())
        self.assertTrue(run.active)
        self.assertEqual(run.phase, "starting")
        self.assertFalse(run.successful)
        self.assertFalse(run.finish(0) is False)  # pre-start exit is failure
        self.assertEqual(run.phase, "failed")
        self.assertFalse(run.successful)
        run.begin(context())
        self.assertTrue(run.started())
        self.assertFalse(run.successful)
        self.assertTrue(run.finish(0))
        self.assertEqual(run.phase, "finished")
        self.assertTrue(run.successful)
        self.assertEqual(run.exit_code, 0)
        self.assertFalse(run.finish(0))

    def test_start_failure_exit_and_crash_not_marked_passed(self):
        run = PlaytestRun()
        run.begin(context())
        self.assertTrue(run.failed_to_start("Executable missing"))
        self.assertEqual(run.phase, "failed")
        self.assertIn("Executable missing", run.report())
        self.assertFalse(run.successful)
        self.assertFalse(run.started())
        run.begin(context())
        self.assertTrue(run.started())
        run.note_error("Playback issue")
        self.assertTrue(run.finish(0))
        self.assertEqual(run.phase, "failed")
        run.begin(context())
        self.assertTrue(run.started())
        self.assertTrue(run.finish(2))
        self.assertFalse(run.successful)
        run.begin(context())
        self.assertTrue(run.started())
        self.assertTrue(run.finish(0, crashed=True))
        self.assertFalse(run.successful)

    def test_stop_is_not_completed_success_even_for_exit_zero(self):
        run = PlaytestRun()
        run.begin(context())
        run.started()
        self.assertTrue(run.request_stop())
        self.assertFalse(run.request_stop())
        self.assertEqual(run.phase, "stopping")
        run.finish(0)
        self.assertEqual(run.phase, "stopped")
        self.assertFalse(run.successful)
        self.assertIn("interrompu", run.report())

    def test_output_is_bounded_local_and_utf8_safe(self):
        run = PlaytestRun(max_output_chars=128)
        run.begin(context())
        run.started()
        encoded = "Édition".encode("utf-8")
        run.append("stderr", encoded[:1])
        run.append("stderr", encoded[1:])
        self.assertIn("Édition", run.stream("stderr"))
        run.append("stdout", "x" * 100000)
        self.assertLessEqual(len(run.stream("stdout")), 150)
        self.assertIn("sortie tronquée", run.stream("stdout"))
        self.assertNotIn("/tmp/studio-test", run.report())
        with self.assertRaises(ValueError):
            run.append("network", b"not permitted")
        with self.assertRaises(TypeError):
            run.append("stderr", object())
        run.finish(1)
        self.assertEqual(run.phase, "failed")

    def test_context_validates_identity_and_document(self):
        ref = context()
        self.assertIn(ref.workspace, ("maps",))
        self.assertFalse(ref.matches(object(), None))
        for invalid in (
            {"workspace": "bogus"},
            {"resource_keys": (("actors", "short"),)},
            {"focus_region": "widget_private_ptr"},
            {"document_path": " "},
            {"session_identity": "123"},
        ):
            data = {
                "workspace": ref.workspace,
                "resource_keys": ref.resource_keys,
                "focus_region": ref.focus_region,
                "document_path": ref.document_path,
                "session_identity": ref.session_identity,
            }
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                EditorReturnContext(**(data | invalid))
        with self.assertRaises(RuntimeError):
            run = PlaytestRun()
            run.begin(ref)
            run.begin(ref)

    def test_parameter_guards(self):
        with self.assertRaises(ValueError):
            PlaytestRun(max_output_chars=0)
        with self.assertRaises(ValueError):
            PlaytestRun(max_output_chars=True)
        run = PlaytestRun()
        with self.assertRaises(TypeError):
            run.begin("not a context")
        run.begin(context())
        with self.assertRaises(ValueError):
            run.finish("zero")


@unittest.skipUnless(importlib.util.find_spec("PySide6"),
                     "PySide6 unavailable")
class PlaytestQtIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, folder):
        from PySide6.QtCore import QSettings
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        from drawtemp.studio.qt_shell import StudioWindow
        session = AuthoringSession.new(*reference_project())
        path = Path(folder) / "game.json"
        session.save_as(path)
        settings = QSettings(str(Path(folder) / "r49b3.ini"),
                             QSettings.IniFormat)
        window = StudioWindow(session, content_path=path, settings=settings)
        window.show()
        self.app.processEvents()
        return window

    def _pump(self, window, *, timeout=10):
        deadline = time.monotonic() + timeout
        while window._r49_playtest.active and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.015)
        self.app.processEvents()
        self.assertFalse(window._r49_playtest.active,
                         "QProcess did not reach a terminal state")

    def _close(self, window):
        with patch.object(window, "_confirm_leave", return_value=True):
            window.close()
        window.deleteLater()
        self.app.processEvents()

    def test_true_os_process_clean_exit_report_and_return(self):
        from drawtemp.studio.workspace_model import resources
        with TemporaryDirectory() as folder:
            window = self._window(folder)
            try:
                actor = next(r for r in resources(window.session.snapshot())
                             if r.family == "actors")
                self.assertTrue(window.focus_resource(actor.key))
                initial_revision = window.session.revision
                with patch.object(window, "_start_player_process",
                                  side_effect=lambda p: p.start(
                                      sys.executable, ["-c", "print('player-demo')"])):
                    self.assertTrue(window.playtest())
                self.assertFalse(window.commands["playtest"].isEnabled())
                self.assertFalse(window._confirm_leave())
                self.assertFalse(window.playtest())
                window.navigate("publication")
                self._pump(window)
                self.assertEqual(window._r49_playtest.phase, "finished")
                self.assertEqual(window._r49_playtest.exit_code, 0)
                self.assertIn("player-demo",
                              window._r49_playtest.stream("stdout"))
                self.assertEqual(window._active_workspace, "publication")
                self.assertTrue(window.commands["return_playtest"].isEnabled())
                self.assertTrue(window.return_to_playtest_editor())
                self.assertEqual(window._active_workspace, "project")
                self.assertEqual(window._selected[0].key, actor.key)
                self.assertEqual(window.session.revision, initial_revision)
                self.assertEqual(window.content_path, Path(folder) / "game.json")
                self.assertFalse(window._r49_playtest.active)
            finally:
                self._close(window)

    def test_os_process_nonzero_and_failed_start_not_success(self):
        with TemporaryDirectory() as folder:
            window = self._window(folder)
            try:
                with patch.object(window, "_start_player_process",
                                  side_effect=lambda p: p.start(
                                      sys.executable, ["-c",
                                                       "import sys;sys.stderr.write('error\\n');sys.exit(7)"])):
                    self.assertTrue(window.playtest())
                self._pump(window)
                self.assertEqual(window._r49_playtest.phase, "failed")
                self.assertEqual(window._r49_playtest.exit_code, 7)
                self.assertIn("error", window._r49_playtest.stream("stderr"))
                with patch.object(window, "_start_player_process",
                                  side_effect=lambda p: p.start(
                                      "__drawtemp_missing_player_executable__",
                                      [])):
                    self.assertTrue(window.playtest())
                self._pump(window)
                self.assertEqual(window._r49_playtest.phase, "failed")
                self.assertIsNone(window._r49_playtest.exit_code)
                self.assertFalse(window._r49_playtest.successful)
            finally:
                self._close(window)

    def test_request_stop_is_not_mistaken_for_success(self):
        with TemporaryDirectory() as folder:
            window = self._window(folder)
            try:
                with patch.object(window, "_start_player_process",
                                  side_effect=lambda p: p.start(
                                      sys.executable, ["-c",
                                                       "import time;time.sleep(15)"])):
                    self.assertTrue(window.playtest())
                deadline = time.monotonic() + 8
                while window._r49_playtest.phase == "starting" and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertEqual(window._r49_playtest.phase, "running")
                self.assertTrue(window.stop_playtest())
                self._pump(window)
                self.assertEqual(window._r49_playtest.phase, "stopped")
                self.assertFalse(window._r49_playtest.successful)
            finally:
                self._close(window)


if __name__ == "__main__":
    unittest.main()

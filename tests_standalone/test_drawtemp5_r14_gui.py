"""R14.4 Qt input journeys on the actual Studio/Player UIs.

CI uses a software/offscreen Qt backend. These are UI-input regression tests,
not a full onscreen accessibility or real-GPU certification.
"""
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "Qt 6 optional; R14 matrix installs pinned PySide6")
class QtUserJourneys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["drawtemp-r14-e2e"])

    def test_map_mouse_paint_undo_redo_and_save_reload(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QToolButton
        from drawtemp.studio.map_editor import MapWindow
        from drawtemp.studio.map_authoring import MapStudio

        with TemporaryDirectory() as folder:
            saved = Path(folder) / "map.json"
            studio = MapStudio.reference()
            studio.save_as(saved)
            window = MapWindow(studio)
            window.show()
            try:
                QTest.qWait(200)
                self.assertIsNotNone(window.viewport.rootObject())
                self.assertEqual(window.viewport.rootObject().property("interactionMode"), "edit")
                # Set tool through its actual ComboBox; paint through a real Qt mouse event.
                window.tools.setCurrentText("Pinceau")
                window.material.setCurrentText("stone")
                x, y = 2, 2
                p = window.renderer.projection.project(x, y)
                sx, sy = window.renderer.camera.screen(*p)
                point = QPoint(round(sx), round(sy))
                self.assertGreater(point.x(), 0)
                self.assertLess(point.x(), window.viewport.width())
                self.assertGreater(point.y(), 0)
                self.assertLess(point.y(), window.viewport.height())
                before = studio.snapshot()["revision"]
                QTest.mouseClick(window.viewport, Qt.LeftButton, pos=point)
                QTest.qWait(80)
                self.assertEqual(studio.sample((x, y)), "stone")
                self.assertEqual(studio.snapshot()["revision"], before + 1)
                self.assertEqual(window.renderer.scene["mission"], studio.mission_id)

                def press_tool(label):
                    button = next((b for b in window.findChildren(QToolButton)
                                   if b.defaultAction() is not None and
                                   b.defaultAction().text() == label), None)
                    self.assertIsNotNone(button, "Missing toolbar action: " + label)
                    self.assertTrue(button.isVisible(), "Toolbar action is hidden: " + label)
                    QTest.mouseClick(button, Qt.LeftButton)
                    QTest.qWait(50)

                press_tool("Annuler")
                self.assertNotEqual(studio.sample((x, y)), "stone")
                press_tool("Rétablir")
                self.assertEqual(studio.sample((x, y)), "stone")
                press_tool("Enregistrer")
                reloaded = MapStudio.open(saved)
                self.assertEqual(reloaded.sample((x, y)), "stone")
                self.assertFalse(studio.snapshot()["dirty"])

                # R14.5: submit the real rendered frame for external golden review.
                # The capture is NOT considered an approved baseline.
                folder_env = os.environ.get("DRAWTEMP_R14_ARTIFACT_DIR")
                if folder_env:
                    from drawtemp.quality.visual import capture_widget
                    capture_widget(window.viewport, Path(folder_env) / "r14-studio.png")
            finally:
                # If assertion fails after edit, do not trigger offscreen modal
                # confirmation during tearDown.
                window.hide()
                window.deleteLater()

    def test_player_qml_clicks_new_choice_mission_save_resume(self):
        """Exercise real Player inputs in its production QGuiApplication.

        R14 also exercises a QQuickWidget-based Studio in the same unittest
        class. On macOS/Qt 6.8 a second QQmlApplicationEngine with its own
        QQuickWindow after that Widget's scenegraph can segfault. Player
        production always runs in a separate process, so the gate must verify
        that real lifecycle rather than accidentally combining two runtimes.
        The production --gui-journey performs actual QTest mouse/keyboard
        input through the QML buttons and checks save/resume itself.
        """
        import subprocess
        import sys

        with TemporaryDirectory() as folder:
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                       QT_QUICK_BACKEND="software")
            process = subprocess.run(
                [sys.executable, "-m", "drawtemp.player.qt_app",
                 "--reference", "--save-dir", folder, "--gui-journey"],
                cwd=Path(__file__).resolve().parents[1], env=env,
                capture_output=True, text=True, timeout=75, check=False)
            self.assertEqual(process.returncode, 0,
                             process.stdout + "\n" + process.stderr)
            self.assertIn("R14 Player QML GUI input:", process.stdout)
            self.assertTrue((Path(folder) / "slot_1.json").is_file())
            # Read the actual checkpoint through the canonical Player, not a
            # synthetic mock or the subprocess' stdout alone.
            from drawtemp.player.qt_app import build_controller
            restored = build_controller(save_dir=folder, reference=True)
            restored.load(1)
            self.assertEqual(restored.state()["screen"], "battle")


if __name__ == "__main__":
    unittest.main()

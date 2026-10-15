"""R14.4: click real Map Studio viewport and toolbar, persist and reopen.

Qt software/offscreen CI tests mouse, transaction, undo, redo and persistence;
it is not a GPU/onscreen release certificate.
"""
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.studio.map_authoring import MapStudio


class MapStudioGuiJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("QT_QPA_PLATFORM") not in ("offscreen", "xcb", "windows", "cocoa"):
            raise RuntimeError("Set an explicit Qt platform for R14 GUI testing")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["drawtemp-r14-gui"])

    def test_mouse_paint_keyboard_undo_redo_and_save_reopen(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtWidgets import QToolButton
        from drawtemp.studio.map_editor import MapWindow

        with TemporaryDirectory() as directory:
            filename = Path(directory) / "r14-gui-map.json"
            studio = MapStudio.reference()
            studio.save_as(filename)
            window = MapWindow(studio=studio)
            window.show()
            try:
                QTest.qWait(120)
                self.assertEqual(window.viewport.status(), QQuickWidget.Ready,
                                 "\n".join(str(e) for e in window.viewport.errors()))
                self.assertTrue(window.viewport.isVisible())
                scene = window.renderer.scene
                x, y = scene["width"] // 2, scene["height"] // 2
                heights = {(t["x"], t["y"]): t["height"] for t in scene["tiles"]}
                sx, sy = window.renderer.camera.screen(
                    *window.renderer.projection.project(x, y, heights.get((x, y), 0)))
                pixel = QPoint(round(sx), round(sy))
                self.assertGreaterEqual(pixel.x(), 0)
                self.assertGreaterEqual(pixel.y(), 0)
                self.assertLess(pixel.x(), window.viewport.width())
                self.assertLess(pixel.y(), window.viewport.height())
                self.assertEqual(window.renderer.cellAt(sx, sy), {"x": x, "y": y})
                before = studio.sample((x, y))
                target = "stone" if before != "stone" else "sand"
                window.material.setCurrentText(target)
                self.assertEqual(window.material.currentText(), target)

                def toolbar_button(name):
                    matches = [button for button in window.findChildren(QToolButton)
                               if button.defaultAction() is not None
                               and button.defaultAction().text() == name]
                    self.assertEqual(len(matches), 1, f"Missing {name} toolbar button")
                    return matches[0]

                revision = studio.snapshot()["revision"]
                QTest.mouseClick(window.viewport, Qt.LeftButton, pos=pixel)
                QTest.qWait(40)
                self.assertEqual(studio.sample((x, y)), target,
                                 "MouseArea must deliver one real Qt pointer gesture")
                self.assertGreater(studio.snapshot()["revision"], revision)

                QTest.mouseClick(toolbar_button("Annuler"), Qt.LeftButton)
                self.assertEqual(studio.sample((x, y)), before)
                redo = toolbar_button("Rétablir")
                redo.setFocus()
                QTest.keyClick(redo, Qt.Key_Space)
                self.assertEqual(studio.sample((x, y)), target)

                QTest.mouseClick(toolbar_button("Enregistrer"), Qt.LeftButton)
                self.assertFalse(studio.snapshot()["dirty"])
                self.assertEqual(MapStudio.open(filename).sample((x, y)), target)
            finally:
                window.hide()
                window.deleteLater()
                self.app.processEvents()


class PlayerGuiJourney(unittest.TestCase):
    def test_real_qml_mouse_keyboard_and_resume(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                       QT_QUICK_BACKEND="software")
            result = subprocess.run(
                [sys.executable, "-m", "drawtemp.player.qt_app",
                 "--reference", "--gui-journey", "--save-dir", directory],
                cwd=root, env=env, text=True, capture_output=True,
                timeout=60, check=False)
            self.assertEqual(result.returncode, 0,
                             "Player GUI journey failed:\n" +
                             result.stdout + "\n" + result.stderr)
            self.assertIn("R14 Player QML GUI input:", result.stdout)
            self.assertTrue((Path(directory) / "slot_1.json").is_file())


if __name__ == "__main__":
    unittest.main()

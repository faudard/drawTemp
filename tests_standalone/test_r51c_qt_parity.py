"""R51.C optional shared-QML visual parity smoke (software renderer only).

Opt-in offscreen smoke compares two instances of the actual shared component.
It is not an approved golden, hardware GPU, real controller or release gate.
"""
from hashlib import sha256
import os
from pathlib import Path
import unittest

from drawtemp.studio.r51_layout_draft import new_layout, editor_sample


@unittest.skipUnless(os.environ.get("DRAWTEMP_R51_QT_GATE") == "1",
                     "Set DRAWTEMP_R51_QT_GATE=1 for explicit Qt rendering")
class R51CQtParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError as exc:
            raise unittest.SkipTest("PySide6 is not installed") from exc
        cls.app = QApplication.instance() or QApplication([])

    def _load(self, projection, *, high_contrast, scale):
        from PySide6.QtCore import QUrl
        from PySide6.QtQuickWidgets import QQuickWidget
        qml = (Path(__file__).parents[1] / "drawtemp" /
               "player" / "R51Layout.qml")
        widget = QQuickWidget()
        widget.setObjectName("r51-parity-capture")
        widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        widget.resize(420, 260)
        widget.setSource(QUrl.fromLocalFile(str(qml)))
        self.assertIsNotNone(widget.rootObject(),
                             "R51 shared QML failed: " +
                             ", ".join(str(e) for e in widget.errors()))
        root = widget.rootObject()
        root.setProperty("projection", projection)
        root.setProperty("allowActions", False)
        root.setProperty("permittedActions", [])
        root.setProperty("highContrast", high_contrast)
        root.setProperty("textScale", scale)
        widget.show()
        self.app.processEvents()
        return widget

    def _capture(self, widget):
        from PySide6.QtTest import QTest
        QTest.qWait(120)
        self.app.processEvents()
        image = widget.grabFramebuffer().convertToFormat(4)  # QImage.Format_RGB32
        self.assertFalse(image.isNull(), "Qt offscreen produced an empty frame")
        self.assertEqual(image.width(), 420)
        self.assertEqual(image.height(), 260)
        return sha256(bytes(image.bits())).hexdigest()

    def test_same_sample_and_theme_yield_identical_shared_qml_frames(self):
        projection = editor_sample(new_layout("MENU"), 1000)
        studio = self._load(projection, high_contrast=True, scale=1.2)
        player = self._load(projection, high_contrast=True, scale=1.2)
        try:
            self.assertEqual(studio.rootObject().property("highContrast"), True)
            self.assertEqual(player.rootObject().property("textScale"), 1.2)
            self.assertEqual(self._capture(studio), self._capture(player))
        finally:
            studio.close()
            player.close()

    def test_contrast_and_scale_are_actual_render_inputs(self):
        projection = editor_sample(new_layout("MENU"), 700)
        standard = self._load(projection, high_contrast=False, scale=1.0)
        contrasted = self._load(projection, high_contrast=True, scale=1.35)
        try:
            self.assertNotEqual(self._capture(standard), self._capture(contrasted))
        finally:
            standard.close()
            contrasted.close()


if __name__ == "__main__":
    unittest.main()

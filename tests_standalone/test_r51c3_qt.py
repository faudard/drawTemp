"""R51.C3 opt-in Qt software-only proof of shared action HUD and campaign bag."""
import os
from pathlib import Path
import unittest

from drawtemp.studio.r51_layout_draft import editor_sample, new_layout


@unittest.skipUnless(os.environ.get("DRAWTEMP_R51_QT_GATE") == "1",
                     "R51 Qt gate requires explicit opt-in; no GPU certification")
class AuthoredActionQtSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError as exc:
            raise unittest.SkipTest("PySide6 not installed") from exc
        cls.app = QApplication.instance() or QApplication([])

    def test_shared_qml_renders_action_and_campaign_inventory_layouts(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtTest import QTest
        qml = Path(__file__).parents[1] / "drawtemp/player/R51Layout.qml"
        for kind in ("HUD_ACTION", "INVENTORY"):
            with self.subTest(kind=kind):
                preview = QQuickWidget()
                try:
                    preview.setResizeMode(QQuickWidget.SizeRootObjectToView)
                    preview.resize(440, 280)
                    preview.setSource(QUrl.fromLocalFile(str(qml)))
                    root = preview.rootObject()
                    self.assertIsNotNone(root, str(preview.errors()))
                    sample = editor_sample(new_layout(kind), 440)
                    root.setProperty("projection", sample)
                    root.setProperty("allowActions", False)
                    root.setProperty("permittedActions", [])
                    root.setProperty("highContrast", True)
                    root.setProperty("textScale", 1.2)
                    preview.show()
                    QTest.qWait(80)
                    self.assertEqual(root.property("projection")["kind"], kind)
                    self.assertTrue(root.property("highContrast"))
                    self.assertFalse(preview.grabFramebuffer().isNull())
                finally:
                    preview.close()


if __name__ == "__main__":
    unittest.main()

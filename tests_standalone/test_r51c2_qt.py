"""R51.C2 optional Qt renderer proof for authored dialogue and inventory."""
import os
from pathlib import Path
import unittest

from drawtemp.studio.r51_layout_draft import editor_sample, new_layout


@unittest.skipUnless(os.environ.get("DRAWTEMP_R51_QT_GATE") == "1",
                     "Qt preview is explicit and not a real GPU qualification")
class AuthoredQtScreensSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError as exc:
            raise unittest.SkipTest("PySide6 unavailable") from exc
        cls.app = QApplication.instance() or QApplication([])

    def test_shared_renderer_loads_dialogue_and_inventory_without_player_commands(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtTest import QTest
        qml = (Path(__file__).parents[1] / "drawtemp" /
               "player" / "R51Layout.qml")
        for kind in ("DIALOGUE", "INVENTORY"):
            with self.subTest(kind=kind):
                widget = QQuickWidget()
                try:
                    widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
                    widget.resize(520, 350)
                    widget.setSource(QUrl.fromLocalFile(str(qml)))
                    root = widget.rootObject()
                    self.assertIsNotNone(root,
                                         "Failed to load shared Qt Quick UI: " +
                                         "; ".join(str(e) for e in widget.errors()))
                    model = editor_sample(new_layout(kind), 520)
                    root.setProperty("projection", model)
                    root.setProperty("allowActions", False)
                    root.setProperty("permittedActions", [])
                    widget.show()
                    QTest.qWait(80)
                    self.assertEqual(root.property("allowActions"), False)
                    self.assertEqual(root.property("projection")["kind"], kind)
                    frame = widget.grabFramebuffer()
                    self.assertFalse(frame.isNull(), "Qt produced an empty UI")
                finally:
                    widget.close()


if __name__ == "__main__":
    unittest.main()

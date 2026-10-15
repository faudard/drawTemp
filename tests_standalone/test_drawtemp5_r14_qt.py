"""R14 Qt 6 functional composition smoke; software/offscreen != real GPU or Player E2E."""
import os
from pathlib import Path
import unittest


class QtIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            raise RuntimeError("R14 Qt CI smoke must explicitly select offscreen backend")
        from PySide6.QtWidgets import QApplication
        cls.application = QApplication.instance() or QApplication(["drawtemp-r14-qa"])

    def test_actual_drawtemp_qml_load_and_resize(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtTest import QTest

        qml = Path(__file__).resolve().parents[1] / "drawtemp/render/Foundation.qml"
        view = QQuickWidget()
        try:
            view.setResizeMode(QQuickWidget.SizeRootObjectToView)
            view.resize(800, 450)
            view.setSource(QUrl.fromLocalFile(str(qml)))
            view.show()
            QTest.qWait(80)
            self.assertEqual(view.status(), QQuickWidget.Ready,
                             "\n".join(error.toString() for error in view.errors()))
            root = view.rootObject()
            self.assertIsNotNone(root)
            self.assertEqual(root.property("width"), 800)
            self.assertEqual(root.property("height"), 450)
            self.assertTrue(any("Fondation R0" in str(child.property("text"))
                                for child in root.children()))
        finally:
            view.close()
            view.deleteLater()

    def test_widgets_focus_and_keyboard_driver(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLineEdit, QMainWindow
        from PySide6.QtTest import QTest

        window = QMainWindow()
        field = QLineEdit()
        window.setCentralWidget(field)
        window.show()
        try:
            field.setFocus()
            QTest.keyClicks(field, "Jeanne")
            self.assertEqual(field.text(), "Jeanne")
            QTest.keyClick(field, Qt.Key_Backspace)
            self.assertEqual(field.text(), "Jeann")
        finally:
            window.close()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()

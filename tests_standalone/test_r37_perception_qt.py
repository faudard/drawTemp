"""R37.D offscreen Studio sensor editor smoke: preview/apply/Undo."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from drawtemp.sdk.authoring import AuthoringSession
from tests_standalone.test_r37_perception import fixture

_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.ai_sensor_qt import AISensorDialog


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class SensorQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_sensor_preview_commit_undo_and_redo(self):
        content, project = fixture()
        editor = AuthoringSession.new(content, project)
        dialog = AISensorDialog(editor)
        self.assertEqual(dialog.objectName(), "r37-sensor-dialog")
        self.assertEqual(dialog.actor.currentText(), "traveler")
        dialog.movement.setChecked(True)
        dialog.preview()
        self.assertIn('"preview_only": true', dialog.diagnostics.toPlainText())
        self.assertEqual(editor.revision, 0)
        dialog.facing.setCurrentIndex(dialog.facing.findData("omni"))
        dialog.validate()
        self.assertTrue(dialog.commands["apply"].isEnabled())
        dialog.apply()
        self.assertEqual(editor.revision, 1)
        self.assertEqual(dialog.designer.agents()[0]["sensor"]["facing"], "omni")
        dialog.undo()
        self.assertEqual(dialog.designer.agents()[0]["sensor"]["facing"], "west")
        dialog.redo()
        self.assertEqual(dialog.designer.agents()[0]["sensor"]["facing"], "omni")
        dialog.remove()
        self.assertIsNone(dialog.designer.agents()[0]["sensor"])
        dialog.close()


if __name__ == "__main__":
    unittest.main()

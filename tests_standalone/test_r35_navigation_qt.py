"""Qt offscreen R35.D1: waypoint authoring follows canonical R1 validation."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.living_world import EXTENSION
from tests_standalone.test_r35_navigation import positional_village

_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtCore import QTime
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.living_world_qt import LivingWorldDialog


@unittest.skipUnless(_HAS_QT, "PySide6 is optional")
class NavigationEditorQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_waypoint_edit_preview_and_undo_roundtrip(self):
        content, project = positional_village()
        editor = AuthoringSession.new(content, project)
        dialog = LivingWorldDialog(editor)
        self.assertEqual(dialog.npc_select.currentText(), "merchant")
        dialog.stops.setCurrentRow(1)
        self.assertTrue(dialog.stop_pos.isChecked())
        self.assertEqual((dialog.stop_x.value(), dialog.stop_y.value()), (3, 1))
        dialog.stop_x.setValue(3)
        dialog.stop_y.setValue(0)
        dialog.stop_time.setTime(QTime(8, 0))
        dialog._update_stop()
        dialog._preview()
        self.assertIn("PNJ : 4", dialog.diagnostics.toPlainText())
        self.assertEqual(editor.revision, 0)
        dialog._apply()
        self.assertEqual(editor.revision, 1)
        project_after = editor.snapshot().to_dict()["project"]
        stops = project_after["extensions"][EXTENSION]["data"]["npcs"][0]["schedule"]
        self.assertEqual(stops[1]["pos"], [3, 0])
        editor.undo()
        previous = editor.snapshot().to_dict()["project"]
        self.assertEqual(
            previous["extensions"][EXTENSION]["data"]["npcs"][0]["schedule"][1]["pos"],
            [3, 1])
        dialog.close()


if __name__ == "__main__":
    unittest.main()

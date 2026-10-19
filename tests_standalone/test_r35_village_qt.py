"""R35.C2 offscreen Qt smoke: NPC schedule changes use canonical R1 history."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.living_world import EXTENSION
from tests_standalone.test_r35_village import living_village

_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtCore import QTime
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.living_world_qt import LivingWorldDialog


@unittest.skipUnless(_HAS_QT, "PySide6 optional")
class LivingWorldQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_schedule_visual_edit_preview_and_undo(self):
        content, project = living_village()
        editor = AuthoringSession.new(content, project)
        dialog = LivingWorldDialog(editor)
        self.assertEqual(dialog.npc_select.count(), 4)
        self.assertEqual(dialog.stops.count(), 3)
        self.assertEqual(dialog.npc_select.currentText(), "merchant")
        dialog.stops.setCurrentRow(1)
        dialog.stop_time.setTime(QTime(8, 1))
        dialog._update_stop()
        dialog._preview()
        self.assertIn("PNJ : 4", dialog.diagnostics.toPlainText())
        self.assertEqual(editor.revision, 0)
        dialog._apply()
        self.assertEqual(editor.revision, 1)
        updated = editor.snapshot().to_dict()
        stops = updated["project"]["extensions"][EXTENSION]["data"]["npcs"][0]["schedule"]
        self.assertEqual(stops[1]["minute"], 481)
        editor.undo()
        stops = editor.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"]["npcs"][0]["schedule"]
        self.assertEqual(stops[1]["minute"], 480)
        dialog.close()


if __name__ == "__main__":
    unittest.main()

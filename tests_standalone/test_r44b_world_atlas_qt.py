"""R44.B optional Qt offscreen smoke: atlas edit, Apply and Undo."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.world_graph44 import EXTENSION
from tests_standalone.test_r25_scene_router import scene_fixture

_HAS_QT = importlib.util.find_spec("PySide6") is not None
if _HAS_QT:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.world_atlas_qt import WorldAtlasDialog


@unittest.skipUnless(_HAS_QT, "Requires PySide6 (optional Qt)")
class WorldAtlasQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_init_move_preview_apply_undo(self):
        content, project = scene_fixture()
        editor = AuthoringSession.new(content, project)
        dialog = WorldAtlasDialog(editor)
        self.assertEqual(dialog.scenes.count(), 2)
        self.assertEqual(dialog.portals.count(), 3)
        self.assertEqual(editor.revision, 0)
        dialog.x.setValue(36)
        self.assertEqual(editor.revision, 0)
        dialog.preview()
        self.assertTrue(dialog.apply_button.isEnabled())
        dialog.apply()
        self.assertEqual(editor.revision, 1)
        data = editor.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"]
        entries = [s for r in data["regions"] for s in r["scenes"]]
        self.assertEqual(entries[0]["origin"][0], 36)
        dialog.undo()
        self.assertNotIn(EXTENSION, editor.snapshot().to_dict()["project"].get("extensions", {}))
        dialog.redo()
        self.assertEqual(editor.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"],
                         data)
        dialog.close()


if __name__ == "__main__":
    unittest.main()

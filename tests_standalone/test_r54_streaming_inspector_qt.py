"""R54.B Qt offscreen smoke: world graph, region edit and safe cache shutdown."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_HAS_QT = importlib.util.find_spec("PySide6") is not None

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.world_streaming import EXTENSION
from tests_standalone.test_r54_world_streaming import fixture

if _HAS_QT:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.world_streaming_qt import WorldStreamingDialog


@unittest.skipUnless(_HAS_QT, "PySide6 is optional")
class WorldStreamingQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_no_json_route_generation_lod_and_atomic_undo(self):
        content, project = fixture()
        editor = AuthoringSession.new(content, project)
        dialog = WorldStreamingDialog(editor)
        try:
            self.assertEqual(dialog.tree.topLevelItemCount(), 3)
            self.assertEqual(dialog.zoom.currentData(), 1.0)
            self.assertIn("Cache :", dialog.status.text())
            dialog.generate_from_routes()
            self.assertEqual(dialog.tree.topLevelItemCount(), 3)
            self.assertEqual(editor.revision, 0)
            self.assertGreater(len(dialog.graph.scene().items()), 3)

            cell = next(
                dialog.tree.topLevelItem(i)
                for i in range(dialog.tree.topLevelItemCount())
                if dialog.tree.topLevelItem(i).data(0, Qt.UserRole) == "forest")
            dialog.tree.setCurrentItem(cell)
            dialog.region.setText("bois")
            dialog.change_region()
            dialog.preview_changes()
            self.assertTrue(dialog.apply_button.isEnabled())
            dialog.apply_changes()
            self.assertEqual(editor.revision, 1)
            current = editor.snapshot().to_dict()["project"]
            names = {c["id"]: c["region"] for c in
                     current["extensions"][EXTENSION]["data"]["cells"]}
            self.assertEqual(names["forest"], "bois")
            editor.undo()
            self.assertEqual(editor.revision, 2)
            restored = editor.snapshot().to_dict()["project"]
            self.assertEqual(restored["extensions"][EXTENSION]["data"]["cells"][1]["id"],
                             "woods")
            editor.redo()
            self.assertEqual(editor.revision, 3)

            dialog.prefetch_neighbors()
            self.assertLessEqual(dialog.cache.stats()["pending"], 8)
            self.assertEqual(dialog.cache.stats()["budget_bytes"], 4 * 1024 * 1024)
        finally:
            dialog.reject()
        self.assertIsNone(dialog.cache)
        self.assertFalse(dialog.timer.isActive())


if __name__ == "__main__":
    unittest.main()

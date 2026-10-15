"""R5.7 Qt offscreen contract: visible selection, ghost, atomic toolbar apply."""
import importlib.util
import os
import unittest

QT_AVAILABLE = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(QT_AVAILABLE, "PySide6 is optional")
class MapSelectionQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def new_window(self):
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.studio.map_editor import MapWindow
        studio = MapStudio.reference()
        studio.create("r57_qt", "R5 Qt", 12, 12)
        window = MapWindow(studio)
        self.addCleanup(window.deleteLater)
        self.assertIsNotNone(window.viewport.rootObject())
        return window

    def state(self, root, name):
        value = root.property(name)
        return value.toVariant() if hasattr(value, "toVariant") else value

    def test_selection_modes_additive_lasso_and_overlays(self):
        w = self.new_window()
        w.tools.setCurrentText("Sélection")
        w.begin_stroke(3, 3)
        w.finish_stroke(4, 4)
        self.assertEqual(len(w.selection), 4)
        root = w.viewport.rootObject()
        self.assertEqual(len(self.state(root, "selectionCells")), 4)
        w.additive_selection.setChecked(True)
        w.begin_stroke(7, 7)
        w.finish_stroke(7, 7)
        self.assertEqual(len(w.selection), 5)
        w.tools.setCurrentText("Lasso")
        for i, point in enumerate(((4, 4), (6, 4), (6, 6), (4, 6), (4, 4))):
            if i == 0:
                w.begin_stroke(*point)
            else:
                w.extend_stroke(*point)
        w.finish_stroke(4, 4)
        self.assertIn((5, 5), w.selection)
        self.assertIn((7, 7), w.selection)
        self.assertTrue(len(self.state(root, "selectionCells")) >= 10)

    def test_duplicate_and_commit_ghost_with_single_undo(self):
        w = self.new_window()
        w.studio.paint([(3, 3)], "surface:stone")
        w.refresh()
        w.tools.setCurrentText("Sélection")
        w.begin_stroke(3, 3)
        w.finish_stroke(3, 3)
        w.copy_selection()
        self.assertIsNotNone(w.studio.region_clipboard)
        before = w.studio.snapshot()
        w.start_transform("duplicate")
        w._hover_transform(7, 7)
        self.assertIsNotNone(w.pending_transform)
        root = w.viewport.rootObject()
        preview = self.state(root, "transformCells")
        self.assertEqual(len(preview), 1)
        self.assertFalse(preview[0]["invalid"])
        self.assertEqual(before, w.studio.snapshot())
        w.apply_transform()
        self.assertEqual(w.studio.sample((7, 7)), "stone")
        self.assertEqual(w.studio.authoring.revision, before["revision"]+1)
        self.assertEqual(self.state(root, "transformCells"), [])
        self.assertEqual(w.selection, [(7, 7)])
        w.undo()
        self.assertEqual(w.studio.sample((7, 7)), "grass")

    def test_invalid_ghost_never_commits_and_shortcuts_present(self):
        w = self.new_window()
        w.studio.paint([(3, 3)], "surface:stone")
        w.refresh()
        w.selection = [(3, 3)]
        w._render_selection()
        w.start_transform("duplicate")
        w._hover_transform(3, 3)
        self.assertIsNone(w.pending_transform)
        root = w.viewport.rootObject()
        red = self.state(root, "transformCells")
        self.assertTrue(red)
        self.assertTrue(red[0]["invalid"])
        w.cancel_transform()
        self.assertFalse(self.state(root, "transformCells"))
        self.assertIn("Ctrl+R", w.toolbar_actions["Rotation ↻"].shortcut().toString())
        self.assertIn("Ctrl+D", w.toolbar_actions["Dupliquer sélection"].shortcut().toString())

    def test_in_place_mirror_visual_preview_and_apply(self):
        w = self.new_window()
        w.studio.paint([(3, 3)], "surface:stone")
        w.studio.paint([(4, 3)], "surface:sand")
        w.refresh()
        w.selection = [(3, 3), (4, 3)]
        w._render_selection()
        revision = w.studio.authoring.revision
        w.start_transform("mirror_x")
        self.assertIsNotNone(w.pending_transform)
        w.apply_transform()
        self.assertEqual(w.studio.sample((3, 3)), "sand")
        self.assertEqual(w.studio.sample((4, 3)), "stone")
        self.assertEqual(w.studio.authoring.revision, revision + 1)


if __name__ == "__main__":
    unittest.main()

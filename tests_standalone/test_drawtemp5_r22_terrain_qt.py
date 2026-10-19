"""R22.2A Qt offscreen smoke: palette, preview ghost and commit."""
import importlib.util
import os
import unittest
from unittest.mock import patch

from drawtemp.studio.map_authoring import MapStudio

QT_AVAILABLE = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(QT_AVAILABLE, "PySide6 is optional")
class TerrainGenerationQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def new_window(self):
        from drawtemp.studio.map_editor import MapWindow
        studio = MapStudio.reference()
        studio.create("r22_qt", "Carte R22", 16, 16)
        window = MapWindow(studio)
        self.addCleanup(window.deleteLater)
        return window

    def test_biome_ghost_preview_cancel_commit(self):
        w = self.new_window()
        w.selection = [(8, 8), (9, 8), (8, 9), (9, 9)]
        w.gen_selected_only.setChecked(True)
        w.gen_biome.setCurrentText("Roche")
        w.gen_coverage.setValue(100)
        w.gen_seed.setValue(42)
        rev = w.studio.authoring.revision
        w.preview_generation()
        self.assertIsNotNone(w.pending_generation)
        self.assertEqual(rev, w.studio.authoring.revision)
        self.assertTrue(w.gen_apply_button.isEnabled())
        root = w.viewport.rootObject()
        projected = root.property("transformCells")
        projected = projected.toVariant() if hasattr(projected, "toVariant") else projected
        self.assertEqual(len(projected), 4)
        w.cancel_generation()
        self.assertIsNone(w.pending_generation)
        self.assertEqual(rev, w.studio.authoring.revision)
        w.preview_generation()
        w.gen_seed.setValue(43)
        self.assertIsNone(w.pending_generation)
        self.assertFalse(w.gen_apply_button.isEnabled())
        w.preview_generation()
        w.apply_generation()
        self.assertEqual(w.studio.authoring.revision, rev + 1)
        self.assertEqual(len(w.studio.mission()["board"]["tiles"]), 4)
        w.undo()
        self.assertEqual(w.studio.authoring.revision, rev + 2)
        self.assertEqual(w.studio.mission()["board"]["tiles"], [])

    def test_selection_required_and_map_change_cancels_preview(self):
        w = self.new_window()
        w.gen_selected_only.setChecked(True)
        with patch("drawtemp.studio.map_editor.QMessageBox.warning"):
            w.preview_generation()
        self.assertIsNone(w.pending_generation)
        w.gen_selected_only.setChecked(False)
        w.gen_coverage.setValue(100)
        w.preview_generation()
        self.assertIsNotNone(w.pending_generation)
        w.change_map(0)
        self.assertIsNone(w.pending_generation)


if __name__ == "__main__":
    unittest.main()

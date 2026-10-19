"""R22.2B Qt offscreen: searchable terrain shelf, ghost and smart brush."""
from __future__ import annotations

import importlib.util
import os
import unittest
from unittest.mock import patch

QT_AVAILABLE = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(QT_AVAILABLE, "PySide6 not installed")
class QtPrefabShelfTests(unittest.TestCase):
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
        studio.create("r22b_gui", "Prefab UI", 16, 16)
        window = MapWindow(studio)
        self.addCleanup(window.deleteLater)
        return window

    def test_shelf_filter_and_paste_preview_without_mutating_before_apply(self):
        from PySide6.QtCore import Qt
        w = self.new_window()
        self.assertEqual(w.prefab_list.count(), 4)
        w.prefab_search.setText("étang")
        self.assertEqual(w.prefab_list.count(), 1)
        self.assertEqual(w.prefab_list.item(0).data(Qt.UserRole),
                         "builtin:pond")
        self.assertEqual(w.prefab_category.currentText(), "Tous")
        w.prefab_search.clear()
        w.prefab_category.setCurrentText("Nature")
        self.assertEqual(w.prefab_list.count(), 2)
        w.prefab_category.setCurrentText("Tous")
        w.prefab_list.setCurrentRow(1)  # builtin:pond
        before = w.studio.snapshot()
        w.place_selected_prefab()
        self.assertEqual(w.pending_operation, "paste")
        w._hover_transform(7, 7)
        self.assertIsNotNone(w.pending_transform)
        self.assertEqual(before, w.studio.snapshot())
        root = w.viewport.rootObject()
        ghost = root.property("transformCells")
        ghost = ghost.toVariant() if hasattr(ghost, "toVariant") else ghost
        self.assertEqual(len(ghost), 25)
        w.apply_transform()
        self.assertEqual(w.studio.authoring.revision, before["revision"]+1)
        self.assertIsNone(w.pending_transform)
        w.undo()
        self.assertEqual(w.studio.snapshot()["content"], before["content"])

    def test_smart_brush_is_clipped_to_selection_from_the_widget(self):
        w = self.new_window()
        w.tools.setCurrentText("Pinceau")
        w.material.setCurrentText("stone")
        w.selection = [(6, 6), (7, 6)]
        w.brush_mask.setChecked(True)
        w.brush_radius.setValue(1)
        w.brush_shape.setCurrentIndex(1)  # square
        w.begin_stroke(6, 6)
        w.finish_stroke(7, 6)
        cells = {tuple(t["pos"]) for t in w.studio.mission()["board"]["tiles"]}
        self.assertEqual(cells, {(6, 6), (7, 6)})
        w.undo()
        self.assertEqual(w.studio.mission()["board"]["tiles"], [])

    def test_capture_custom_selection_and_import_fail_closed(self):
        w = self.new_window()
        w.studio.paint([(5, 5)], "surface:stone")
        w.selection = [(5, 5)]
        before = w.studio.snapshot()
        with patch("drawtemp.studio.map_editor.QInputDialog.getText",
                   return_value=("Mon chemin", True)):
            w.capture_selection_prefab()
        self.assertEqual(before, w.studio.snapshot())
        w.prefab_category.setCurrentText("Mes modèles")
        self.assertEqual(w.prefab_list.count(), 1)
        self.assertIn("Mon chemin", w.prefab_list.item(0).text())
        with patch("drawtemp.studio.map_editor.QFileDialog.getOpenFileName",
                   return_value=("/missing/r22-prefabs.json", "JSON (*.json)")), \
             patch("drawtemp.studio.map_editor.QMessageBox.warning"):
            w.import_prefabs()
        self.assertEqual(w.prefab_list.count(), 1)


if __name__ == "__main__":
    unittest.main()

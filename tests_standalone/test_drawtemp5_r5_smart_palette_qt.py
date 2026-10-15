"""R5.4/5.5 Qt real palette/ghost/drop integration (offscreen functional gate)."""
import importlib.util
import os
import unittest

from drawtemp.studio.map_palette import MIME_BRUSH

QT_AVAILABLE = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(QT_AVAILABLE, "PySide6 optional")
class MapPaletteQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QApplication.instance() or QApplication([])

    def test_palette_filters_illustrations_and_drag_mime(self):
        from PySide6.QtCore import Qt
        from drawtemp.studio.map_palette_dock import MapPaletteDock
        palette = MapPaletteDock()
        self.addCleanup(palette.deleteLater)
        self.assertEqual(palette.items.count(), 20)
        self.assertFalse(palette.items.item(0).icon().pixmap(100, 72).isNull())
        palette.family.setCurrentText("Décors")
        self.assertEqual(palette.items.count(), 12)
        palette.search.setText("roseaux")
        self.assertEqual(palette.items.count(), 1)
        item = palette.items.item(0)
        self.assertEqual(item.data(Qt.UserRole), "feature:reeds")
        self.assertFalse(item.icon().pixmap(100, 72).isNull())
        palette.select_brush("surface:stone")
        self.assertEqual(palette.current_brush, "surface:stone")

    def test_editor_ghost_preview_and_smart_paint_are_transactional(self):
        from drawtemp.studio.map_editor import MapWindow
        window = MapWindow()
        self.addCleanup(window.deleteLater)
        window.studio.create("qt_smart", "Carte Qt", 12, 12)
        window.refresh_maps()
        root = window.viewport.rootObject()
        self.assertIsNotNone(root)
        self.assertEqual(root.property("interactionMode"), "edit")
        before = window.studio.snapshot()
        window.palette.select_brush("surface:stone")
        window.tools.setCurrentText("Pinceau intelligent")
        window.smart_radius.setValue(1)
        window._hover_cell(3, 3)
        ghosts = root.property("previewCells")
        ghosts = ghosts.toVariant() if hasattr(ghosts, "toVariant") else ghosts
        self.assertTrue(ghosts)
        self.assertEqual(window.studio.snapshot(), before)
        window.begin_stroke(3, 3)
        window.extend_stroke(5, 3)
        window.finish_stroke(5, 3)
        self.assertEqual(window.studio.sample((4, 3)), "stone")
        self.assertEqual(window.studio.snapshot()["revision"], before["revision"]+1)
        ghosts = root.property("previewCells")
        ghosts = ghosts.toVariant() if hasattr(ghosts, "toVariant") else ghosts
        self.assertFalse(ghosts)
        self.assertEqual(window.renderer.scene["mission"], window.studio.mission_id)
        window.hide()

    def test_validated_drop_action_one_edit_and_unknown_mime_rejected(self):
        from PySide6.QtCore import QByteArray, QMimeData
        from drawtemp.studio.map_dragdrop import MapDropViewport
        from drawtemp.studio.map_editor import MapWindow

        class Drop:
            def __init__(self, raw):
                self.mime = QMimeData()
                self.mime.setData(MIME_BRUSH, QByteArray(raw))
            def mimeData(self):
                return self.mime

        self.assertEqual(MapDropViewport._brush(Drop(b"surface:water")), "surface:water")
        self.assertIsNone(MapDropViewport._brush(Drop(b"../../evil")))
        self.assertIsNone(MapDropViewport._brush(Drop(b"\xff")))
        window = MapWindow()
        self.addCleanup(window.deleteLater)
        window.studio.create("qt_drop", "Carte glisser", 12, 12)
        window.refresh_maps()
        rev = window.studio.snapshot()["revision"]
        window._drop_brush("surface:stone", 4, 4)
        self.assertEqual(window.studio.snapshot()["revision"], rev + 1)
        self.assertEqual(window.studio.sample((4, 4)), "stone")
        window.hide()


if __name__ == "__main__":
    unittest.main()

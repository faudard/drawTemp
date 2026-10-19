"""R27.A Qt Widgets+Quick integration: exercises the actual contextual dock.

Run under a Qt-capable display (or offscreen software backend); this is a
functional UI smoke test, not visual/golden or hardware GPU certification.
"""
from __future__ import annotations

import os
import unittest

from drawtemp.studio.map_authoring import MapStudio


@unittest.skipUnless(os.environ.get("DRAWTEMP_R27_QT_SMOKE") == "1",
                     "Requires explicit Qt GUI smoke environment")
class R27DungeonDockQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_room_lever_and_diagnostics_share_real_map_window(self):
        from drawtemp.studio.map_editor import MapWindow
        window = MapWindow(MapStudio.reference())
        try:
            window.studio.create("r27_gui", "Ruines GUI", 16, 16)
            window.refresh_maps()
            window.mode.setCurrentIndex(2)
            dock = window.dungeon
            self.assertEqual(dock.objectName(), "r27_dungeon_dock")
            self.assertFalse(dock.isHidden())
            dock.build_room()
            mission = window.studio.mission()
            self.assertEqual(
                next(o for o in mission["objects"]
                     if o["id"] == "room_door")["pos"], [7, 3])
            window.studio.paint([(6, 6)], "goal")
            window.refresh()
            dock.kind.setCurrentIndex(1)
            dock.link.setCurrentIndex(dock.link.findData("room_door"))
            dock.object_x.setValue(7)
            dock.object_y.setValue(2)
            dock.identifier.setText("lever_ui")
            dock.place_object()
            self.assertTrue(any(o["id"] == "lever_ui"
                                for o in window.studio.mission()["objects"]))
            dock.show_report()
            self.assertIn("Objectifs accessibles : 1",
                          dock.report.toPlainText())
            window.undo()
            self.assertFalse(any(o["id"] == "lever_ui"
                                 for o in window.studio.mission()["objects"]))
            window.redo()
            self.assertTrue(any(o["id"] == "lever_ui"
                                for o in window.studio.mission()["objects"]))
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

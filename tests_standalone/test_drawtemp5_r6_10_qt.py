"""R6.10 Qt Widgets smoke: author floor links and a real door without JSON."""
import unittest
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 unavailable")
class ConstructionGameplayQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_direct_construction_stairs_door_shared_scene(self):
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.studio.map_editor import MapWindow
        from drawtemp.core import Content
        from tests_standalone.test_drawtemp5_r6 import available_anchor

        studio = MapStudio.reference()
        content = Content.from_dict(studio.snapshot()["content"])
        anchor = available_anchor(content)
        window = MapWindow(studio)
        try:
            window.mode.setCurrentIndex(1)
            dock = window.construction
            dock.preset.setCurrentIndex(dock.preset.findData("Maison"))
            dock.x.setValue(anchor[0])
            dock.y.setValue(anchor[1])
            dock.place_button.click()
            entry = dock.workspace.inspect().entry
            self.assertIsNotNone(entry)
            dock.add_floor.click()
            dock.stair_x.setValue(entry[0])
            dock.stair_y.setValue(entry[1])
            dock.stair_from.setCurrentIndex(0)
            dock.make_stair.click()
            self.assertEqual(len(studio.mission()["level_links"]), 1)
            dock.gameplay_door.click()
            mission = studio.mission()
            self.assertEqual(sum(o["kind"] == "door" for o in mission["objects"]), 1)
            self.assertEqual(tuple(next(o["pos"] for o in mission["objects"]
                                        if o["kind"] == "door")), entry)
            self.assertIs(dock.workspace.authoring, studio.authoring)
            self.assertTrue(any(item["kind"] == "building"
                                for item in window.renderer.items))
            dock.undo.click()
            self.assertFalse(any(o["kind"] == "door" for o in studio.mission()["objects"]))
            dock.redo.click()
            self.assertTrue(any(o["kind"] == "door" for o in studio.mission()["objects"]))
        finally:
            with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
                window.close()


if __name__ == "__main__":
    unittest.main()

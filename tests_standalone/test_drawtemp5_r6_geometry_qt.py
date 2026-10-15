"""R6.2 real Qt/R5 construction viewport integration smoke."""
import unittest
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class ConstructionWindowR6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_one_qt_viewport_one_authoring_session_building_selection(self):
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.studio.map_editor import MapWindow
        from tests_standalone.test_drawtemp5_r6 import available_anchor
        from drawtemp.core import Content

        studio = MapStudio.reference()
        content = Content.from_dict(studio.snapshot()["content"])
        anchor = available_anchor(content)
        window = MapWindow(studio)
        try:
            self.assertIs(window.construction.workspace.authoring, studio.authoring)
            window.mode.setCurrentIndex(1)
            self.assertEqual(window.viewport.rootObject().property("interactionMode"),
                             "construction")
            dock = window.construction
            dock.preset.setCurrentIndex(dock.preset.findData("Maison"))
            dock.x.setValue(anchor[0])
            dock.y.setValue(anchor[1])
            dock.place_button.click()
            self.assertEqual(dock.workspace.inspect().name,"Maison")
            self.assertTrue(any(r["kind"]=="building" and r["part"]=="roof"
                                for r in window.renderer.items))
            roof = next(r for r in window.renderer.items
                        if r["kind"]=="building" and r["part"]=="roof")
            cx = sum(v[0] for v in roof["vertices"])/4
            cy = sum(v[1] for v in roof["vertices"])/4
            x,y = window.renderer.camera.screen(cx,cy)
            hit = window.renderer.buildingAt(x,y)
            self.assertEqual(hit["part"],"roof")
            window._on_building_pick(hit)
            self.assertEqual(dock.workspace.inspect().selected_part,"roof")
            dock.add_floor.click()
            dock.level.setCurrentIndex(dock.level.findData(1))
            self.assertFalse(any(r["part"]=="roof" for r in window.renderer.items
                                 if r["kind"]=="building"))
            self.assertTrue(any(r["part"]=="floor" for r in window.renderer.items
                                if r["kind"]=="building"))
            dock.cutaway.click()
            self.assertTrue(dock.workspace.cutaway)
            window.mode.setCurrentIndex(0)
            self.assertEqual(window.viewport.rootObject().property("interactionMode"),"edit")
        finally:
            from PySide6.QtWidgets import QMessageBox
            with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
                window.close()


if __name__ == "__main__":
    unittest.main()

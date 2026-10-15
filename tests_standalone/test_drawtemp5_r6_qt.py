"""R6 Qt Widget smoke: controls edit canonical authoring state without Tk."""
import unittest

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class ConstructionDockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dock_placement_material_and_floor_edit(self):
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.construction import ConstructionWorkspace
        from drawtemp.sdk.reference import MISSION, reference_project
        from drawtemp.studio.construction_dock import ConstructionDock
        from sporebound.iso_structures import structure_template, validate_structure_placement

        content, project = reference_project()
        data = content.to_dict()
        mission = data["missions"][0]
        clip = structure_template("Maison")
        anchor = None
        for y in range(mission["board"]["height"] - clip.height + 1):
            for x in range(mission["board"]["width"] - clip.width + 1):
                try:
                    validate_structure_placement(data, MISSION, clip, (x, y))
                    anchor = x, y
                    break
                except ValueError:
                    pass
            if anchor is not None:
                break
        self.assertIsNotNone(anchor)
        workspace = ConstructionWorkspace(AuthoringSession.new(content, project), MISSION)
        dock = ConstructionDock(workspace)
        self.assertEqual(dock.objectName(), "drawtemp5_construction_dock")
        dock.preset.setCurrentIndex(dock.preset.findData("Maison"))
        dock.x.setValue(anchor[0])
        dock.y.setValue(anchor[1])
        dock.place_button.click()
        self.assertEqual(workspace.inspect().name, "Maison")
        dock.facade.setCurrentText("torchis")
        dock.roof.setCurrentText("ardoise")
        dock.material_button.click()
        self.assertEqual(workspace.inspect().roof, "ardoise")
        dock.add_floor.click()
        self.assertEqual(workspace.inspect().levels, (1,))
        dock.level.setCurrentIndex(dock.level.findData(1))
        self.assertEqual(workspace.active_level, 1)
        dock.cutaway.click()
        self.assertTrue(workspace.cutaway)
        self.assertTrue(dock.undo.isEnabled())
        dock.close()


if __name__ == "__main__":
    unittest.main()

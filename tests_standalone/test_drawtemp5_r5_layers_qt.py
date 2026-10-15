"""R5.6 Qt viewport integration smoke for visibility, locks and active mission."""
import importlib.util
import unittest

QT_AVAILABLE = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(QT_AVAILABLE, "PySide6 Qt 6 is optional")
class MapLayersQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_layer_dock_modifies_qml_without_changing_canonical_map(self):
        from PySide6.QtCore import Qt
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.studio.map_editor import MapWindow
        from drawtemp.studio.map_layers import LAYERS

        studio = MapStudio.reference()
        window = MapWindow(studio)
        try:
            panel = window.layers_panel
            self.assertEqual(panel.tree.topLevelItemCount(), len(LAYERS))
            terrain = panel.tree.topLevelItem(LAYERS.index("Terrain"))
            self.assertEqual(terrain.checkState(1), Qt.Checked)
            baseline = studio.snapshot()
            terrain.setCheckState(1, Qt.Unchecked)
            self.assertFalse(studio.layers.view(studio.mission_id)["visible"]["Terrain"])
            qml = window.viewport.rootObject()
            self.assertFalse(qml.property("layerVisibility")["Terrain"])
            self.assertEqual(baseline, studio.snapshot())

            terrain.setCheckState(2, Qt.Checked)
            self.assertTrue(studio.layers.view(studio.mission_id)["locked"]["Terrain"])
            self.assertEqual(baseline, studio.snapshot())
            panel.level.setValue(2)
            self.assertEqual(studio.layers.view(studio.mission_id)["active_level"], 2)

            panel.tree.setCurrentItem(terrain)
            panel.opacity.setValue(55)
            self.assertEqual(studio.layers.view(studio.mission_id)["opacity"]["Terrain"], 55)
            self.assertEqual(qml.property("layerOpacity")["Terrain"], 55)
        finally:
            studio.layers.discard()
            window.close()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()

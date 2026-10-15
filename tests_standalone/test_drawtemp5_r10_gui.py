"""R10 real Qt Widgets interactions, offscreen but not a GPU golden."""
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAVE_QT = importlib.util.find_spec("PySide6") is not None

if HAVE_QT:
    from PySide6.QtWidgets import QApplication, QPushButton
    from drawtemp.studio.campaign_window import CampaignWindow
    from tests_standalone.test_drawtemp5_r10 import _three_missions
    from drawtemp.sdk.reference import MISSION


@unittest.skipUnless(HAVE_QT, "Optional PySide6 is not installed")
class CampaignQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = CampaignWindow(_three_missions())
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        # Hide without triggering the protective unsaved-document dialog.
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()

    def _click(self, text):
        matches = [b for b in self.window.findChildren(QPushButton)
                   if b.text() == text]
        self.assertEqual(len(matches), 1, "Missing or duplicate action: " + text)
        matches[0].click()
        self.app.processEvents()

    def test_link_and_world_through_widget_actions(self):
        gui = self.window
        gui.origin.setCurrentIndex(gui.origin.findData(MISSION))
        gui.destination.setCurrentIndex(gui.destination.findData("r10_forest"))
        self._click("Relier")
        self.assertEqual(gui.studio.overview()["graph"]["edges"],
                         [(MISSION, "r10_forest")])
        self.assertGreater(len(gui.graph_scene.items()), 0)
        self._click("Créer la carte")
        self.assertEqual(len(gui.studio.overview()["world"]["nodes"]), 3)
        gui.origin.setCurrentIndex(gui.origin.findData("r10_forest"))
        gui.world_x.setValue(360)
        gui.world_y.setValue(260)
        gui.region.setText("Bois")
        self._click("Positionner la mission sélectionnée")
        changed = next(row for row in gui.studio.overview()["world"]["nodes"]
                       if row["mission"] == "r10_forest")
        self.assertEqual(changed["region"], "Bois")
        self.assertEqual((changed["x"], changed["y"]), (360, 260))
        self._click("Annuler")
        self.assertNotEqual(next(row for row in gui.studio.overview()["world"]["nodes"]
                                 if row["mission"] == "r10_forest")["x"], 360)

    def test_typed_condition_and_campaign_simulation(self):
        gui = self.window
        gui.condition_target.setCurrentText("ending")
        gui.condition_id.setText("alliance")
        gui.condition_kind.setCurrentText("flag_eq")
        gui.condition_key.setText("allegiance")
        gui.condition_value.setText("aid")
        self._click("Appliquer la condition")
        self.assertIn("alliance", gui.studio.overview()["flow"]["endings"])
        self.assertGreater(gui.simulation_action.count(), 0)
        # The choice is made on the real existing StoryBook simulation,
        # not by writing the UI's displayed JSON.
        gui.simulation_action.setCurrentIndex(0)
        self._click("Appliquer l'hypothèse")
        self.assertTrue(gui.studio.simulation_inspect()["symbolic_only"])
        self.assertEqual(gui.studio.simulation_inspect()["node"], 1)


if __name__ == "__main__":
    unittest.main()

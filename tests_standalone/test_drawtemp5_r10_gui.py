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

    def test_create_linked_mission_and_story_without_json(self):
        gui = self.window
        gui.new_mission_id.setText("r10_new")
        gui.new_mission_name.setText("Mission de test")
        gui.new_after.setCurrentIndex(gui.new_after.findData(MISSION))
        self._click("Créer la mission et son lien")
        missions = gui.studio.overview()["missions"]
        self.assertEqual(len(missions), 4)
        self.assertIn((MISSION, "r10_new"), gui.studio.overview()["graph"]["edges"])
        self.assertEqual(gui.origin.currentData(), "r10_new")
        gui.mission_reward.setValue(15)
        self._click("Définir pour la mission sélectionnée")
        self.assertEqual(next(m["reward"] for m in gui.studio.overview()["missions"]
                              if m["id"] == "r10_new"), 15)

        gui.scene_id.setText("r10_scene")
        gui.scene_title.setText("Un choix")
        gui.scene_dialogue.setPlainText("Où aller ?")
        self._click("Créer une scène")
        self.assertEqual(gui.scene_select.currentData(), "r10_scene")
        self._click("Scène d'introduction")
        self.assertEqual(gui.studio.overview()["entry_scene"], "r10_scene")
        gui.choice_id.setText("help")
        gui.choice_label.setText("Aider")
        self._click("Ajouter le choix")
        self.assertEqual(gui.choice_select.currentData(), "help")
        gui.choice_effect_kind.setCurrentText("set_flag")
        gui.choice_effect_name.setText("allegiance")
        gui.choice_effect_value.setText("aid")
        self._click("Ajouter l'effet au choix sélectionné")
        scene = next(x for x in gui.studio.overview()["scenes"]
                     if x["id"] == "r10_scene")
        choice = next(x for x in scene["choices"] if x["id"] == "help")
        self.assertEqual(choice["effects"], [
            {"kind": "set_flag", "flag": "allegiance", "value": "aid"}])
        gui.origin.setCurrentIndex(gui.origin.findData("r10_new"))
        self._click("Après victoire de la mission")
        self.assertEqual(gui.studio.overview()["after_mission_scenes"]["r10_new"],
                         "r10_scene")

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

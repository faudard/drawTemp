"""R7.C: real Player equip/unequip uses Campaign inventory and verified save."""
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.character_outfits import outfit_from_progress
from drawtemp.core import Content
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.simulation import Simulation, SimulationError, thaw
from sporebound.game_session import GameSession


class R7EquipmentGameplayTests(unittest.TestCase):
    def setUp(self):
        content, self.project = reference_project()
        data = content.to_dict()
        data["equipment"]["r7_training_sword"] = {
            "name": "Épée d'entraînement", "slot": "weapon", "price": 20,
            "bonuses": {"weapon_power": 1},
        }
        data["equipment"]["r7_armor"] = {
            "name": "Armure de Jeanne", "slot": "armor", "price": 40,
            "bonuses": {"defense": 2},
        }
        self.content = Content.from_dict(data)
        self.project.validate(self.content)
        session = GameSession.new(self.content, self.project, "main", seed=17)
        session.choose_story_option("enter")
        session.progress.gold = 100
        session.progress.buy(self.content, "r7_training_sword")
        session.progress.buy(self.content, "r7_armor")
        self.sim = Simulation(session)

    def _outfit(self):
        return outfit_from_progress(self.sim.snapshot().progress,
                                    self.content.equipment,
                                    "jeanne",
                                    ("peasant", "apprentice", "armor", "wounded"))

    def test_purchase_equip_saves_and_unequip_inventory_restores(self):
        self.assertEqual(self._outfit(), "peasant")
        snapshot = self.sim.snapshot()
        self.sim.equip_hero("jeanne", "r7_training_sword",
                            expected_revision=snapshot.revision)
        self.assertEqual(self._outfit(), "apprentice")
        self.sim.equip_hero("jeanne", "r7_armor",
                            expected_revision=self.sim.snapshot().revision)
        self.assertEqual(self._outfit(), "armor")
        with tempfile.TemporaryDirectory() as folder:
            save = Path(folder) / "session.json"
            self.sim.save(save)
            loaded = Simulation.load(save, self.content, self.project)
            self.assertEqual(outfit_from_progress(
                loaded.snapshot().progress, self.content.equipment, "jeanne",
                ("peasant", "apprentice", "armor", "wounded")), "armor")
            hero = thaw(loaded.snapshot().progress)["heroes"]["jeanne"]
            self.assertEqual(hero["equipment"]["armor"], "r7_armor")
            self.assertEqual(hero["equipment"]["weapon"], "r7_training_sword")
            loaded.unequip_hero("jeanne", "armor",
                                expected_revision=loaded.snapshot().revision)
            self.assertEqual(outfit_from_progress(
                loaded.snapshot().progress, self.content.equipment, "jeanne",
                ("peasant", "apprentice", "armor", "wounded")), "apprentice")
            stock = thaw(loaded.snapshot().progress)["inventory"]
            self.assertEqual(stock["r7_armor"], 1)

    def test_reject_stale_unowned_unknown_or_battle_gear_changes_atomically(self):
        before = self.sim.snapshot().to_dict()
        for actor, item in (("ghost", "r7_armor"), ("jeanne", "missing_item")):
            with self.subTest(actor=actor, item=item):
                with self.assertRaises(SimulationError):
                    self.sim.equip_hero(actor, item,
                                        expected_revision=self.sim.snapshot().revision)
                self.assertEqual(self.sim.snapshot().to_dict(), before)
        with self.assertRaises(SimulationError):
            self.sim.unequip_hero("jeanne", "armor",
                                  expected_revision=self.sim.snapshot().revision)
        self.assertEqual(self.sim.snapshot().to_dict(), before)
        self.sim.equip_hero("jeanne", "r7_armor",
                            expected_revision=self.sim.snapshot().revision)
        after_equipping = self.sim.snapshot().to_dict()
        with self.assertRaises(SimulationError):
            self.sim.equip_hero("jeanne", "r7_armor",
                                expected_revision=self.sim.snapshot().revision)
        self.assertEqual(self.sim.snapshot().to_dict(), after_equipping)
        with self.assertRaises(SimulationError):
            self.sim.unequip_hero("jeanne", "armor",
                                  expected_revision=before["revision"])
        self.assertEqual(self.sim.snapshot().to_dict(), after_equipping)
        self.sim.start_mission(MISSION,
                               expected_revision=self.sim.snapshot().revision)
        in_battle = self.sim.snapshot().to_dict()
        with self.assertRaises(SimulationError):
            self.sim.unequip_hero("jeanne", "armor",
                                  expected_revision=self.sim.snapshot().revision)
        self.assertEqual(self.sim.snapshot().to_dict(), in_battle)


if __name__ == "__main__":
    unittest.main()

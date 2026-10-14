"""R12 standalone Player: canonical flow, saves and UI isolation (headless)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.player.qt_app import build_controller
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.simulation import SimulationError


class PlayerR12Tests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        content, project = reference_project()
        self.player = PlayerController(content, project, "main", self.temp.name)

    def test_reference_title_story_mission_save_and_reload_without_studio(self):
        self.assertEqual(self.player.state()["screen"], "title")
        self.assertEqual(self.player.new_game()["screen"], "dialogue")
        self.assertEqual(self.player.state()["choices"][0]["id"], "enter")
        self.player.choose("enter")
        self.assertEqual(self.player.state()["screen"], "campaign")
        self.assertIn(MISSION, self.player.state()["missions"])
        self.player.start_mission(MISSION)
        started = self.player.state()
        self.assertIn(started["screen"], ("battle", "result"))
        self.player.save(1)
        self.assertIn(1, self.player.slots())
        saved = Path(self.temp.name) / "slot_1.json"
        self.assertTrue(saved.is_file())
        before = saved.read_bytes()
        self.player.title()
        self.assertEqual(self.player.state()["screen"], "title")
        self.player.load(1)
        resumed = self.player.state()
        self.assertEqual(resumed["screen"], started["screen"])
        self.assertEqual(resumed["battle"], started["battle"])
        self.assertEqual(saved.read_bytes(), before)

    def test_invalid_action_or_slot_keeps_revision_and_existing_save(self):
        self.player.new_game()
        original = self.player.state()
        with self.assertRaises(ValueError):
            self.player.choose("invented")
        with self.assertRaises(ValueError):
            self.player.save(0)
        with self.assertRaises(ValueError):
            self.player.start_mission(MISSION)  # pending narrative
        self.assertEqual(original["revision"], self.player.state()["revision"])
        self.player.save(1)
        valid = (Path(self.temp.name) / "slot_1.json").read_bytes()
        with self.assertRaises(SimulationError):
            self.player.load(2)
        self.assertEqual(valid, (Path(self.temp.name) / "slot_1.json").read_bytes())
        self.assertEqual(self.player.state()["screen"], "dialogue")

    def test_exact_revision_guard_and_read_only_tactical_projection(self):
        self.player.new_game()
        self.player.choose("enter")
        self.player.start_mission(MISSION)
        state = self.player.state()
        self.assertNotIn("rng", state["battle"])
        self.assertNotIn("events", state["battle"])
        self.assertNotIn("rules", state["battle"])
        self.assertEqual(self.player.select_cell(-100, 1000)["selected"],
                         [0, state["battle"]["height"] - 1])
        with self.assertRaises(ValueError):
            self.player.command("teleport")
        self.assertEqual(self.player.state()["revision"], state["revision"])

    def test_jeanne_prologue_exploration_is_not_a_fake_scene(self):
        game = build_controller(save_dir=self.temp.name)
        self.assertEqual(game.state()["screen"], "title")
        stage = game.new_game()
        self.assertEqual(stage["screen"], "exploration")
        self.assertEqual(stage["exploration"]["position"], [1, 5])
        with self.assertRaises(ValueError):
            game.choose("ecouter")
        game.explore_move(1, 0)
        game.explore_interact("ble")
        after = game.state()
        point = next(p for p in after["exploration"]["interactions"]
                     if p["id"] == "ble")
        self.assertTrue(point["visited"])
        self.assertEqual(after["exploration"]["position"], [2, 5])
        self.assertEqual(after["revision"], 2)
        recording = game.session.recording()
        with self.assertRaises(SimulationError):
            game.explore_move(3, 0)
        self.assertEqual(recording, game.session.recording())
        game.save(1)
        copy = build_controller(save_dir=self.temp.name)
        self.assertEqual(copy.load(1)["exploration"], game.state()["exploration"])

    def test_explicit_backup_recovers_previous_verified_slot(self):
        self.player.new_game()
        self.player.save(1)
        self.player.choose("enter")
        self.player.save(1)
        original = Path(self.temp.name) / "slot_1.json"
        backup = original.with_suffix(".json.bak")
        self.assertTrue(backup.exists())
        original.write_text("invalid checkpoint", encoding="utf-8")
        self.player.restore_backup(1)
        self.assertEqual(original.read_bytes(), backup.read_bytes())
        self.assertEqual(self.player.state()["screen"], "dialogue")

    def test_ui_modules_are_optional_until_launch(self):
        import sys
        from drawtemp.player import controller, qt_app
        self.assertTrue(callable(qt_app.main))
        self.assertTrue(callable(controller.PlayerController))
        self.assertNotIn("PySide6.QtQuick", sys.modules)


if __name__ == "__main__":
    unittest.main()

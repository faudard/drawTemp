"""R63.B headless Player E2E: authored survival HUD, actions and save/reload."""
from copy import deepcopy
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.survival_authoring import (
    preview_survival_design, apply_survival_design)
from sporebound.survival import EXTENSION
from tests_standalone.test_r25_scene_router import scene_fixture
from tests_standalone.test_r63_survival import survival_spec


def fixture():
    content, project = scene_fixture()
    spec = survival_spec()
    # A complete, playable village loop begins without manually granting a tool.
    spec["nodes"][0].update(tool=None, wear=0, pos=[0, 0])
    spec["shelters"][0]["pos"] = [1, 1]
    authoring = AuthoringSession(content, project)
    preview = preview_survival_design(authoring, spec)
    apply_survival_design(authoring, preview)
    from sporebound.game_project import GameProject
    project = GameProject.from_dict(
        authoring.snapshot().to_dict()["project"], content)
    return content, project


class R63PlayerTests(unittest.TestCase):
    def test_legacy_player_hud_remains_absent(self):
        content, project = scene_fixture()
        with TemporaryDirectory() as directory:
            player = PlayerController(content, project, "main", directory)
            self.assertIsNone(player.new_game()["survival"])
            with self.assertRaises(ValueError):
                player.survival_gather("forest")

    def test_studio_player_craft_camp_replay_and_reload(self):
        content, project = fixture()
        with TemporaryDirectory() as directory:
            player = PlayerController(content, project, "main", directory)
            initial = player.new_game()
            self.assertTrue(initial["survival"]["enabled"])
            self.assertEqual(len(initial["survival"]["recipes"]), 2)
            self.assertEqual(initial["survival"]["nodes"][0]["pos"], [0, 0])
            self.assertEqual(initial["survival"]["shelters"][0]["pos"], [1, 1])
            self.assertFalse(initial["survival"]["recipes"][0]["available"])
            player.survival_gather("forest")
            player.survival_gather("rocks")
            player.survival_gather("berry_bush")
            before = deepcopy(player.state()["survival"])
            self.assertTrue(all(row["available"]
                                for row in before["recipes"]))
            player.survival_craft("make_camp")
            player.survival_craft("make_ration")
            quantities = {row["id"]: row["quantity"]
                          for row in player.state()["survival"]["inventory"]}
            self.assertEqual(quantities, {"camp": 1, "ration": 1})
            self.assertTrue(player.state()["survival"]["shelters"][0]["available"])
            hunger = player.state()["survival"]["needs"]["hunger"]
            player.survival_eat("ration")
            self.assertGreater(player.state()["survival"]["needs"]["hunger"], hunger)
            energy = player.state()["survival"]["needs"]["energy"]
            player.survival_rest("home")
            self.assertGreater(player.state()["survival"]["needs"]["energy"], energy)
            self.assertFalse(player.state()["survival"]["shelters"][0]["available"])
            player.save(1)
            saved = deepcopy(player.state()["survival"])
            player.load(1)
            self.assertEqual(player.state()["survival"], saved)
            before_receipt = deepcopy(player.state()["survival"])
            player.survival_craft("make_camp", "r63-player-3")
            self.assertEqual(player.state()["survival"]["inventory"],
                             before_receipt["inventory"])

    def test_invalid_commands_preserve_ui_snapshot_and_revision(self):
        content, project = fixture()
        with TemporaryDirectory() as directory:
            player = PlayerController(content, project, "main", directory)
            player.new_game()
            before = deepcopy(player.state()["survival"])
            revision = player.state()["revision"]
            with self.assertRaises(ValueError):
                player.survival_craft("make_camp")
            self.assertEqual(player.state()["survival"], before)
            self.assertEqual(player.state()["revision"], revision)
            player.survival_wait(1)
            self.assertEqual(player.state()["survival"]["tick"], 1)


if __name__ == "__main__":
    unittest.main()

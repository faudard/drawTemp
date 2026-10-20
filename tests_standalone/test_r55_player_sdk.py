"""R55.C Player facade: immutable SDK state, revision guards, resume and VS-55."""
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.simulation import Simulation, SimulationError, thaw
from examples.r55_micro_economy import build_example, run_demo


class R55PlayerFacadeTests(unittest.TestCase):
    def test_simulation_state_is_immutable_and_commands_are_revisioned(self):
        content, project = build_example()
        sdk = Simulation.new(content, project, "main", seed=55)
        state = sdk.system_state(expected_revision=0)
        self.assertEqual(state["tick"], 0)
        with self.assertRaises(TypeError):
            state["stocks"]["ore"] = 999
        self.assertEqual(sdk.system_state()["stocks"]["ore"], 8)
        forecast = sdk.system_preview(4, expected_revision=0)
        self.assertEqual(forecast["stocks"]["ingot"], 2)
        self.assertEqual(sdk.snapshot().revision, 0)
        sdk.system_advance(2, expected_revision=0)
        self.assertEqual(sdk.system_state()["tick"], 2)
        self.assertEqual(sdk.snapshot().revision, 1)
        with self.assertRaises(SimulationError) as failure:
            sdk.system_advance(1, expected_revision=0)
        self.assertEqual(failure.exception.code, "stale_revision")
        self.assertEqual(sdk.system_state()["tick"], 2)
        with self.assertRaises(SimulationError):
            sdk.system_trade("trader", "buy", 99, "failed", expected_revision=1)
        self.assertEqual(sdk.system_state()["stocks"]["ingot"], 1)
        self.assertEqual(sdk.snapshot().revision, 1)

    def test_player_controller_r55_actions_and_save_load(self):
        content, project = build_example()
        with TemporaryDirectory(prefix="r55-player-") as directory:
            player = PlayerController(content, project, "main", directory, seed=55)
            first = player.new_game()
            self.assertTrue(first["systems"]["enabled"])
            self.assertEqual(first["systems"]["tick"], 0)
            self.assertEqual(first["systems"]["stocks"]["ore"], 8)
            self.assertEqual(len(first["systems"]["merchants"]), 1)
            self.assertEqual(first["systems"]["quests"][0]["fulfilled"], False)
            # Explicit demo stipend (not created by the R55 economy).
            player.session._session.progress.gold = 100
            player.system_wait(4)
            self.assertEqual(player.state()["systems"]["stocks"]["ingot"], 2)
            player.system_trade("trader", "buy", 2, "player-buy")
            player.system_fulfill("delivery")
            view = player.state()
            self.assertEqual(view["systems"]["stocks"]["ingot"], 0)
            self.assertTrue(view["systems"]["quests"][0]["fulfilled"])
            self.assertEqual(view["systems"]["tick"], 4)
            player.save(1)
            player.load(1)
            loaded = player.state()
            self.assertEqual(loaded["systems"], view["systems"])
            player.system_trade("trader", "buy", 2, "player-buy")
            player.system_fulfill("delivery")
            self.assertEqual(player.state()["systems"], loaded["systems"])

    def test_full_two_region_slice_idempotency(self):
        result = run_demo()
        self.assertEqual(result["scenes"], ["arrival", "outpost", "arrival"])
        self.assertEqual(result["economy_ticks"], 4)
        self.assertEqual(result["gold"], 90)
        self.assertTrue(result["delivered_flag"])
        self.assertTrue(result["save_reload_equal"])
        self.assertTrue(result["duplicate_purchase_prevented"])
        self.assertTrue(result["duplicate_quest_prevented"])


if __name__ == "__main__":
    unittest.main()

"""R63.C gate: two-scene VS-63, deterministic balance and failure/recovery."""
from copy import deepcopy
import unittest

from examples.r63_survival_refuge import build_example, run_demo
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from sporebound.survival import SurvivalRuntime
from tests_standalone.test_r63_survival import survival_spec


class R63JourneyGateTests(unittest.TestCase):
    def test_full_two_scene_exhaustion_recovery_and_save_replay(self):
        result = run_demo(seed=63)
        self.assertEqual(result["slice"], "VS-63")
        self.assertEqual(result["route"], ["to_outpost", "return_camp"])
        self.assertEqual(set(result["recipes_used"]), {"build_camp", "cook_ration"})
        self.assertEqual(result["hazard"], "cold")
        self.assertEqual(result["exhaustion_phase"], "incapacitated")
        self.assertNotEqual(result["recovery_phase"], "incapacitated")
        self.assertEqual(result["inventory"], {})
        self.assertTrue(result["save_replay_equal"])
        self.assertTrue(result["no_duplicate_rewards"])
        self.assertEqual(result["remaining_stocks"], {
            "forest": 1, "quarry": 1, "bush": 2, "windfall": 1,
        })

    def test_multiseed_genre_is_independent_of_combat_rng(self):
        outcomes = []
        for seed in (1, 17, 63, 999):
            row = run_demo(seed=seed)
            self.assertEqual(row.pop("seed"), seed)
            outcomes.append(row)
        self.assertTrue(all(row == outcomes[0] for row in outcomes[1:]))

    def test_exhaustion_pauses_crafting_and_collecting_not_paid_recovery(self):
        document = survival_spec()
        document["needs"].update(energy=50, hunger=50, temperature=15,
                                 energy_drain=0, hunger_drain=0, cold_drain=0)
        survival = SurvivalRuntime(document, {"arrival"})
        from types import SimpleNamespace
        player = SimpleNamespace(inventory={
            "axe": 1, "wood": 1, "stone": 1, "camp": 1, "ration": 1,
        })
        self.assertEqual(survival.condition()["phase"], "warning")
        survival.gather(player, "arrival", "forest", "chill")
        self.assertEqual(survival.condition()["phase"], "incapacitated")
        before = (survival.snapshot(), deepcopy(player.inventory))
        with self.assertRaises(RuleError):
            survival.craft(player, "arrival", "make_camp", "blocked-craft")
        self.assertEqual((survival.snapshot(), player.inventory), before)
        self.assertTrue(survival.rest(player, "arrival", "home", "safe-rest"))
        self.assertEqual(survival.condition()["phase"], "stable")
        self.assertEqual(player.inventory["camp"], 0)
        self.assertFalse(survival.rest(player, "arrival", "home", "safe-rest"))
        with self.assertRaises(RuleError):
            survival.rest(player, "arrival", "home", "no-fuel")

    def test_crafting_rejects_duplication_and_inventory_forgery(self):
        content, project = build_example()
        game = GameSession.new(content, project, "main", seed=17)
        for node in ("forest", "quarry", "bush"):
            self.assertTrue(game.survival_gather(node, "g-" + node))
        self.assertTrue(game.survival_craft("build_camp", "craft-1"))
        self.assertFalse(game.survival_craft("build_camp", "craft-1"))
        prior = game.recording()
        with self.assertRaises(RuleError):
            game.survival_craft("build_camp", "craft-2")
        self.assertEqual(game.recording(), prior)
        with self.assertRaises(RuleError):
            game.survival_craft("cook_ration", "craft-1")
        self.assertEqual(game.recording(), prior)
        checkpoint = deepcopy(prior)
        checkpoint["survival"]["stock"]["forest"] = 2
        checkpoint["digest"] = digest({k: v for k, v in checkpoint.items()
                                       if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(checkpoint, content, project)

    def test_balance_report_is_deterministic_readonly_and_detects_risks(self):
        from sporebound.survival_balance import balance_survival
        document = survival_spec()
        original = deepcopy(document)
        report = balance_survival(document, {"arrival"}, horizon=128)
        self.assertEqual(document, original)
        self.assertIsNotNone(report["exhausted_tick"])
        self.assertGreater(report["exhausted_tick"], 0)
        self.assertEqual(report["issues"], [])
        self.assertEqual(len(report["cold_hazards"]), 1)
        self.assertEqual(report,
                         balance_survival(document, {"arrival"}, horizon=128))
        cut = deepcopy(document)
        cut["shelters"] = []
        cut["foods"] = []
        cut["nodes"][0]["cold"] = 0
        report = balance_survival(cut, {"arrival"}, horizon=128)
        self.assertEqual(set(report["issues"]), {
            "no_environmental_hazard", "no_shelter", "no_food"})
        for horizon in (0, True, 257):
            with self.assertRaises(RuleError):
                balance_survival(document, {"arrival"}, horizon=horizon)

    def test_long_fast_forward_matches_single_fixed_ticks(self):
        document = survival_spec()
        short = SurvivalRuntime(document, {"arrival"})
        long = SurvivalRuntime(document, {"arrival"})
        long.advance(200)
        for _ in range(200):
            short.advance(1)
        self.assertEqual(long.snapshot(), short.snapshot())
        self.assertEqual(long.condition(), short.condition())
        self.assertEqual(long.condition()["phase"], "incapacitated")


if __name__ == "__main__":
    unittest.main()

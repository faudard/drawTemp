"""R6.14 — real Battle legality, state isolation and tactical choice gates."""
from copy import deepcopy
import json
import unittest

from sporebound.engine import Battle
from sporebound.model import Board, Content, Mission, RuleError, Tile, Unit
from sporebound.tactical_choice_lab_r6 import (
    available_tactical_choices, compare_choice_reports,
    evaluate_choice_gate, run_choice_lab)


def arena():
    board = Board(8, 6)
    board.tiles[(1, 1)] = Tile(cover=50)
    units = [
        Unit("hero", "Hero", "player", (0, 0), speed=35,
             max_hp=48, hp=48, weapon="ranged", attack_range=3),
        Unit("ally", "Ally", "player", (0, 1), speed=5,
             max_hp=40, hp=20),
        Unit("enemy", "Enemy", "enemy", (2, 0), speed=5),
        Unit("guard", "Guard", "enemy", (6, 3), speed=5),
    ]
    return Content({}, {"arena": Mission("arena", "Arena", board, units)})


class TacticalChoiceR6Tests(unittest.TestCase):
    def test_probe_real_commands_without_mutating_battle(self):
        content = arena()
        battle = Battle(content, "arena", seed=7)
        self.assertEqual(battle.active.id, "hero")
        before_digest, before_recording = battle.digest(), battle.recording()
        result = available_tactical_choices(battle)
        self.assertTrue(result["sampled"])
        self.assertIn("positioning", result["categories"])
        self.assertIn("resources", result["categories"])
        self.assertIn("damage", result["categories"])
        self.assertLessEqual(result["probes_executed"], 30)
        self.assertEqual(battle.digest(), before_digest)
        self.assertEqual(battle.recording(), before_recording)
        for option in result["options"]:
            copy = deepcopy(battle)
            copy.execute(option["command"])
            self.assertEqual(copy.commands[-1], option["command"])

    def test_seed_replay_and_stable_choice_report(self):
        content = arena()
        original = content.to_dict()
        kwargs = dict(seed=3, max_commands=32, max_samples=8, sample_stride=1)
        first = run_choice_lab(content, "arena", **kwargs)
        second = run_choice_lab(content, "arena", **kwargs)
        self.assertEqual(first, second)
        self.assertTrue(first["replay_verified"])
        self.assertEqual(first["gate"]["status"], "pass")
        self.assertGreaterEqual(first["observed_player_commands"], 1)
        self.assertGreaterEqual(len(first["decisions"]), 1)
        self.assertIn("positioning", first["decisions"][0]["categories"])
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertEqual(content.to_dict(), original)

    def test_regression_gate_rejects_no_options_and_required_pairs(self):
        report = run_choice_lab(arena(), "arena", seed=1,
                                max_commands=10, sample_stride=1)
        self.assertTrue(evaluate_choice_gate(report, min_multi=1)["passed"])
        gate = evaluate_choice_gate(report,
                                    required_pairs=("positioning+damage",
                                                    "positioning+resources"))
        self.assertTrue(gate["passed"])
        impossible = deepcopy(report)
        impossible["decisions"] = []
        self.assertFalse(evaluate_choice_gate(impossible)["passed"])
        fake = deepcopy(report)
        fake["replay_verified"] = False
        with self.assertRaises(RuleError):
            evaluate_choice_gate(fake)
        with self.assertRaises(RuleError):
            evaluate_choice_gate(report, required_pairs=["positioning+magic"])
        with self.assertRaises(RuleError):
            run_choice_lab(arena(), "arena", max_samples=100)

    def test_paired_choice_comparison_and_disappearing_pairs(self):
        report = run_choice_lab(arena(), "arena", seed=2,
                                max_commands=15, sample_stride=1)
        self.assertTrue(compare_choice_reports(report, deepcopy(report))["passed"])
        changed = deepcopy(report)
        changed["decisions"] = []
        comparison = compare_choice_reports(report, changed)
        self.assertFalse(comparison["passed"])
        self.assertTrue(comparison["pairs_disappeared"])
        self.assertGreater(
            comparison["multi_category_rate_before"],
            comparison["multi_category_rate_after"])
        drift = deepcopy(report)
        drift["digest"] = "tampered"
        self.assertFalse(compare_choice_reports(report, drift)["passed"])
        scope = deepcopy(report)
        scope["seed"] += 1
        with self.assertRaises(RuleError):
            compare_choice_reports(report, scope)

    def test_runtime_design_limits_are_not_enforced(self):
        content = arena()
        report = run_choice_lab(content, "arena", seed=0,
                                max_commands=6, max_samples=1)
        self.assertNotIn("human_minutes", report)
        self.assertIn("ticks_ct", report)
        self.assertIsInstance(report["gate"]["passed"], bool)


if __name__ == "__main__":
    unittest.main()

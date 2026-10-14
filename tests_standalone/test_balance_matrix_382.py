"""3.8.2 Balance Matrix: paired scenario fairness, isolated variants and gates."""
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.balance_matrix import (compare_matrices, run_matrix,
                                       save_matrix, scenario_content)
from sporebound.model import Board, Content, Mission, RuleError, Unit


def arena():
    units = [
        Unit("hero", "Hero", "player", (0, 1), max_hp=55, hp=55),
        Unit("ally", "Ally", "player", (0, 2)),
        Unit("foe", "Foe", "enemy", (4, 1)),
        Unit("guard", "Guard", "enemy", (4, 2)),
    ]
    return Content({}, {
        "lab": Mission("lab", "Lab", Board(7, 5), deepcopy(units)),
        "second": Mission("second", "Second", Board(7, 5), deepcopy(units)),
    })


class BalanceMatrixTests(unittest.TestCase):
    def test_multi_mission_variants_are_isolated_seed_paired_and_repeatable(self):
        content = arena()
        authored = deepcopy(content.to_dict())
        cases = [
            {"id": "lab/tough", "mission": "lab",
             "team_deltas": {"enemy": {"max_hp": 6, "defense": 1}}},
            {"id": "lab/roster", "mission": "lab",
             "remove_units": ["guard"]},
            {"id": "second/weapon", "mission": "second",
             "unit_overrides": {"foe": {"weapon": "ranged",
                                        "attack_range": 3}}},
        ]
        first = run_matrix(content, cases, seeds=(2, 7), max_commands=25)
        second = run_matrix(content, cases, seeds=(2, 7), max_commands=25)
        self.assertEqual(first, second)
        self.assertEqual(content.to_dict(), authored)
        self.assertEqual(first["case_count"], 5)
        self.assertEqual(first["mission_count"], 2)
        self.assertTrue(first["all_replays_verified"])
        expected = {"lab::baseline", "second::baseline",
                    "lab/tough", "lab/roster", "second/weapon"}
        self.assertEqual({row["id"] for row in first["cases"]}, expected)
        for row in first["cases"]:
            self.assertEqual(row["report"]["seeds"], [2, 7])
            self.assertEqual(len(row["paired_seeds"]), 2)
            self.assertTrue(all(pair["seed"] in (2, 7)
                                for pair in row["paired_seeds"]))
            self.assertTrue(all(sample["replay_verified"]
                                for sample in row["report"]["samples"]))
        baseline = next(row for row in first["cases"]
                        if row["id"] == "lab::baseline")
        self.assertEqual(baseline["victory_delta"], 0)
        self.assertEqual(baseline["commands_p95_delta"], 0)
        self.assertTrue(compare_matrices(first, second)["passed"])

    def test_unit_and_team_modifiers_keep_source_untouched(self):
        content = arena()
        report = run_matrix(content, [
            {"id": "case", "mission": "lab",
             "team_deltas": {"player": {"max_hp": 7}},
             "unit_deltas": {"hero": {"attack": 2}},
             "unit_overrides": {"foe": {"weapon": "ranged",
                                        "attack_range": 3}}},
        ], seeds=[1], max_commands=12)
        case = report["cases"][-1]["spec"]
        clone = scenario_content(content, case)
        hero = next(x for x in clone.missions["lab"].units if x.id == "hero")
        self.assertEqual((hero.max_hp, hero.hp, hero.attack), (62, 62, 7))
        self.assertEqual(content.missions["lab"].units[0].max_hp, 55)
        self.assertEqual(content.missions["lab"].units[0].attack, 5)
        self.assertEqual(clone.missions["lab"].units[2].weapon, "ranged")
        self.assertEqual(content.missions["lab"].units[2].weapon, "melee")

    def test_regression_gate_detects_same_case_bad_outcomes_and_unpaired_sets(self):
        baseline = run_matrix(arena(), [{"id": "only", "mission": "lab"}],
                              seeds=[1, 5], max_commands=20)
        bad = deepcopy(baseline)
        bad["cases"][0]["report"]["commands_p95"] += 100
        bad["cases"][1]["report"]["outcomes"]["limit"] += 2
        bad["cases"][0]["report"]["samples"][0]["digest"] = "corrupt"
        comparison = compare_matrices(baseline, bad, max_p95_growth=0,
                                      max_new_limits=0)
        self.assertFalse(comparison["passed"])
        self.assertIn("lab::baseline", comparison["failures"])
        self.assertIn("only", comparison["failures"])
        self.assertEqual(comparison["checked_cases"], 2)
        mismatched = deepcopy(baseline)
        mismatched["cases"][1]["id"] = "renamed"
        with self.assertRaises(RuleError):
            compare_matrices(baseline, mismatched)

    def test_guard_invalid_scenarios_and_report_roundtrip(self):
        content = arena()
        cases = [{"id": "a", "mission": "lab",
                  "team_deltas": {"player": {"attack": 1}}}]
        original = run_matrix(content, cases, seeds=[0, 42],
                              max_commands=12)
        with TemporaryDirectory() as root:
            target = Path(root) / "matrix.json"
            save_matrix(target, original)
            loaded = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(loaded, original)
            self.assertTrue(compare_matrices(original, loaded)["passed"])
        broken = [
            [{"id": "a", "mission": "missing"}],
            [{"id": "same", "mission": "lab"},
             {"id": "same", "mission": "lab"}],
            [{"id": "a", "mission": "lab",
              "remove_units": ["hero", "ally"]}],
            [{"id": "a", "mission": "lab",
              "unit_deltas": {"ghost": {"attack": 1}}}],
            [{"id": "a", "mission": "lab",
              "team_deltas": {"player": {"hp": 2}}}],
            [{"id": "a", "mission": "lab",
              "team_deltas": {"player": {"attack": 101}}}],
            [{"id": "a", "mission": "lab", "ruleset": "missing"}],
            [{"id": "lab::baseline", "mission": "lab"}],
        ]
        for scenario in broken:
            with self.subTest(scenario=scenario), self.assertRaises(RuleError):
                run_matrix(content, scenario, seeds=[1], max_commands=10)
        with self.assertRaises(RuleError):
            run_matrix(content, cases, seeds=[3, 3], max_commands=12)


if __name__ == "__main__":
    unittest.main()

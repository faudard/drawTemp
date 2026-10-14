"""R6 encounter profiles, tactical evidence, human observations and campaign gates."""
from copy import deepcopy
import unittest

from sporebound.balance_matrix import run_matrix, scenario_content
from sporebound.campaign import Campaign
from sporebound.encounter_balance6 import (
    ai_decision_analytics, campaign_balance_curve, campaign_curve_review,
    encounter_profile, human_variant_breakdown, strict_regression_gate,
    trace_encounter_ai)
from sporebound.model import Board, Content, Mission, RuleError, Unit


def content_fixture():
    units = [
        Unit("h1", "Hero", "player", (0, 0), max_hp=55, hp=55),
        Unit("h2", "Ally", "player", (0, 1)),
        Unit("e1", "Enemy", "enemy", (6, 0)),
        Unit("e2", "Guard", "enemy", (6, 1)),
    ]
    first = Mission("first", "First", Board(9, 6), deepcopy(units),
                    next_missions=["second"])
    second = Mission("second", "Second", Board(9, 6), deepcopy(units))
    return Content({}, {"first": first, "second": second})


def human_session(seconds, result, *, mission="first", partial=False):
    return {
        "mission": mission, "outcome": result, "duration_seconds": seconds,
        "partial_capture": partial, "events": [], "truncated_events": 0,
        "command_kinds": {"act": 2}, "damage_observed": 3,
        "healing_observed": 0, "objective_hold_ticks": 5,
        "goal_occupied": True,
    }


class R6BalanceTests(unittest.TestCase):
    def test_profiles_are_observations_not_roster_generation(self):
        content = content_fixture()
        before = content.to_dict()
        profile = encounter_profile(content, "first")
        self.assertEqual((profile["player_count"], profile["enemy_count"]), (2, 2))
        self.assertFalse(profile["target_roster_met"])
        self.assertEqual(profile["target"]["human_minutes"], [15, 30])
        self.assertEqual(content.to_dict(), before)
        with self.assertRaises(RuleError):
            encounter_profile(content, "missing")

    def test_position_cloned_reinforcement_inventory_and_seed_replay(self):
        content = content_fixture()
        before = content.to_dict()
        proposed = {
            "id": "first/tuned", "mission": "first",
            "unit_positions": {"h1": [1, 0]},
            "clone_units": [{"id": "e3", "template_id": "e1", "pos": [7, 0]}],
            "unit_deltas": {"h2": {"attack": 2}},
            "unit_overrides": {"e2": {"weapon": "ranged",
                                      "attack_range": 3}},
            "inventory": {"potion": 4, "ether": 2, "phoenix": 1},
        }
        report = run_matrix(content, [proposed], seeds=[1], max_commands=16)
        tuned = next(r for r in report["cases"] if r["id"] == "first/tuned")
        self.assertTrue(tuned["report"]["samples"][0]["replay_verified"])
        self.assertEqual(tuned["report"]["samples"][0]["initial_inventory"],
                         proposed["inventory"])
        self.assertEqual(content.to_dict(), before)
        variant = scenario_content(content, tuned["spec"])
        self.assertEqual(len(variant.missions["first"].units), 5)
        self.assertEqual(next(u.pos for u in variant.missions["first"].units
                              if u.id == "h1"), (1, 0))
        self.assertEqual(next(u.pos for u in variant.missions["first"].units
                              if u.id == "e3"), (7, 0))
        self.assertEqual(run_matrix(content, [proposed], seeds=[1],
                                    max_commands=16), report)

    def test_tuning_rejects_collisions_wrong_rosters_and_untrusted_inventory(self):
        content = content_fixture()
        invalid = [
            {"unit_positions": {"h1": [0, 1]}},
            {"unit_positions": {"h1": [99, 1]}},
            {"clone_units": [{"id": "h1", "template_id": "e1",
                              "pos": [4, 4]}]},
            {"clone_units": [{"id": "e3", "template_id": "bad",
                              "pos": [4, 4]}]},
            {"inventory": {"potion": -1, "ether": 0, "phoenix": 0}},
            {"inventory": {"potion": 1}},
        ]
        for changed in invalid:
            with self.subTest(changed=changed), self.assertRaises(RuleError):
                run_matrix(content, [{"id": "invalid", "mission": "first",
                                      **changed}], seeds=[1], max_commands=8)

    def test_strict_matrix_gate_rejects_scope_drift_and_regressions(self):
        content = content_fixture()
        base = run_matrix(content, [{"id": "first/tuning", "mission": "first"}],
                          seeds=[1], max_commands=12)
        self.assertTrue(strict_regression_gate(base, deepcopy(base))["passed"])
        altered = deepcopy(base)
        altered["cases"][-1]["spec"]["team_deltas"]["enemy"] = {"attack": 1}
        gate = strict_regression_gate(base, altered)
        self.assertFalse(gate["passed"])
        self.assertIn("scenario changed", gate["incompatible_inputs"][0])
        bad = deepcopy(base)
        bad["cases"][0]["report"]["commands_p95"] += 100
        self.assertFalse(strict_regression_gate(
            base, bad, max_p95_growth=0)["passed"])
        mismatched = deepcopy(base)
        mismatched["seeds"] = [2]
        with self.assertRaises(RuleError):
            strict_regression_gate(base, mismatched)

    def test_ai_decisions_use_verified_steps_not_inferred_ai_optimality(self):
        trace = {
            "kind": "battle_diagnostics", "replay_verified": True,
            "mission": "first", "seed": 2, "digest": "fixture",
            "board": {"goals": [[2, 0]]},
            "initial": {"units": [{"id": "h1", "team": "player", "pos": [0, 0]}],
                        "hold_ticks": 0},
            "diagnostics": {"counts": {"repeat_idle": 1}},
            "steps": [
                {"index": 1, "actor": "h1", "team": "player",
                 "command": {"kind": "move"}, "events": [],
                 "after": {"units": [{"id": "h1", "team": "player",
                                      "pos": [1, 0], "alive": True}],
                           "hold_ticks": 0}},
                {"index": 2, "actor": "h1", "team": "player",
                 "command": {"kind": "move"}, "events": [
                     {"kind": "intercept"}],
                 "after": {"units": [{"id": "h1", "team": "player",
                                      "pos": [0, 0], "alive": True}],
                           "hold_ticks": 0}},
            ],
        }
        report = ai_decision_analytics(trace)
        self.assertEqual(report["signals"]["backtrack"], 1)
        self.assertEqual(report["signals"]["repeat_idle"], 1)
        self.assertEqual(report["protective_reactions"], 1)
        self.assertEqual(report["actions"], {"move": 2})
        with self.assertRaises(RuleError):
            ai_decision_analytics({**trace, "replay_verified": False})

    def test_canonical_trace_and_campaign_are_non_mutating(self):
        content = content_fixture()
        campaign = Campaign(unlocked=["first"])
        original_content, original_campaign = content.to_dict(), deepcopy(campaign)
        trace = trace_encounter_ai(content, "first", seed=1, max_commands=8)
        self.assertTrue(trace["analytics"]["replay_verified"])
        curve = campaign_balance_curve(content, campaign, ["first", "second"],
                                       seeds=[1, 2], max_commands=20)
        self.assertGreaterEqual(len(curve["rows"]), 1)
        self.assertTrue(curve["rows"][0]["replay_verified"])
        self.assertIsNone(curve["human_minutes"])
        self.assertEqual(content.to_dict(), original_content)
        self.assertEqual(campaign, original_campaign)
        self.assertIn("review_required", campaign_curve_review(curve))
        with self.assertRaises(RuleError):
            campaign_balance_curve(content, campaign, ["first", "first"],
                                   seeds=[1, 2])

    def test_human_variants_minimum_sample_and_separate_confusion(self):
        report = {
            "kind": "human_playtest", "schema": 1, "opt_in": True,
            "sessions": [human_session(20 * 60, "victory"),
                         human_session(26 * 60, "defeat"),
                         human_session(9 * 60, "abandoned"),
                         human_session(16 * 60, "victory")],
        }
        labels = [
            {"index": 0, "variant": "castle_a", "confusion": ["positioning"]},
            {"index": 1, "variant": "castle_a", "confusion": ["objective"]},
            {"index": 2, "variant": "castle_a", "exit_reason": "difficulty"},
            {"index": 3, "variant": "castle_a"},
        ]
        summary = human_variant_breakdown(report, labels, min_complete=3)
        row = summary["groups"][0]
        self.assertEqual(row["summary"]["complete_observations"], 3)
        self.assertEqual(row["summary"]["human_duration_minutes_p50"], 20)
        self.assertEqual(row["confusion"], {"objective": 1, "positioning": 1})
        self.assertEqual(row["exit_reasons"], {"difficulty": 1})
        self.assertTrue(row["duration_target_15_30_minutes"])
        insufficient = human_variant_breakdown(report, labels, min_complete=5)
        self.assertIsNone(insufficient["groups"][0]["duration_target_15_30_minutes"])
        with self.assertRaises(RuleError):
            human_variant_breakdown(report, [{"index": 0,
                                             "confusion": ["private_name"]}])


if __name__ == "__main__":
    unittest.main()

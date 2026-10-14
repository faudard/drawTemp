"""R6.15: canonical single-command outcomes, trade-offs and human sign-off."""
from copy import deepcopy
import json
import unittest

from sporebound.engine import Battle
from sporebound.model import RuleError
from sporebound.tactical_quality_r6 import (
    immediate_effect, measure_decision, run_quality_lab,
    evaluate_quality_gate, release_quality_review, _tradeoff)
from tests_standalone.test_tactical_choice_r6 import arena


def playtest(content_sha, count=5, *, seconds=1200, partial=False):
    return {
        "kind": "human_playtest", "schema": 1, "opt_in": True,
        "content_sha256": content_sha,
        "sessions": [
            {"mission": "arena", "outcome": "victory",
             "partial_capture": partial,
             "duration_seconds": seconds,
             "events": [], "truncated_events": 0,
             "command_kinds": {"act": 1},
             "damage_observed": 0, "healing_observed": 0,
             "objective_hold_ticks": 0, "goal_occupied": False}
            for _ in range(count)],
    }


def approval(**replacements):
    result = dict.fromkeys(
        ("positioning", "protection", "resources",
         "objectives", "player_comprehension"), True)
    result.update(replacements)
    return result


class TacticalQualityR615Tests(unittest.TestCase):
    def test_single_step_same_prestate_and_no_mutation(self):
        battle = Battle(arena(), "arena", seed=7)
        self.assertEqual(battle.active.id, "hero")
        before_digest = battle.digest()
        before_commands = deepcopy(battle.recording())
        attack = {"kind": "act", "skill": "attack", "cell": [1, 0]}
        potion = {"kind": "item", "item": "potion", "cell": [0, 1]}
        attack_effect = immediate_effect(battle, attack)
        potion_effect = immediate_effect(battle, potion)
        self.assertEqual(potion_effect["metrics"]["ally_hp_restored"], 20)
        self.assertEqual(potion_effect["metrics"]["consumables_spent"], 1)
        self.assertEqual(attack_effect["metrics"]["consumables_spent"], 0)
        self.assertEqual(battle.digest(), before_digest)
        self.assertEqual(battle.recording(), before_commands)
        with self.assertRaises(RuleError):
            immediate_effect(battle, {"kind": "interact",
                                      "object": "not_an_object"})
        self.assertEqual(battle.digest(), before_digest)

    def test_representative_options_distinct_and_credible(self):
        battle = Battle(arena(), "arena", seed=4)
        snapshot = battle.digest()
        measured = measure_decision(
            battle, {"kind": "item", "item": "potion", "cell": [0, 1]})
        categories = {opt["category"] for opt in measured["alternatives"]}
        self.assertIn("positioning", categories)
        self.assertIn("damage", categories)
        self.assertIn("resources", categories)
        self.assertTrue(measured["has_differentiation"])
        self.assertGreaterEqual(measured["distinct_immediate_footprints"], 2)
        self.assertEqual(measured["chosen_immediate"]["metrics"][
                         "consumables_spent"], 1)
        self.assertEqual(battle.digest(), snapshot)

    def test_tradeoffs_are_pareto_not_single_damage_score(self):
        one = {"enemy_hp_removed": 8, "cover_gain": 0,
               "consumables_spent": 0}
        two = {"enemy_hp_removed": 0, "cover_gain": 40,
               "consumables_spent": 0}
        # Construct complete effects so every shared feature is measured.
        zero = immediate_effect(
            Battle(arena(), "arena", seed=1),
            {"kind": "item", "item": "potion", "cell": [0, 1]})["metrics"]
        first = {**dict.fromkeys(zero, 0), **one}
        second = {**dict.fromkeys(zero, 0), **two}
        self.assertTrue(_tradeoff(first, second))
        self.assertFalse(_tradeoff(first, deepcopy(first)))
        best = {**dict.fromkeys(zero, 0), "enemy_hp_removed": 9,
                "cover_gain": 40}
        self.assertFalse(_tradeoff(best, second))

    def test_real_simulation_repeatable_and_json_roundtrip(self):
        content = arena()
        original = content.to_dict()
        options = dict(seed=3, max_commands=24,
                       max_samples=3, sample_stride=1)
        first = run_quality_lab(content, "arena", **options)
        self.assertEqual(first, run_quality_lab(content, "arena", **options))
        self.assertEqual(content.to_dict(), original)
        self.assertTrue(first["replay_verified"])
        self.assertGreaterEqual(len(first["decisions"]), 1)
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertTrue(evaluate_quality_gate(
            first, min_decisions=1, min_differentiated=1,
            min_tradeoffs=0)["passed"])
        self.assertFalse(evaluate_quality_gate(
            first, min_tradeoffs=100)["passed"])

    def test_release_gate_requires_real_duration_and_human_attestation(self):
        report = run_quality_lab(
            arena(), "arena", max_commands=8,
            max_samples=1, sample_stride=1)
        pending = release_quality_review(report, min_tradeoffs=0)
        self.assertFalse(pending["passed"])
        self.assertIn("Missing opt-in human playtest report", pending["issues"])
        evidence = playtest(report["content_sha256"])
        self.assertFalse(release_quality_review(
            report, evidence, min_tradeoffs=0)["passed"])
        accepted = release_quality_review(
            report, evidence, human_signoff=approval(), min_tradeoffs=0)
        self.assertTrue(accepted["passed"], accepted["issues"])
        self.assertEqual(accepted["human"]["summary"][
                         "human_duration_minutes_p50"], 20)
        mismatch = playtest("incorrect")
        self.assertFalse(release_quality_review(
            report, mismatch, human_signoff=approval(),
            min_tradeoffs=0)["passed"])
        short = playtest(report["content_sha256"], count=2)
        self.assertFalse(release_quality_review(
            report, short, human_signoff=approval(),
            min_tradeoffs=0)["passed"])
        too_short = playtest(report["content_sha256"], seconds=300)
        self.assertFalse(release_quality_review(
            report, too_short, human_signoff=approval(),
            min_tradeoffs=0)["passed"])
        partial = playtest(report["content_sha256"], partial=True)
        self.assertFalse(release_quality_review(
            report, partial, human_signoff=approval(),
            min_tradeoffs=0)["passed"])
        self.assertFalse(release_quality_review(
            report, evidence,
            human_signoff=approval(protection=False),
            min_tradeoffs=0)["passed"])
        with self.assertRaises(RuleError):
            release_quality_review(report, evidence,
                                   human_signoff={"positioning": True})


if __name__ == "__main__":
    unittest.main()

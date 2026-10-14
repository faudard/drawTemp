"""R6.16: full canonical activation policies, sequencing and reproducibility."""
from copy import deepcopy
import json
import unittest

from sporebound.engine import Battle
from sporebound.model import RuleError
from sporebound.full_activation_r616 import (
    execute_activation, evaluate_activation_state,
    evaluate_activation_gate, run_activation_lab, _dominance)
from tests_standalone.test_tactical_choice_r6 import arena


class FullActivationR616Tests(unittest.TestCase):
    def test_move_act_end_and_act_move_end_same_prestate(self):
        battle = Battle(arena(), "arena", seed=7)
        self.assertEqual(battle.active.id, "hero")
        opening = battle.digest()
        commands = deepcopy(battle.recording())
        move = {"kind": "move", "cell": [1, 1]}
        shot = {"kind": "act", "skill": "attack", "cell": [2, 0]}
        facing = {"kind": "end", "facing": [0, 1]}
        first = execute_activation(battle, [move, shot, facing])
        inverse = execute_activation(battle, [shot, move, facing])
        self.assertEqual([c["kind"] for c in first["commands"]],
                         ["move", "act", "end"])
        self.assertEqual([c["kind"] for c in inverse["commands"]],
                         ["act", "move", "end"])
        self.assertEqual(first["ct_end_cost"], 100)
        self.assertEqual(inverse["ct_end_cost"], 100)
        self.assertTrue(first["end_committed"])
        self.assertTrue(inverse["end_committed"])
        self.assertEqual(first["actor_position"], [1, 1])
        self.assertEqual(battle.digest(), opening)
        self.assertEqual(battle.recording(), commands)

    def test_half_turn_and_full_turn_ct_cost_are_not_confused(self):
        battle = Battle(arena(), "arena", seed=9)
        movement = execute_activation(battle, [
            {"kind": "move", "cell": [1, 1]},
            {"kind": "end", "facing": [0, 1]}])
        mixed = execute_activation(battle, [
            {"kind": "move", "cell": [1, 1]},
            {"kind": "act", "skill": "attack", "cell": [2, 0]},
            {"kind": "end", "facing": [0, 1]}])
        self.assertEqual(movement["ct_end_cost"], 80)
        self.assertEqual(mixed["ct_end_cost"], 100)
        self.assertEqual(movement["metrics"]["consumables_spent"], 0)
        self.assertEqual(len(mixed["commands"]), 3)

    def test_plan_enumeration_contains_both_sequences_and_ai_reference(self):
        battle = Battle(arena(), "arena", seed=4)
        digest = battle.digest()
        detail = evaluate_activation_state(battle)
        self.assertLessEqual(detail["plan_count"], 12)
        self.assertEqual(detail["plans"][0]["label"], "AI reference activation")
        self.assertTrue(detail["plans"][0]["reference"])
        self.assertTrue(any(
            [c["kind"] for c in p["commands"]] == ["move", "act", "end"]
            for p in detail["plans"]))
        self.assertTrue(any(
            [c["kind"] for c in p["commands"]] == ["act", "move", "end"]
            for p in detail["plans"]))
        self.assertTrue(detail["has_distinct_full_activations"])
        self.assertGreaterEqual(detail["non_dominated_pairs"], 0)
        self.assertEqual(battle.digest(), digest)

    def test_invalid_or_incomplete_activation_cannot_be_evidence(self):
        battle = Battle(arena(), "arena", seed=2)
        digest = battle.digest()
        with self.assertRaises(RuleError):
            execute_activation(battle, [
                {"kind": "move", "cell": [1, 1]}])
        with self.assertRaises(RuleError):
            execute_activation(battle, [
                {"kind": "act", "skill": "attack", "cell": [99, 99]},
                {"kind": "end", "facing": [0, 1]}])
        with self.assertRaises(RuleError):
            execute_activation(battle, [], ai_continuation=False)
        with self.assertRaises(RuleError):
            execute_activation(battle, [
                {"kind": "end", "facing": [0, 1]}],
                ai_continuation=True)
        self.assertEqual(battle.digest(), digest)

    def test_pareto_frontier_handles_ct_and_terminal_separately(self):
        battle = Battle(arena(), "arena", seed=5)
        passing = execute_activation(battle, [
            {"kind": "end", "facing": [0, 1]}])
        use_move = execute_activation(battle, [
            {"kind": "move", "cell": [1, 1]},
            {"kind": "end", "facing": [0, 1]}])
        self.assertEqual(passing["ct_end_cost"], 60)
        self.assertEqual(use_move["ct_end_cost"], 80)
        self.assertFalse(_dominance(use_move, passing))
        terminal = {**passing, "ct_end_cost": None}
        self.assertFalse(_dominance(terminal, passing))
        self.assertFalse(_dominance(passing, terminal))

    def test_lab_is_reproducible_and_fails_closed_without_samples(self):
        content = arena()
        original = content.to_dict()
        kwargs = dict(seed=1, max_commands=15,
                      max_samples=2, sample_stride=1)
        first = run_activation_lab(content, "arena", **kwargs)
        second = run_activation_lab(content, "arena", **kwargs)
        self.assertEqual(first, second)
        self.assertTrue(first["replay_verified"])
        self.assertEqual(content.to_dict(), original)
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertTrue(evaluate_activation_gate(
            first, min_distinct=1, min_non_dominated=0)["passed"])
        empty = deepcopy(first)
        empty["decisions"] = []
        self.assertFalse(evaluate_activation_gate(empty)["passed"])
        fake = deepcopy(first)
        fake["replay_verified"] = False
        with self.assertRaises(RuleError):
            evaluate_activation_gate(fake)
        with self.assertRaises(RuleError):
            run_activation_lab(arena(), "arena", max_samples=100)
        self.assertNotIn("human_minutes", first)


if __name__ == "__main__":
    unittest.main()

"""R7.8 guidance is a pure projection, not another combat validator."""
from dataclasses import replace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.model import Content
from sporebound.presentation import battle_frame
from sporebound.player_guidance import combat_guidance


class PlayerGuidanceR7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)

    def setUp(self):
        self.battle = Battle(self.content, "garden", seed=19)
        self.frame = battle_frame(self.battle, (1, 1))

    def player_frame(self):
        hero = next(actor for actor in self.frame.actors
                    if actor.team == "player" and actor.alive)
        return replace(self.frame, deploying=False, active_id=hero.id,
                       reachable=((2, 2),), forecast=(
                           {"kind": "attack", "amount": 4, "chance": .7},))

    def test_deployment_help_never_changes_battle(self):
        digest = self.battle.digest()
        deploying = replace(self.frame, deploying=True, active_id=None)
        result = combat_guidance(deploying, "deploy")
        self.assertEqual(result.phase, "deployment")
        self.assertIn("deploy", result.instruction)
        self.assertEqual(result, combat_guidance(deploying, "deploy"))
        self.assertEqual(self.battle.digest(), digest)

    def test_results_enemy_and_idle_have_distinct_instructions(self):
        frame = self.player_frame()
        enemy = next(actor for actor in frame.actors if actor.team == "enemy")
        self.assertEqual(combat_guidance(
            replace(frame, active_id=enemy.id), "move").phase, "enemy")
        self.assertEqual(combat_guidance(
            replace(frame, active_id=None), "move").phase, "waiting")
        self.assertEqual(combat_guidance(
            replace(frame, result="victory"), "move").phase, "results")

    def test_movement_warning_truth_labels_and_no_hypothetical_forecast(self):
        frame = replace(self.player_frame(), forecast=(), selected=(2, 2),
                        danger=(
                            {"kind": "hazard", "cell": [2, 2]},
                            {"kind": "prepared", "cell": [2, 2]},
                            {"kind": "charge", "cell": [2, 2]},
                            {"kind": "charge", "cell": [2, 2]},
                            {"kind": "cast", "cell": [5, 5]},
                        ))
        result = combat_guidance(frame, "move")
        self.assertEqual(result.phase, "player")
        self.assertTrue(any("atteignable" in row for row in result.notes))
        self.assertTrue(any("Terrain dangereux" in row for row in result.notes))
        self.assertTrue(any("armée" in row for row in result.notes))
        self.assertTrue(any("possible" in row for row in result.notes))
        self.assertEqual(sum("possible" in row for row in result.notes), 1)
        self.assertFalse(any("Incantation" in row for row in result.notes))
        self.assertFalse(any("Prévision disponible" in row for row in result.notes))

    def test_help_never_approves_attacks_without_engine_forecast(self):
        frame = replace(self.player_frame(), forecast=())
        result = combat_guidance(frame, "attack", (2, 2))
        self.assertTrue(any("Aucune prévision certifiée" in row
                            for row in result.notes))
        self.assertIn("validées par le moteur", result.instruction)
        self.assertEqual(combat_guidance(
            replace(frame, forecast=({"kind": "attack", "amount": 2},)),
            "attack", (2, 2)).phase, "player")
        with self.assertRaises(ValueError):
            combat_guidance(frame, "attack", (frame.width, 0))

    def test_action_families_explain_constraints_not_results(self):
        frame = self.player_frame()
        for action in ("level_move", "level_attack", "item:potion",
                       "object:gate", "formation:shield_wall",
                       "prepare:hold", "charge", "disengage", "fireball",
                       "end", ""):
            hint = combat_guidance(frame, action)
            self.assertEqual(hint.phase, "player")
            self.assertTrue(hint.instruction)
            self.assertTrue(hint.notes)


if __name__ == "__main__":
    unittest.main()

"""Jeanne gameplay gates: non-elimination, role telegraphs and dialogue supplies."""
from pathlib import Path
import unittest

from sporebound.ai import choose_command
from sporebound.engine import Battle
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Board, Content, Mission, Unit, distance
from sporebound.presentation import battle_frame
from sporebound.tactical_intents import tactical_intents
from sporebound.tactical_rpg3 import authored_rules_for_document, tactical_rpg_rules


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound/content/jeanne.json"
PROJECT = ROOT / "sporebound/content/jeanne.game.json"


class JeanneGameplayFinishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT)
        cls.project = GameProject.load(PROJECT, cls.content)

    def test_act_i_has_two_distinct_non_elimination_objectives(self):
        route = self.content.missions["a1_01_route"]
        bridge = self.content.missions["a1_02_pont"]
        self.assertEqual(route.objective, "extract")
        self.assertTrue(route.goal)
        self.assertEqual(bridge.objective, "hold")
        self.assertEqual(bridge.target_ticks, 35)
        self.assertEqual(
            {u.id for u in bridge.units if u.team == "enemy"},
            {"lancier_pont", "arbaletrier_pont"})
        self.assertIn("formation", authored_rules_for_document(
            self.content.to_dict()).commands)

    def test_bridge_enemy_role_and_objective_are_visible_without_mutation(self):
        rules = authored_rules_for_document(self.content.to_dict())
        battle = Battle(self.content, "a1_02_pont", seed=23, rules=rules)
        original = battle.digest()
        intents = tactical_intents(battle)
        squads = {row["unit"]: row for row in intents["squads"]}
        self.assertEqual(squads["lancier_pont"]["role"], "vanguard")
        self.assertEqual(squads["arbaletrier_pont"]["role"], "archer")
        self.assertEqual(squads["lancier_pont"]["intent"], "contest_goal")
        self.assertEqual(squads["lancier_pont"]["certainty"], "possible")
        self.assertEqual(squads["lancier_pont"]["goal_cells"], [[3, 3], [3, 4]])
        frame = battle_frame(battle)
        self.assertEqual(len(frame.squads), 2)
        self.assertEqual(battle.digest(), original)

    def test_coordinated_defender_moves_toward_real_goal_and_replays(self):
        enemy = Unit("guard", "Guard", "enemy", (6, 4),
                     tags=["squad:vanguard"], behavior="coordinated", ct=100)
        hero = Unit("jeanne", "Jeanne", "player", (0, 0), ct=0)
        goals = [(0, 4)]
        content = Content({}, {"guard": Mission(
            "guard", "Guard an extraction", Board(8, 6), [enemy, hero],
            objective="extract", goal=goals)})
        rules = tactical_rpg_rules()
        battle = Battle(content, "guard", seed=5, rules=rules)
        self.assertEqual(battle.active_id, "guard")
        before = battle.digest()
        command = choose_command(battle)
        self.assertEqual(command["kind"], "move")
        self.assertLess(min(distance(command["cell"], cell) for cell in goals),
                        min(distance(enemy.pos, cell) for cell in goals))
        self.assertEqual(before, battle.digest())
        battle.execute(command)
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())

    def test_dialogue_choices_affect_real_bridge_supplies(self):
        supplies = {}
        for choice in ("tenir_passage", "contourner"):
            session = GameSession.new(self.content, self.project, "jeanne", seed=11)
            session.progress.completed = [
                "p0_01_lame", "p0_02_incendie",
                "p0_03a_secours", "p0_04_fuite", "a1_01_route"]
            session.progress.story_pending = "sc_a1_pont"
            session.choose_story_option(choice)
            self.assertEqual(session.available_missions(), ["a1_02_pont"])
            supplies[choice] = session.start_mission(
                "a1_02_pont").inventory["player"]["potion"]
        self.assertEqual(supplies["tenir_passage"],
                         supplies["contourner"] + 1)


if __name__ == "__main__":
    unittest.main()

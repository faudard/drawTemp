"""R6.6: elite boss terrain choices, phase waves and conditional telegraphs."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.ai import choose_command
from sporebound.class_ai_authoring import ai_preview, set_unit_ai
from sporebound.editor import Document
from sporebound.bosses3 import boss_intent_preview
from sporebound.elite_boss_r6 import boss_r6_telegraph
from sporebound.engine import Battle
from sporebound.game_project import GameProject
from sporebound.model import Board, Content, Mission, RuleError, Tile, Unit, distance
from sporebound.player_session import PlayerSession
from sporebound.rules import default_rules
from sporebound.tactical_r6 import tactical_r6_rules
from sporebound.tactical_rpg3 import tactical_rpg_rules, authored_rules_for_document
from sporebound.tactical_ui import tactical_snapshot


def encounter(*, hero=(6, 3), boss=(1, 1), footprint=(2, 2),
              phase=2, tiles=None, triggers=None, move=4):
    player = Unit("hero", "Hero", "player", hero, speed=10)
    warden = Unit("warden", "Warden", "enemy", boss, footprint=footprint,
                  hp=90, max_hp=90, speed=20, move=move, attack=10,
                  behavior="adaptive_boss", tags=[f"boss_phase:{phase}"])
    board = Board(9, 7, tiles or {})
    mission = Mission("throne", "Throne", board, [player, warden],
                      triggers=triggers or [])
    return Content({}, {"throne": mission})


class EliteBossR6Tests(unittest.TestCase):
    def test_opt_in_registry_and_player_selection_preserve_legacy(self):
        content = encounter()
        data = content.to_dict()
        default_manifest = default_rules().manifest()
        tactical_manifest = tactical_rpg_rules().manifest()
        self.assertNotIn("adaptive_boss", default_rules().behaviors)
        self.assertNotIn("adaptive_boss", tactical_rpg_rules().behaviors)
        self.assertIn("adaptive_boss", tactical_r6_rules().behaviors)
        self.assertEqual(default_rules().manifest(), default_manifest)
        self.assertEqual(tactical_rpg_rules().manifest(), tactical_manifest)
        with self.assertRaises(RuleError):
            Battle(content, "throne")
        self.assertIn("adaptive_boss",
                      authored_rules_for_document(data).behaviors)
        with TemporaryDirectory() as temp:
            player = PlayerSession(content, GameProject.default(content),
                                   Path(temp) / "profile.json")
            player.new_game("main", 1)
            battle = player.begin("throne")
            self.assertIn("adaptive_boss", battle.rules.behaviors)

    def test_multicell_boss_repositions_around_a_dangerous_tile(self):
        content = encounter(tiles={(3, 1): Tile(hazard=1000)})
        rules = tactical_r6_rules()
        battle = Battle(content, "throne", rules=rules, seed=31)
        battle.active_id = "warden"
        battle.unit("warden").ct = 100
        before = battle.digest()
        boss = battle.unit("warden")
        original = min(distance(p, battle.unit("hero").pos)
                       for p in boss.occupied_cells())
        chosen = choose_command(battle)
        self.assertEqual(chosen["kind"], "move")
        destination = tuple(chosen["cell"])
        self.assertIn(destination, battle.reachable(boss))
        self.assertFalse(any(battle.board.tile(cell).blocked or
                             battle.board.tile(cell).hazard
                             for cell in boss.occupied_cells(destination)))
        self.assertLess(min(distance(p, battle.unit("hero").pos)
                            for p in boss.occupied_cells(destination)), original)
        self.assertEqual(before, battle.digest())
        battle.execute(chosen)
        self.assertEqual(battle.unit("warden").pos, destination)
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())

    def test_charging_boss_shows_actual_corridor_and_replay(self):
        content = encounter(hero=(6, 2), boss=(1, 2), footprint=(1, 1))
        rules = tactical_r6_rules()
        battle = Battle(content, "throne", rules=rules, seed=12)
        battle.active_id = "warden"
        battle.unit("warden").ct = 100
        before = battle.digest()
        command = choose_command(battle)
        self.assertEqual(command, {"kind": "charge", "cell": [6, 2]})
        preview = boss_r6_telegraph(battle, "warden")
        self.assertEqual(preview["command"], command)
        self.assertEqual(preview["certainty"], "conditional")
        self.assertEqual(preview["threat_cells"], [[6, 2]])
        self.assertTrue(preview["path"])
        self.assertTrue(preview["destination_cells"])
        self.assertEqual(tactical_snapshot(battle)["bosses"][0], preview)
        self.assertEqual(battle.digest(), before)
        battle.execute(command)
        self.assertTrue(any(row["kind"] == "charge" for row in battle.events))
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())

    def test_pending_hp_phase_waves_are_possible_and_not_guessed(self):
        actions = [
            {"kind": "boss_phase", "unit": "warden", "phase": 3,
             "footprint": [2, 2], "bonuses": {"defense": 2}},
            {"kind": "queue_wave", "actors": [
                {"id": "reserve", "name": "Reserve", "team": "enemy",
                 "pos": [8, 6]}]},
        ]
        content = encounter(triggers=[{
            "id": "reinforce", "condition": "hp_below",
            "unit": "warden", "percent": 60, "actions": actions}])
        battle = Battle(content, "throne", rules=tactical_r6_rules(), seed=3)
        battle.active_id = "hero"
        before = battle.digest()
        view = boss_r6_telegraph(battle, "warden")
        self.assertFalse(view["ready"])
        self.assertIsNone(view["command"])
        self.assertEqual(view["certainty"], "unknown")
        self.assertEqual(view["reinforcements"], [
            {"trigger": "reinforce", "percent": 60,
             "kind": "queue_wave", "count": 1, "certainty": "possible"}])
        self.assertEqual(view["queued_waves"], [])
        self.assertEqual(view["occupied_cells"],
                         [[1, 1], [1, 2], [2, 1], [2, 2]])
        self.assertEqual(before, battle.digest())

        battle.encounter.queue([{"id": "queued", "name": "Queued",
                                  "team": "enemy", "pos": [7, 5]}])
        queued = boss_r6_telegraph(battle, "warden")
        self.assertEqual(queued["queued_waves"][0]["certainty"], "queued")
        self.assertIsNone(queued["command"])

    def test_studio_can_author_adaptive_boss_and_undo_without_json_schema_change(self):
        content = encounter()
        content.missions["throne"].units[1].behavior = "tactical"
        doc = Document(content)
        before = deepcopy(doc.data)
        updated = set_unit_ai(doc.data, "throne", "warden",
                              behavior="adaptive_boss")
        self.assertEqual(updated["version"], 1)
        self.assertEqual(ai_preview(updated, "throne", "warden")["ruleset"], "r6")
        doc.replace(updated)
        self.assertEqual(doc.data["missions"][0]["units"][1]["behavior"],
                         "adaptive_boss")
        self.assertIn("adaptive_boss",
                      authored_rules_for_document(doc.data).behaviors)
        doc.undo()
        self.assertEqual(doc.data, before)
        doc.redo()
        self.assertEqual(doc.data, updated)
        with self.assertRaises(RuleError):
            set_unit_ai(before, "throne", "warden",
                        behavior="adaptive_boss", route=[(1, 1), (1, 2)])
        with self.assertRaises(RuleError):
            set_unit_ai(before, "throne", "hero",
                        behavior="adaptive_boss")
        self.assertEqual(content.to_dict(), before)

    def test_phase_one_retains_legacy_guard_and_not_premature_charge(self):
        content = encounter(hero=(3, 1), boss=(1, 1),
                            footprint=(1, 1), phase=1)
        battle = Battle(content, "throne", rules=tactical_r6_rules())
        battle.active_id = "warden"
        battle.unit("warden").ct = 100
        before = battle.digest()
        self.assertEqual(choose_command(battle),
                         boss_intent_preview_legacy_command(battle))
        self.assertEqual(battle.digest(), before)


def boss_intent_preview_legacy_command(battle):
    from sporebound.bosses3 import phase_boss_command
    return phase_boss_command(battle)


if __name__ == "__main__":
    unittest.main()

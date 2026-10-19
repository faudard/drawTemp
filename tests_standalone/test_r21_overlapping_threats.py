"""R21.1 regression: overlapping telegraphs must never hide independent units.

All checks use the canonical Battle, without modifying its executor or rules
manifest. Threat certainty is inherited from the real prepared/cast/charge state.
"""
import json
import unittest

from sporebound.engine import Battle
from sporebound.model import Board, Content, Effect, Mission, Skill, Unit
from sporebound.player_ux import combat_hud
from sporebound.presentation import battle_frame
from sporebound.tactical_intents import tactical_intents
from sporebound.tactical_rpg3 import tactical_rpg_rules


def shared_arena():
    hero = Unit("hero", "Hero", "player", (1, 2), ct=100)
    alpha = Unit("alpha", "Alpha", "enemy", (4, 1),
                 weapon="ranged", attack_range=5, skills=["ember"])
    zulu = Unit("zulu", "Zulu", "enemy", (4, 3),
                weapon="ranged", attack_range=5, skills=["ember"])
    ember = Skill("ember", "Ember", [Effect("damage", 3)],
                  target="ground", range=6, radius=1, cast_ticks=3)
    return Content({"ember": ember},
                   {"arena": Mission("arena", "Arena", Board(8, 6),
                                     [hero, alpha, zulu])})


def rows_at(view, kind, cell):
    return [row for row in view["danger"]
            if row["kind"] == kind and row["cell"] == list(cell)]


class OverlappingTacticalThreatTests(unittest.TestCase):
    def test_two_scheduled_casts_preserve_both_sources_in_all_projections(self):
        battle = Battle(shared_arena(), "arena", seed=31,
                        rules=tactical_rpg_rules())
        for uid in ("zulu", "alpha"):
            battle.unit(uid).cast = {
                "skill": "ember", "cell": [2, 2],
                "remaining": 2, "unit": None}
        before = battle.digest()
        view = tactical_intents(battle)
        threats = rows_at(view, "cast", (2, 2))
        self.assertEqual([row["unit"] for row in threats], ["alpha", "zulu"])
        self.assertEqual({row["certainty"] for row in threats}, {"scheduled"})
        self.assertEqual(len(rows_at(tactical_intents(battle), "cast", (2, 2))), 2)
        self.assertEqual(
            [row["unit"] for row in battle_frame(battle).danger
             if row["kind"] == "cast" and row["cell"] == [2, 2]],
            ["alpha", "zulu"])
        hud = combat_hud(battle_frame(battle), cell=(2, 2))
        self.assertIn("sort programmé ×2", hud.warnings)
        self.assertIn("sort programmé ×2", hud.selection_summary)
        json.dumps(view, sort_keys=True)
        self.assertEqual(battle.digest(), before)

    def test_two_armed_overwatch_units_do_not_collapse_to_one_reaction(self):
        battle = Battle(shared_arena(), "arena", seed=31,
                        rules=tactical_rpg_rules())
        battle.prepared_reactions["zulu"] = {
            "mode": "overwatch", "charges": 1, "ct_tax": 20}
        battle.prepared_reactions["alpha"] = {
            "mode": "overwatch", "charges": 1, "ct_tax": 20}
        original = battle.digest()
        view = tactical_intents(battle)
        threats = rows_at(view, "prepared", (2, 2))
        self.assertEqual([row["unit"] for row in threats], ["alpha", "zulu"])
        self.assertEqual({row["certainty"] for row in threats}, {"armed"})
        self.assertIn("réaction armée ×2",
                      combat_hud(battle_frame(battle), cell=(2, 2)).warnings)
        self.assertEqual(battle.digest(), original)
        self.assertEqual(view, tactical_intents(battle))

    def test_two_independent_charge_corridors_share_a_target_cell(self):
        hero = Unit("hero", "Hero", "player", (5, 2), ct=100)
        west = Unit("west", "West", "enemy", (1, 2), move=5)
        south = Unit("south", "South", "enemy", (5, 5), move=5)
        content = Content({}, {"m": Mission("m", "M", Board(8, 8),
                                            [hero, west, south])})
        battle = Battle(content, "m", rules=tactical_rpg_rules(), seed=17)
        before = battle.digest()
        threats = rows_at(tactical_intents(battle), "charge", (5, 2))
        self.assertEqual([row["unit"] for row in threats], ["south", "west"])
        self.assertEqual({row["certainty"] for row in threats}, {"possible"})
        self.assertEqual(battle.digest(), before)

    def test_unchanged_canonical_commands_still_replay_exactly(self):
        rules = tactical_rpg_rules()
        battle = Battle(shared_arena(), "arena", seed=31, rules=rules)
        baseline = rules.manifest()
        tactical_intents(battle)
        battle.execute({"kind": "end"})
        recording = battle.recording()
        self.assertEqual(Battle.replay(recording, rules=rules).digest(),
                         battle.digest())
        self.assertEqual(rules.manifest(), baseline)


if __name__ == "__main__":
    unittest.main()

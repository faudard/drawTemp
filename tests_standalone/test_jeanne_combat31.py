"""Jeanne courtyard integration: authored mission, live AI and fair A/B."""
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest

from examples.jeanne_combat31 import (MISSION, balance_comparison,
                                      encounter_preview, jeanne_siege_content,
                                      main)
from examples.siege_scenarios import siege_content
from sporebound.ai import choose_command, simulate
from sporebound.engine import Battle
from sporebound.model import Content
from sporebound.presentation import battle_frame
from sporebound.tactical_rpg3 import tactical_rpg_rules


class JeanneCourtyardCombatTests(unittest.TestCase):
    def setUp(self):
        self.rules = tactical_rpg_rules()

    def test_editable_siege_fixture_and_original_not_mutated(self):
        original = siege_content().to_dict()
        content = jeanne_siege_content()
        content.validate(rules=self.rules)
        self.assertEqual(siege_content().to_dict(), original)
        self.assertEqual(content.missions[MISSION].objective, "eliminate")
        self.assertEqual(len(content.missions[MISSION].units), 10)
        tags = {unit.id: unit.tags for unit in content.missions[MISSION].units}
        self.assertEqual(tags["lance_nord"], ["squad:pikeman"])
        self.assertEqual(tags["officier"], ["squad:officer"])
        rebuilt = Content.from_dict(content.to_dict(), rules=self.rules)
        self.assertEqual(content.to_dict(), rebuilt.to_dict())
        self.assertEqual(rebuilt.missions["castle_courtyard"].units[0].id,
                         content.missions["castle_courtyard"].units[0].id)

    def test_studio_json_export_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "jeanne.json"
            main(["--export", str(destination)])
            exported = Content.load(destination, rules=self.rules)
            self.assertIn(MISSION, exported.missions)
            self.assertEqual(
                exported.missions[MISSION].name,
                "Jeanne — la cour intérieure (brèche)")

    def test_defender_actions_are_real_and_read_only(self):
        content = jeanne_siege_content()
        battle = Battle(content, MISSION, seed=12, rules=self.rules)
        original = battle.digest()
        for actor_id, expected in (
            ("lance_nord", {"kind": "formation", "mode": "phalanx"}),
            ("lance_sud", {"kind": "formation", "mode": "phalanx"}),
            ("officier", {"kind": "formation", "mode": "escort",
                          "target": "soigneur"}),
        ):
            battle.active_id = actor_id
            actor = battle.active
            actor.ct = 100
            before = battle.digest()
            self.assertEqual(choose_command(battle), expected)
            self.assertEqual(battle.digest(), before)
        # A temporary preview may change no canonical state.
        preview = encounter_preview(content)
        self.assertIn("timeline", preview["threats"])
        knight = [row for row in preview["threats"]["charges"]
                  if row["unit"] == "chevalier" and row["target"] == "ecuyer"]
        self.assertTrue(knight, "The knight's straight courtyard charge must be visible")
        self.assertEqual(knight[0]["certainty"], "possible")
        self.assertEqual(knight[0]["path"][-1], knight[0]["landing"])
        self.assertGreaterEqual(len(knight[0]["path"]), 2)
        view = battle_frame(battle)
        self.assertEqual(view.width, 12)
        self.assertTrue(view.timeline)
        self.assertNotEqual(original, battle.digest())  # manual setup only

    def test_real_formation_and_escort_actions_replay(self):
        content = jeanne_siege_content()
        for unit in content.missions[MISSION].units:
            unit.ct = 100 if unit.id in {"lance_nord", "lance_sud", "officier"} else 0
        battle = Battle(content, MISSION, seed=21, rules=self.rules)
        for unit_id, expected in (
            ("lance_nord", {"kind": "formation", "mode": "phalanx"}),
            ("lance_sud", {"kind": "formation", "mode": "phalanx"}),
            ("officier", {"kind": "formation", "mode": "escort",
                          "target": "soigneur"}),
        ):
            self.assertEqual(battle.active_id, unit_id)
            command = choose_command(battle)
            self.assertEqual(command, expected)
            battle.execute(command)
            battle.execute({"kind": "end"})
        self.assertTrue(any(event["kind"] == "formation" and event["mode"] == "escort"
                            for event in battle.events))
        self.assertTrue(any(event["kind"] == "formation" and event["mode"] == "phalanx"
                            for event in battle.events))
        self.assertEqual(Battle.replay(battle.recording(), rules=self.rules).digest(),
                         battle.digest())

    def test_balanced_coordinated_and_uncoordinated_rosters(self):
        strong = jeanne_siege_content()
        plain = jeanne_siege_content(coordinated=False)
        first = strong.missions[MISSION]
        second = plain.missions[MISSION]
        for a, b in zip(first.units, second.units):
            self.assertEqual((a.id, a.pos, a.attack, a.speed, a.hp),
                             (b.id, b.pos, b.attack, b.speed, b.hp))
            self.assertEqual(a.behavior, b.behavior)
        self.assertFalse(any(u.tags for u in second.units if u.team == "enemy"))
        results = balance_comparison(seeds=(7,), max_commands=80)
        self.assertEqual(results["baseline"], "isolated")
        self.assertEqual(results["seeds"], [7])
        self.assertEqual({row["name"] for row in results["compositions"]},
                         {"coordinated", "isolated"})
        for row in results["compositions"]:
            self.assertEqual(row["report"]["runs"], 1)
            self.assertEqual(len(row["report"]["samples"]), 1)
            self.assertLessEqual(row["report"]["commands_p95"], 80)


if __name__ == "__main__":
    unittest.main()

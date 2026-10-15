"""R8.D acceptance: real statuses/reactions and AI, transactional document semantics."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.r8_combat_ai import CombatAIEditor
from drawtemp.studio.rpg_database import DatabaseEditor, lancer_example
from sporebound.engine import Battle
from sporebound.model import Content, RuleError
from sporebound.tactical_rpg3 import authored_rules_for_document


class CombatAIR8Tests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)
        self.editor = CombatAIEditor(self.session)
        self.database = DatabaseEditor(self.session)
        self.actors = self.editor.actors(MISSION)
        self.player = next(a[0] for a in self.actors if a[2] == "player")
        self.enemy = next(a[0] for a in self.actors if a[2] == "enemy")

    def _battle(self):
        data = self.session.snapshot().to_dict()["content"]
        rules = authored_rules_for_document(data)
        return Battle(Content.from_dict(data, rules=rules), MISSION,
                      seed=17, rules=rules)

    def test_initial_states_and_resistances_use_real_battle(self):
        baseline = self.session.snapshot()
        self.editor.states(MISSION, self.player,
                           statuses={"protect": 24, "haste": 60},
                           resistances={"physical": 100, "fire": -25},
                           reaction="counter", support="defense_up",
                           movement="move_plus_1")
        self.assertEqual(self.session.snapshot().revision, baseline.revision + 1)
        battle = self._battle()
        target = battle.unit(self.player)
        attacker = battle.unit(self.enemy)
        self.assertEqual(target.statuses["protect"], 24)
        self.assertEqual(target.resistances["physical"], 100)
        self.assertEqual(target.reaction, "counter")
        skill = battle._basic(attacker)
        self.assertEqual(battle._mitigate(attacker, target, skill,
                                         skill.effects[0], 250), 0)
        report = self.editor.preview(MISSION, self.player, seed=17)
        self.assertEqual(report["battle_digest"], battle.digest())
        self.assertGreater(report["effective_speed"], target.speed)
        self.assertEqual(report["active_enemy_plan"], None)
        self.assertEqual(report["certainty"], "observed_initial_state")
        self.assertEqual(self.session.snapshot().revision, baseline.revision + 1)
        self.editor.undo()
        self.assertEqual(self.session.snapshot().content, baseline.content)
        self.editor.redo()
        self.assertEqual(self.editor.detail(MISSION, self.player)["reaction"],
                         "counter")

    def test_ai_doctrine_and_phalanx_preserve_unrelated_tags(self):
        self.database.update("actors", self.enemy, mission_id=MISSION,
                             weapon="spear", tags=["quest:watcher", "medic"])
        previous = self.session.snapshot()
        self.editor.ai(MISSION, self.enemy, roles=("protector", "leader"),
                       doctrine="spear_hold", squad="west_gate",
                       formation="phalanx")
        row = self.editor.detail(MISSION, self.enemy)
        self.assertEqual(row["behavior"], "tactical")
        self.assertEqual(row["patrol_route"], ())
        self.assertIn("quest:watcher", row["tags"])
        self.assertNotIn("medic", row["tags"])
        self.assertIn("protector", row["tags"])
        self.assertIn("leader", row["tags"])
        self.assertIn("squad:west_gate", row["tags"])
        self.assertIn("doctrine:spear_hold", row["tags"])
        self.assertIn("formation:phalanx", row["tags"])
        self.assertEqual(self.session.snapshot().revision, previous.revision + 1)
        battle = self._battle()
        self.assertEqual(battle.unit(self.enemy).weapon, "spear")
        self.assertEqual(battle.unit(self.enemy).behavior, "tactical")
        report = self.editor.preview(MISSION, self.enemy)
        self.assertEqual(report["formation"]["mode"], "phalanx")
        self.assertIs(report["formation"]["phalanx"], False)
        self.editor.undo()
        self.assertEqual(self.session.snapshot().content, previous.content)

    def test_reject_incompatible_doctrine_and_bad_formation_atomically(self):
        before = self.session.snapshot()
        bad = [
            lambda: self.editor.ai(MISSION, self.enemy,
                                   doctrine="spear_hold"),
            lambda: self.editor.ai(MISSION, self.enemy,
                                   doctrine="crossbow_reload"),
            lambda: self.editor.ai(MISSION, self.enemy, formation="phalanx"),
            lambda: self.editor.ai(MISSION, self.player,
                                   doctrine="bandit_ambush"),
            lambda: self.editor.ai(MISSION, self.player, behavior="adaptive_boss"),
            lambda: self.editor.ai(MISSION, self.enemy, roles=("medic", "medic")),
            lambda: self.editor.ai(MISSION, self.enemy, formation="escort",
                                   escort_target="missing"),
            lambda: self.editor.ai(MISSION, self.enemy, doctrine="pack_hunt",
                                   route=((0, 0), (1, 0))),
            lambda: self.editor.states(MISSION, self.player,
                                       statuses={"haste": 0}),
            lambda: self.editor.states(MISSION, self.player,
                                       statuses={"haste": 20, "slow": 20}),
            lambda: self.editor.ai(MISSION, self.enemy,
                                   behavior="coordinated", doctrine="pack_hunt"),
            lambda: self.editor.states(MISSION, self.player,
                                       resistances={"physical": 120}),
            lambda: self.editor.states(MISSION, self.player,
                                       reaction="invented"),
        ]
        for fn in bad:
            with self.subTest(fn=fn), self.assertRaises(RuleError):
                fn()
            self.assertEqual(self.session.snapshot(), before)

    def test_enemy_tactical_policy_and_patrol_are_validated(self):
        self.editor.ai(MISSION, self.enemy, behavior="tactical",
                       route=((0, 2), (0, 3)))
        self.assertEqual(self.editor.detail(MISSION, self.enemy)
                         ["patrol_route"], ((0, 2), (0, 3)))
        with self.assertRaises(RuleError):
            self.editor.ai(MISSION, self.enemy, behavior="adaptive_boss",
                           route=((0, 2), (0, 3)))
        self._battle()

    def test_effect_status_changes_real_skill_without_shadow_database(self):
        lancer_example(self.session)
        old = self.database.detail("skills", "r8_guard_ally")
        self.editor.set_status_effect("r8_guard_ally", 0, "haste", 64)
        new = self.database.detail("skills", "r8_guard_ally")
        self.assertEqual(new["effects"][0]["status"], "haste")
        self.assertEqual(new["effects"][0]["duration"], 64)
        self.assertEqual(new["effects"][0]["kind"], "status")
        self.assertEqual(new["cost"], old["cost"])
        self.assertEqual(new["target"], old["target"])
        with self.assertRaises(RuleError):
            self.editor.set_status_effect("r8_guard_ally", 0, "imaginary", 20)
        with self.assertRaises(RuleError):
            self.editor.set_status_effect("r8_guard_ally", 0, "slow", 0)
        self._battle()

    def test_roundtrip_save_and_no_unintended_change_to_templates(self):
        lancer_example(self.session)
        archetype = self.database.detail("archetypes", "r8_lancier")
        self.editor.states(MISSION, self.enemy, statuses={"guard": -1},
                           reaction="opportunity")
        self.editor.ai(MISSION, self.enemy, roles=("leader",))
        original = self.session.snapshot().to_dict()
        self.assertEqual(self.database.detail("archetypes", "r8_lancier"),
                         archetype)
        with TemporaryDirectory() as root:
            filename = Path(root) / "r8d.json"
            self.session.save_as(filename)
            restored = AuthoringSession.open(filename)
            self.assertEqual(restored.snapshot().to_dict()["content"],
                             original["content"])
            new_editor = CombatAIEditor(restored)
            self.assertEqual(new_editor.detail(MISSION, self.enemy)
                             ["statuses"]["guard"], -1)
            self.assertIn("leader", new_editor.detail(MISSION, self.enemy)["tags"])


if __name__ == "__main__":
    unittest.main()

"""R53.A2 — native RPG cooperative skills with deterministic R41 turn replay."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.classic_party import EXTENSION
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from tests_standalone.test_r41_encounter import encounter_fixture


def combo_fixture(*, with_skills=True, extra_enemy=True):
    content, project = encounter_fixture()
    spec = project.extensions[EXTENSION]["data"]
    spec["campaigns"]["main"].update(
        recruitable=["jeanne", "etienne"],
        initial=["jeanne", "etienne"],
        active=["jeanne", "etienne"],
        max_active=2)
    combo = {"id": "combined_strike",
             "members": ["jeanne", "etienne"],
             "modes": ["RPG_TURN", "TACTICAL_CT"]}
    if with_skills:
        combo["skills"] = {"jeanne": "estoc", "etienne": "garde_rapprochee"}
    spec["orchestration"] = {
        "version": 1, "pause_policy": "freeze_on_encounter", "combos": [combo]}
    if extra_enemy:
        spec["encounters"]["sparring"]["enemies"].append("raider_secours_1")
    content.skills["estoc"].cost = 2
    content.skills["garde_rapprochee"].cost = 1
    project.validate(content)
    return content, project


def seal(row):
    row["digest"] = digest({k: v for k, v in row.items() if k != "digest"})
    return row


class R53ComboRpgTests(unittest.TestCase):
    def test_real_native_effects_partner_cost_and_skipped_next_turn(self):
        content, project = combo_fixture()
        session = GameSession.new(content, project, "main", seed=17)
        session.progress.inventory["potion"] = 3
        session.rpg_start("sparring")
        before = session.rpg_state()
        self.assertEqual(before["active"], "jeanne")
        self.assertEqual(before["combos"], ["combined_strike"])
        stats = {row["id"]: row for row in before["actors"]}
        enemy_before = stats["renaud_mentor"]["hp"]
        result = session.rpg_action({
            "kind": "combo", "actor": "jeanne",
            "target": "renaud_mentor", "combo": "combined_strike"})
        changed = {row["id"]: row for row in result["actors"]}
        self.assertLess(changed["renaud_mentor"]["hp"], enemy_before)
        self.assertEqual(changed["jeanne"]["mp"], stats["jeanne"]["mp"] - 2)
        self.assertEqual(changed["etienne"]["mp"], stats["etienne"]["mp"] - 1)
        self.assertEqual(session.progress.inventory["potion"], 3)
        # Etienne's next activation was spent supporting Jeanne, then skipped.
        self.assertEqual(result["active"], "jeanne")
        self.assertEqual(result["combo_skip"], [])
        self.assertEqual(session._rpg_encounter.commands[0]["kind"], "combo")

    def test_save_mid_encounter_roundtrip_and_once_only_settlement(self):
        content, project = combo_fixture()
        session = GameSession.new(content, project, "main", seed=42)
        session.rpg_start("sparring")
        session.rpg_action({
            "kind": "combo", "actor": "jeanne",
            "target": "renaud_mentor", "combo": "combined_strike"})
        initial = session.recording()
        replayed = GameSession.from_recording(initial, content, project)
        self.assertEqual(replayed.recording(), initial)
        with TemporaryDirectory() as path:
            target = Path(path) / "r53-combo.json"
            session.save(target)
            reload = GameSession.load(target, content, project)
            self.assertEqual(reload.recording(), initial)
            self.assertEqual(reload.party_orchestration_state(),
                             session.party_orchestration_state())
        for _ in range(40):
            if replayed.rpg_state()["result"] is not None:
                break
            current = replayed.rpg_state()["active"]
            replayed.rpg_action({
                "kind": "attack", "actor": current, "target": "raider_secours_1"})
        self.assertEqual(replayed.rpg_state()["result"], "victory")
        self.assertEqual(replayed.progress.gold, 0)
        replayed.rpg_finish()
        self.assertEqual(replayed.progress.gold, 17)
        with self.assertRaises(RuleError):
            replayed.rpg_finish()
        self.assertEqual(replayed.progress.gold, 17)

    def test_invalid_actions_rollback_entire_session(self):
        content, project = combo_fixture()
        session = GameSession.new(content, project, "main")
        session.rpg_start("sparring")
        initial = session.recording()
        invalid = [
            {"kind": "combo", "actor": "etienne",
             "target": "renaud_mentor", "combo": "combined_strike"},
            {"kind": "combo", "actor": "jeanne",
             "target": "etienne", "combo": "combined_strike"},
            {"kind": "combo", "actor": "jeanne",
             "target": "renaud_mentor", "combo": "unknown"},
            {"kind": "combo", "actor": "jeanne",
             "target": "renaud_mentor", "combo": "combined_strike", "debug": True},
        ]
        for action in invalid:
            with self.subTest(action=action), self.assertRaises(RuleError):
                session.rpg_action(action)
            self.assertEqual(session.recording(), initial)
        session._rpg_encounter.actors["etienne"]["hp"] = 0
        # Do not serialize the manual fault injection: verify that the
        # canonical turn boundary rejects an unavailable helper.
        with self.assertRaises(RuleError):
            session.rpg_action({"kind": "combo", "actor": "jeanne",
                                "target": "renaud_mentor", "combo": "combined_strike"})

    def test_rpg_command_and_recovery_cannot_be_forged_with_valid_outer_digest(self):
        content, project = combo_fixture()
        session = GameSession.new(content, project, "main")
        session.rpg_start("sparring")
        session.rpg_action({
            "kind": "combo", "actor": "jeanne",
            "target": "renaud_mentor", "combo": "combined_strike"})
        original = session.recording()
        for change in (
            lambda data: data["rpg_encounter"]["commands"][0].update(
                combo="not_authored"),
            lambda data: data["rpg_encounter"]["view"].update(
                combo_skip=["etienne"]),
            lambda data: data["rpg_encounter"]["view"].update(combos=["fake"]),
        ):
            changed = deepcopy(original)
            change(changed)
            with self.subTest(change=change), self.assertRaises(RuleError):
                GameSession.from_recording(seal(changed), content, project)

    def test_advisory_combo_and_legacy_r41_are_not_executable(self):
        content, project = combo_fixture(with_skills=False)
        session = GameSession.new(content, project, "main")
        session.rpg_start("sparring")
        self.assertNotIn("combos", session.rpg_state())
        initial = session.recording()
        with self.assertRaises(RuleError):
            session.rpg_action({
                "kind": "combo", "actor": "jeanne",
                "target": "renaud_mentor", "combo": "combined_strike"})
        self.assertEqual(session.recording(), initial)
        content, project = encounter_fixture()
        vanilla = GameSession.new(content, project, "main")
        vanilla.rpg_start("sparring")
        self.assertNotIn("combos", vanilla.rpg_state())
        self.assertNotIn("combo_skip", vanilla.rpg_state())

    def test_schema_refuses_wrong_skill_effect_ownership_and_capabilities(self):
        content, project = combo_fixture()
        candidates = [
            lambda combo: combo["skills"].update(jeanne="premiers_soins"),
            lambda combo: combo["skills"].update(etienne="unknown"),
            lambda combo: combo["skills"].pop("etienne"),
            lambda combo: combo.update(skills={"jeanne": "estoc",
                                                "etienne": "garde_rapprochee",
                                                "extra": "estoc"}),
            lambda combo: combo.update(modes=["TACTICAL_CT"]),
        ]
        for mutate in candidates:
            altered = deepcopy(project)
            combo = altered.extensions[EXTENSION]["data"]["orchestration"]["combos"][0]
            mutate(combo)
            with self.subTest(mutate=mutate), self.assertRaises(RuleError):
                altered.validate(content)


if __name__ == "__main__":
    unittest.main()

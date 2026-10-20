"""R53.B1 — canonical Party Composer transactions, default seeds and preview."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.party_orchestration_authoring import (
    apply_orchestration_edit, combo_impact_preview, inspect_orchestration,
    native_damage_choices, preview_orchestration_edit,
)
from sporebound.classic_party import EXTENSION
from sporebound.game_session import GameSession
from sporebound.model import RuleError
from tests_standalone.test_r41_classic_party import party_fixture


def composer_fixture():
    content, project = party_fixture()
    config = project.extensions[EXTENSION]["data"]["campaigns"]["main"]
    config.update(recruitable=["jeanne", "etienne"], initial=["jeanne", "etienne"],
                  active=["jeanne", "etienne"], max_active=2)
    project.validate(content)
    return content, project


def joint_strike():
    return [{"id": "joint_strike", "members": ["jeanne", "etienne"],
             "modes": ["RPG_TURN", "TACTICAL_CT"],
             "skills": {"jeanne": "estoc",
                        "etienne": "garde_rapprochee"}}]


class R53PartyComposerTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = composer_fixture()
        self.editor = AuthoringSession.new(self.content, self.project)

    def edit(self, **changes):
        data = {"leader": "etienne", "formation": ["rear", "front"],
                "combos": joint_strike()}
        data.update(changes)
        return preview_orchestration_edit(self.editor, "main",
                                          expected_revision=self.editor.revision,
                                          **data)

    def test_authoring_preview_apply_undo_redo_runtime_seed_and_replay(self):
        snapshot = self.editor.snapshot().to_dict()
        before = inspect_orchestration(self.editor.snapshot(), "main")
        self.assertFalse(before["enabled"])
        self.assertEqual(before["leader"], "jeanne")
        self.assertEqual(before["formation"], ["front", "left"])
        self.assertIn(("estoc", "Estoc"),
                      native_damage_choices(self.editor.snapshot(), "jeanne"))
        impact = combo_impact_preview(self.editor.snapshot(), joint_strike())
        self.assertTrue(impact[0]["executable_rpg"])
        self.assertEqual(impact[0]["native_skills"][0]["hero"], "jeanne")
        self.assertEqual(impact[0]["native_skills"][0]["skill"], "estoc")

        draft = self.edit()
        self.assertEqual(self.editor.snapshot().to_dict(), snapshot)
        applied = apply_orchestration_edit(self.editor, draft)
        self.assertEqual(applied.snapshot.revision, 1)
        result = inspect_orchestration(self.editor.snapshot(), "main")
        self.assertEqual(result["leader"], "etienne")
        self.assertEqual(result["formation"], ["rear", "front"])
        self.assertEqual(result["combos"], joint_strike())

        document = self.editor.snapshot().to_dict()
        self.assertEqual(document["content"], snapshot["content"])
        from sporebound.game_project import GameProject
        from sporebound.model import Content
        content = Content.from_dict(document["content"])
        project = GameProject.from_dict(document["project"], content)
        session = GameSession.new(content, project, "main", seed=19)
        state = session.party_orchestration_state()
        self.assertEqual(state["leader"], "etienne")
        self.assertEqual(state["formation"], ["rear", "front"])
        self.assertEqual(state["eligible_combos"], ["joint_strike"])
        self.assertEqual(GameSession.from_recording(
            session.recording(), content, project).recording(), session.recording())

        self.editor.undo()
        self.assertEqual(self.editor.snapshot().to_dict()["project"],
                         snapshot["project"])
        self.editor.redo()
        self.assertEqual(inspect_orchestration(self.editor.snapshot(), "main")[
            "formation"], ["rear", "front"])

    def test_invalid_combos_slots_leaders_and_stale_edits_are_atomic(self):
        snapshot = self.editor.snapshot().to_dict()
        invalid = [
            {"leader": "margot"},
            {"formation": ["front", "front"]},
            {"formation": ["unknown", "front"]},
            {"formation": ["front"]},
            {"combos": [{"id": "bad", "members": ["jeanne", "margot"],
                         "modes": ["RPG_TURN"]}]},
            {"combos": [{"id": "bad", "members": ["jeanne", "etienne"],
                         "modes": ["RPG_TURN"],
                         "skills": {"jeanne": "premiers_soins",
                                    "etienne": "estoc"}}]},
        ]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(RuleError):
                self.edit(**change)
            self.assertEqual(self.editor.snapshot().to_dict(), snapshot)

        original = self.edit()
        alternative = self.edit(leader="jeanne", formation=["front", "rear"])
        apply_orchestration_edit(self.editor, alternative)
        later = self.editor.snapshot().to_dict()
        with self.assertRaises(RuleError):
            apply_orchestration_edit(self.editor, original)
        with self.assertRaises(RuleError):
            preview_orchestration_edit(
                self.editor, "main", leader="etienne", formation=["rear", "front"],
                combos=joint_strike(), expected_revision=0)
        self.assertEqual(self.editor.snapshot().to_dict(), later)

    def test_declarative_combo_has_no_invented_skill_executor(self):
        declarative = [{"id": "group_pose", "members": ["jeanne", "etienne"],
                        "modes": ["TACTICAL_CT"]}]
        draft = self.edit(combos=declarative)
        apply_orchestration_edit(self.editor, draft)
        view = inspect_orchestration(self.editor.snapshot(), "main")
        self.assertEqual(view["combos"], declarative)
        self.assertFalse(combo_impact_preview(self.editor.snapshot(),
                                             declarative)[0]["executable_rpg"])

    def test_changing_r41_active_roster_rejects_stale_r53_default(self):
        apply_orchestration_edit(self.editor, self.edit())
        snapshot = self.editor.snapshot().to_dict()
        from drawtemp.studio.party_authoring import (
            apply_party_edit, preview_party_edit)
        draft = preview_party_edit(
            self.editor, "main", recruitable=["jeanne", "etienne"],
            initial=["jeanne", "etienne"], active=["jeanne"],
            max_active=2, expected_revision=self.editor.revision)
        with self.assertRaises(RuleError):
            apply_party_edit(self.editor, draft)
        self.assertEqual(self.editor.snapshot().to_dict(), snapshot)

    def test_defaults_do_not_leak_into_another_campaign(self):
        content, project = composer_fixture()
        clone = deepcopy(project.campaigns[0])
        clone["id"] = "secondary"
        clone["name"] = "Campagne secondaire"
        project.campaigns.append(clone)
        project.extensions[EXTENSION]["data"]["campaigns"]["secondary"] = {
            "recruitable": ["jeanne", "etienne"],
            "initial": ["jeanne"], "active": ["jeanne"], "max_active": 2}
        project.validate(content)
        editor = AuthoringSession.new(content, project)
        draft = preview_orchestration_edit(
            editor, "main", leader="etienne",
            formation=["rear", "front"], combos=joint_strike())
        apply_orchestration_edit(editor, draft)
        data = editor.snapshot().to_dict()
        from sporebound.game_project import GameProject
        manifest = GameProject.from_dict(data["project"], content)
        primary = GameSession.new(content, manifest, "main")
        secondary = GameSession.new(content, manifest, "secondary")
        self.assertEqual(primary.party_orchestration_state()["leader"],
                         "etienne")
        self.assertEqual(secondary.party_orchestration_state()["leader"],
                         "jeanne")


if __name__ == "__main__":
    unittest.main()

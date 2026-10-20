"""R65.B: versioned canonical presets, replay and reversible authoring gates."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.combat_composer_r65 import CombatComposerDraft
from sporebound.action_combat_catalog_r65 import (
    NAMESPACE, catalog_from_project, hitbox_preview, preset_from_project,
    runtime_from_project, starter_preset, validate_catalog, validate_preset,
    windows_preview,
)
from sporebound.action_combat_r65 import ActionCombatR65
from sporebound.action_runtime import ActionError
from sporebound.game_project import GameProject


def editor():
    return AuthoringSession.new(*reference_project())


def arena(*, walls=None):
    return {"id": "r65b_arena", "width": 9, "height": 9,
            "walls": walls if walls is not None else [],
            "hero": {"pos": [4, 4], "hp": 16},
            "enemies": [], "objects": []}


class R65CombatComposerTests(unittest.TestCase):
    def test_legacy_inert_and_preview_atomic_undo_redo(self):
        session = editor()
        before = session.snapshot().to_dict()
        self.assertEqual(catalog_from_project(before["project"])["presets"], [])
        draft = CombatComposerDraft.create(session, "sword")
        draft.document["rules"]["combo"][0]["damage"] = 4
        report = draft.preview(scene=arena())
        self.assertEqual(report["after"]["id"], "sword")
        self.assertEqual(report["timeline"]["windows"][1]["kind"], "active")
        self.assertIn([5, 4], report["geometry"]["cells"])
        self.assertEqual(session.snapshot().to_dict(), before)
        draft.apply()
        after = session.snapshot().to_dict()
        self.assertEqual(after["revision"], before["revision"] + 1)
        self.assertEqual(
            catalog_from_project(after["project"])["default"], "sword")
        self.assertEqual(after["content"], before["content"])
        session.undo()
        self.assertEqual(session.snapshot().to_dict()["project"], before["project"])
        session.redo()
        self.assertEqual(session.snapshot().to_dict()["project"], after["project"])

    def test_second_preset_does_not_mutate_first_and_native_runtime(self):
        session = editor()
        first = CombatComposerDraft.create(session, "blade")
        first.preview()
        first.apply()
        second = CombatComposerDraft.create(session, "bow")
        second.document["rules"]["combo"][0]["windup"] = 8
        second.preview(default="bow")
        second.apply()
        catalog = catalog_from_project(session.snapshot().to_dict()["project"])
        self.assertEqual({p["id"] for p in catalog["presets"]}, {"blade", "bow"})
        self.assertEqual(catalog["default"], "bow")
        self.assertEqual(preset_from_project(
            session.snapshot().to_dict()["project"])["id"], "bow")
        combat = runtime_from_project(
            arena(), session.snapshot().to_dict()["project"], preset_id="blade",
            initial_inventory={"key": 2})
        for tick in range(1, 12):
            combat.step({"tick": tick, "dx": 1 if tick == 1 else 0,
                         "attack": tick == 1})
        self.assertEqual(combat.digest(),
                         ActionCombatR65.from_recording(combat.recording()).digest())
        self.assertEqual(combat.inventory["key"], 2)
        with self.assertRaises(ActionError):
            runtime_from_project(arena(), session.snapshot().to_dict()["project"],
                                 preset_id="missing")

    def test_revision_invalidates_preview_and_change_invalidates_pending(self):
        session = editor()
        draft = CombatComposerDraft.create(session, "blade")
        draft.preview()
        draft.replace(starter_preset("blade"))
        with self.assertRaises(ActionError):
            draft.apply()
        draft.preview()
        session.apply(session.preview_project(
            lambda project: {**project, "subtitle": "changed"}))
        with self.assertRaises(ActionError):
            draft.apply()
        with self.assertRaises(ActionError):
            draft.preview()
        self.assertEqual(catalog_from_project(
            session.snapshot().to_dict()["project"])["presets"], [])

    def test_existing_identity_duplicate_and_noop_refused(self):
        session = editor()
        d = CombatComposerDraft.create(session, "blade")
        d.preview()
        d.apply()
        with self.assertRaises(ActionError):
            CombatComposerDraft.create(session, "blade").preview()
        current = CombatComposerDraft.load(session, "blade")
        with self.assertRaises(ActionError):
            current.preview()
        changed = deepcopy(current.document)
        changed["id"] = "renamed"
        current.replace(changed)
        with self.assertRaises(ActionError):
            current.preview()
        with self.assertRaises(ActionError):
            CombatComposerDraft.load(session, "missing")

    def test_known_namespace_is_fail_closed_on_project_load(self):
        content, project = reference_project()
        bad = project.to_dict()
        entry = starter_preset()
        entry["rules"]["combo"][0]["damage"] = True
        bad["extensions"] = {
            NAMESPACE: {"schema_version": 1, "data": {
                "version": 1, "default": "starter", "presets": [entry]},
                "references": []}
        }
        with self.assertRaises(Exception):
            GameProject.from_dict(bad, content)
        self.assertEqual(project.to_dict().get("extensions", {}), {})

    def test_metadata_bounds_and_version_reject_scripts(self):
        preset = starter_preset()
        self.assertEqual(validate_preset(preset), preset)
        for mutator in (
            lambda p: p["telegraphs"][0].update(stage=99),
            lambda p: p["telegraphs"][0].update(lead_ticks=True),
            lambda p: p["boss_patterns"].append({
                "id": "boss", "phase": 3, "hp_at_or_below": 50,
                "steps": [{"kind": "melee", "repeat": 1, "wait_ticks": 1}]}),
            lambda p: p["boss_patterns"].append({
                "id": "boss", "phase": 1, "hp_at_or_below": 50,
                "steps": [{"kind": "__import__", "repeat": 1, "wait_ticks": 1}]}),
        ):
            invalid = deepcopy(preset)
            mutator(invalid)
            with self.subTest(invalid=invalid), self.assertRaises(ActionError):
                validate_preset(invalid)
        with self.assertRaises(ActionError):
            validate_catalog({"version": 2, "default": "", "presets": []})
        with self.assertRaises(ActionError):
            validate_catalog({"version": 1, "default": "missing",
                              "presets": [preset]})

    def test_boss_patterns_metadata_only_not_runtime_changes(self):
        with_pattern = starter_preset()
        with_pattern["boss_patterns"] = [{
            "id": "two_phase", "phase": 2, "hp_at_or_below": 50,
            "steps": [{"kind": "projectile", "repeat": 3, "wait_ticks": 10}]
        }]
        plain = starter_preset()
        self.assertEqual(windows_preview(with_pattern)["boss_patterns"][0]["phase"], 2)
        session = editor()
        draft = CombatComposerDraft.create(session, "sword")
        draft.replace({**with_pattern, "id": "sword"})
        draft.preview()
        draft.apply()
        project = session.snapshot().to_dict()["project"]
        loaded = runtime_from_project(arena(), project)
        baseline = ActionCombatR65(arena(), plain["rules"])
        for tick in range(1, 8):
            command = {"tick": tick, "attack": tick == 1}
            loaded.step(command)
            baseline.step(command)
        self.assertEqual(loaded.digest(), baseline.digest(),
                         "Boss choreography remains inert until R65.C")

    def test_hitbox_los_and_preview_no_side_effects(self):
        preset = starter_preset()
        original = deepcopy(preset)
        overlay = hitbox_preview(arena(), preset)
        self.assertIn([5, 4], overlay["cells"])
        self.assertNotIn([3, 4], overlay["cells"])
        blocked = hitbox_preview(arena(walls=[[5, 4]]), preset)
        self.assertNotIn([5, 4], blocked["cells"])
        self.assertIn([5, 4], blocked["blocked"])
        self.assertEqual(preset, original)
        with self.assertRaises(ActionError):
            hitbox_preview(arena(), preset, stage=True)
        with self.assertRaises(ActionError):
            hitbox_preview(arena(), preset, facing=(0, 0))


if __name__ == "__main__":
    unittest.main()

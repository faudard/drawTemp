"""R43.B1 headless authoring and schematic viewport regression tests."""
from copy import deepcopy
import unittest

from drawtemp.sdk.ability_contracts import AbilityError, catalog_from_project, preview_ability
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.ability_authoring_r43 import AbilityDraft, area_preview


def editor():
    return AuthoringSession.new(*reference_project())


class AbilityDraftTests(unittest.TestCase):
    def test_new_preview_does_not_write_until_atomic_apply(self):
        session = editor()
        before = session.snapshot().to_dict()
        draft = AbilityDraft.create(session, "r43_ice")
        draft.document["name"] = "Gel"
        result = draft.preview()
        self.assertEqual(result.report["id"], "r43_ice")
        self.assertEqual(result.report["native_CT"]["id"], "r43_ice")
        self.assertEqual(session.snapshot().to_dict(), before)
        self.assertTrue(result.report["target_preview"]["in_range"])
        draft.apply()
        after = session.snapshot().to_dict()
        self.assertEqual(session.revision, 1)
        self.assertEqual(
            catalog_from_project(after["project"])["abilities"][0]["id"], "r43_ice")
        self.assertIn("r43_ice", [skill["id"] for skill in after["content"]["skills"]])
        session.undo()
        self.assertEqual(session.snapshot().to_dict()["content"], before["content"])
        self.assertEqual(session.snapshot().to_dict()["project"], before["project"])
        session.redo()
        self.assertEqual(session.snapshot().to_dict()["content"], after["content"])

    def test_effect_ordering_budget_and_pending_invalidation(self):
        session = editor()
        draft = AbilityDraft.create(session)
        draft.add_effect()
        draft.edit_effect(
            1, kind="heal", formula={"op": "constant", "value": 10},
            element="physical", status="", duration=1, scope="allies")
        self.assertEqual([e["kind"] for e in draft.document["effects"]],
                         ["damage", "heal"])
        draft.move_effect(1, -1)
        self.assertEqual([e["kind"] for e in draft.document["effects"]],
                         ["heal", "damage"])
        self.assertEqual(draft.preview().report["after"]["effects"][0]["kind"], "heal")
        draft.add_effect()
        self.assertIsNone(draft.pending)
        with self.assertRaises(AbilityError) as error:
            draft.apply()
        self.assertEqual(error.exception.code, "preview_required")
        for _ in range(5):
            draft.add_effect()
        with self.assertRaises(AbilityError):
            draft.add_effect()
        for _ in range(7):
            draft.remove_effect(0)
        with self.assertRaises(AbilityError):
            draft.remove_effect(0)

    def test_existing_skill_id_cannot_be_renamed_or_clobbered(self):
        session = editor()
        created = AbilityDraft.create(session)
        created.apply if False else None
        created.preview()
        created.apply()
        loaded = AbilityDraft.load(session, "r43_new")
        loaded.document["id"] = "r43_renamed"
        with self.assertRaises(AbilityError) as error:
            loaded.preview()
        self.assertEqual(error.exception.code, "id_change")
        duplicate = AbilityDraft.create(session, "r43_new")
        with self.assertRaises(AbilityError):
            duplicate.preview()
        self.assertEqual(session.revision, 1)

    def test_revision_and_mode_gates_fail_closed(self):
        session = editor()
        draft = AbilityDraft.create(session)
        with self.assertRaises(AbilityError) as error:
            draft.preview(mode="RPG_TURN")
        self.assertEqual(error.exception.code, "unsupported_mode")
        planned = draft.preview()
        session.apply(session.preview_project(
            lambda data: {**data, "subtitle": "New revision"}))
        with self.assertRaises(AbilityError) as error:
            draft.preview()
        self.assertEqual(error.exception.code, "stale_revision")
        with self.assertRaises(AbilityError):
            draft.apply()
        with self.assertRaises(AbilityError):
            AbilityDraft.load(session, "missing")

    def test_action_only_formula_preview_is_numeric_not_runtime_execution(self):
        session = editor()
        draft = AbilityDraft.create(session)
        draft.set_header(
            name="Arc", profiles=["ACTION_REALTIME"], resource="stamina",
            cost=3, team="enemy", shape="cross", min_range=0, max_range=5,
            radius=2, timing={"ACTION_REALTIME": {"windup": 4, "cooldown": 12}})
        draft.edit_effect(
            0, kind="damage", formula={"op": "percent",
                                       "input": {"op": "stat", "name": "magic"},
                                       "amount": 150},
            element="lightning", status="", duration=1, scope="enemies")
        before = session.snapshot().to_dict()["content"]
        report = draft.preview(mode="ACTION_REALTIME").report
        self.assertEqual(report["impact"]["effects"][0]["power"], 18)
        self.assertIsNone(report["native_CT"])
        draft.apply()
        self.assertEqual(session.snapshot().to_dict()["content"], before)
        self.assertIn("ACTION_REALTIME",
                      catalog_from_project(session.snapshot().to_dict()["project"])
                      ["abilities"][0]["profiles"])

    def test_ct_dynamic_formula_rejected_without_native_adapter(self):
        session = editor()
        draft = AbilityDraft.create(session)
        draft.edit_effect(
            0, kind="damage",
            formula={"op": "stat", "name": "attack"}, element="fire",
            status="", duration=1, scope="target")
        with self.assertRaises(AbilityError) as error:
            draft.preview()
        self.assertEqual(error.exception.code, "unsupported_formula")
        self.assertEqual(session.revision, 0)

    def test_target_footprints_and_range_are_pure(self):
        original = {"team": "enemy", "shape": "single", "min_range": 0,
                    "range": 3, "radius": 0}
        before = deepcopy(original)
        result = area_preview(original)
        self.assertEqual(result["cells"], [[4, 3]])
        self.assertEqual(original, before)
        for shape, expected in (("diamond", 13), ("square", 25), ("cross", 9)):
            target = {**original, "shape": shape, "radius": 2}
            area = area_preview(target, origin=(4, 4), aim=(4, 3))
            self.assertEqual(len(area["cells"]), expected)
        out = area_preview(original, aim=(0, 0))
        self.assertFalse(out["in_range"])
        self.assertEqual(out["cells"], [])
        with self.assertRaises(AbilityError):
            area_preview(original, aim=(-1, 2))
        with self.assertRaises(AbilityError):
            area_preview({**original, "radius": 1})


if __name__ == "__main__":
    unittest.main()

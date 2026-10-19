"""R43.A regression tests: strict schemas, deterministic math and CT compatibility."""
from copy import deepcopy
import unittest

from drawtemp.sdk.ability_contracts import (
    NAMESPACE, AbilityError, catalog_from_project, compile_ct_skill,
    digest_ability, evaluate_formula, preview_ability, resolve_ability,
    validate_ability, validate_catalog,
)
from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from drawtemp.sdk.reference import reference_project
from sporebound.game_project import GameProject
from sporebound.model import RuleError


def example_ability():
    return {
        "schema_version": 1, "id": "r43_flame", "name": "Flamme",
        "profiles": ["TACTICAL_CT", "ACTION_REALTIME"],
        "cost": {"resource": "mp", "amount": 3},
        "target": {"team": "enemy", "shape": "diamond",
                   "min_range": 0, "range": 3, "radius": 1},
        "timing": {
            "TACTICAL_CT": {"windup": 2, "cooldown": 0},
            "ACTION_REALTIME": {"windup": 4, "cooldown": 12},
        },
        "effects": [
            {"kind": "damage", "formula": {"op": "constant", "value": 12},
             "element": "fire", "status": "", "duration": 1, "scope": "enemies"},
        ],
    }


def stats():
    return {"attack": 9, "magic": 12, "defense": 3, "resistance": 2}


class AbilityContractTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.session = AuthoringSession.new(self.content, self.project)

    def test_legacy_project_roundtrip_does_not_add_extension(self):
        original = self.project.to_dict()
        self.assertNotIn("extensions", original)
        self.assertEqual(catalog_from_project(self.project)["abilities"], [])
        loaded = GameProject.from_dict(original, self.content)
        self.assertEqual(loaded.to_dict(), original)

    def test_atomic_preview_apply_undo_and_redo(self):
        previous = self.session.snapshot().to_dict()
        spec = example_ability()
        plan = preview_ability(self.session, spec)
        self.assertEqual(self.session.snapshot().to_dict(), previous)
        transition = self.session.apply(plan)
        updated = self.session.snapshot().to_dict()
        self.assertEqual(catalog_from_project(updated["project"])["abilities"], [spec])
        expected_native = compile_ct_skill(spec)
        self.assertIn(expected_native, updated["content"]["skills"])
        self.assertEqual(transition.snapshot.revision, self.session.revision)
        self.session.undo()
        self.assertEqual(self.session.snapshot().to_dict()["content"],
                         previous["content"])
        self.assertEqual(catalog_from_project(
            self.session.snapshot().to_dict()["project"])["abilities"], [])
        self.session.redo()
        self.assertEqual(self.session.snapshot().to_dict()["content"],
                         updated["content"])
        self.assertEqual(self.session.snapshot().to_dict()["project"],
                         updated["project"])

    def test_replaces_native_only_if_unchanged(self):
        first = example_ability()
        self.session.apply(preview_ability(self.session, first))
        second = deepcopy(first)
        second["effects"][0]["formula"]["value"] = 14
        self.session.apply(preview_ability(self.session, second))
        rows = [s for s in self.session.snapshot().to_dict()["content"]["skills"]
                if s["id"] == second["id"]]
        self.assertEqual(rows, [compile_ct_skill(second)])
        conflict = deepcopy(second)
        conflict["effects"][0]["formula"]["value"] = 15

        def manual_edit(content, project):
            for skill in content["skills"]:
                if skill["id"] == second["id"]:
                    skill["effects"][0]["power"] = 20
            return content, project

        self.session.apply(self.session.preview_pair(manual_edit))
        with self.assertRaises(AuthoringError):
            preview_ability(self.session, conflict)

    def test_rejects_native_collisions(self):
        spec = example_ability()
        spec["id"] = self.content.to_dict()["skills"][0]["id"]
        with self.assertRaises(AuthoringError):
            preview_ability(self.session, spec)

    def test_strict_failure_cases(self):
        cases = [
            ("schema", lambda a: a.update(schema_version=True)),
            ("mode", lambda a: a["profiles"].append("TACTICAL_CT")),
            ("unknown", lambda a: a["profiles"].append("MALICIOUS")),
            ("code", lambda a: a["effects"][0]["formula"].update({"eval": "open('x')"})),
            ("cost", lambda a: a["cost"].update(amount=True)),
            ("CT-cooldown", lambda a: a["timing"]["TACTICAL_CT"].update(cooldown=7)),
            ("AOE", lambda a: a["target"].update(min_range=4)),
            ("status", lambda a: a["effects"][0].update(status="unknown")),
            ("effect", lambda a: a["effects"][0].update(kind="arbitrary-python")),
            ("extra", lambda a: a.update(python="exec")),
        ]
        for label, mutate in cases:
            with self.subTest(label=label):
                data = example_ability()
                mutate(data)
                with self.assertRaises(AbilityError):
                    validate_ability(data)
        with self.assertRaises(AbilityError):
            validate_catalog({"version": 1,
                              "abilities": [example_ability(), example_ability()]})

    def test_canonical_load_checks_extension_even_without_studio(self):
        raw = self.project.to_dict()
        raw["extensions"] = {
            NAMESPACE: {"schema_version": 1, "references": [],
                        "data": {"version": 1, "abilities": [example_ability()]}}}
        self.assertEqual(GameProject.from_dict(raw, self.content).to_dict(), raw)
        raw["extensions"][NAMESPACE]["data"]["abilities"][0]["cost"]["amount"] = -1
        with self.assertRaises(RuleError):
            GameProject.from_dict(raw, self.content)

    def test_deterministic_integer_formula_and_profile_plans(self):
        a = {"op": "percent",
             "input": {"op": "subtract", "left": {"op": "stat", "name": "magic"},
                       "right": {"op": "stat", "name": "defense"}},
             "amount": 125}
        self.assertEqual(evaluate_formula(a, stats()), 11)
        self.assertEqual(evaluate_formula(a, stats()), 11)
        self.assertEqual(evaluate_formula(
            {"op": "subtract", "left": {"op": "constant", "value": 2},
             "right": {"op": "constant", "value": 8}}, stats()), 0)
        spec = example_ability()
        one = resolve_ability(spec, mode="ACTION_REALTIME", stats=stats())
        two = resolve_ability(deepcopy(spec), mode="ACTION_REALTIME", stats=stats())
        self.assertEqual(one, two)
        self.assertEqual(one["digest"], digest_ability(spec))
        with self.assertRaises(AbilityError):
            resolve_ability(spec, mode="RPG_TURN", stats=stats())
        spec["effects"][0]["formula"] = a
        with self.assertRaises(AbilityError):
            compile_ct_skill(spec)
        with self.assertRaises(AbilityError):
            evaluate_formula(a, {**stats(), "attack": True})
        huge = {"op": "constant", "value": 1}
        for _ in range(7):
            huge = {"op": "percent", "input": huge, "amount": 100}
        with self.assertRaises(AbilityError):
            evaluate_formula(huge, stats())

    def test_no_implicit_native_changes_for_action_only(self):
        action = example_ability()
        action["profiles"] = ["ACTION_REALTIME"]
        action["timing"] = {"ACTION_REALTIME": {"windup": 0, "cooldown": 5}}
        previous_content = self.session.snapshot().to_dict()["content"]
        self.session.apply(preview_ability(self.session, action))
        after = self.session.snapshot().to_dict()
        self.assertEqual(after["content"], previous_content)
        self.assertEqual(catalog_from_project(after["project"])["abilities"], [action])
        with self.assertRaises(AbilityError):
            compile_ct_skill(action)


if __name__ == "__main__":
    unittest.main()

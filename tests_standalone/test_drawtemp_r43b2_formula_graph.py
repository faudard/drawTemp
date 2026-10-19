"""R43.B2 — safe formula editing and deterministic numeric lab."""
from copy import deepcopy
import unittest

from drawtemp.sdk.ability_contracts import (
    AbilityError, evaluate_formula, digest_ability,
)
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.ability_authoring_r43 import AbilityDraft, new_ability
from drawtemp.studio.ability_formula_graph_r43 import (
    CASES, DEFAULT_STATS, balance_lab, describe_nodes, node_at, replace_node,
)


class FormulaGraphTests(unittest.TestCase):
    def test_retype_constant_to_percent_stat_and_recursive_calculation(self):
        original = {"op": "constant", "value": 9}
        wrapped = replace_node(original, (), op="percent", amount=150)
        self.assertEqual(wrapped["input"], original)
        with_stat = replace_node(wrapped, ("input",), op="stat", name="magic")
        self.assertEqual(evaluate_formula(with_stat, DEFAULT_STATS), 18)
        self.assertEqual(original, {"op": "constant", "value": 9})
        self.assertEqual([n["path"] for n in describe_nodes(with_stat)],
                         [(), ("input",)])
        self.assertEqual(node_at(with_stat, ("input",))["name"], "magic")
        no_alias = node_at(with_stat, ("input",))
        no_alias["name"] = "attack"
        self.assertEqual(node_at(with_stat, ("input",))["name"], "magic")

    def test_add_subtract_percentage_operators_are_deterministic(self):
        f = replace_node({"op": "stat", "name": "attack"},
                         (), op="add")
        f = replace_node(f, ("right",), op="constant", value=4)
        self.assertEqual(evaluate_formula(f, DEFAULT_STATS), 16)
        f = replace_node(f, (), op="subtract")
        self.assertEqual(evaluate_formula(f, DEFAULT_STATS), 8)
        f = replace_node(f, ("left",), op="percent", amount=125)
        self.assertEqual(evaluate_formula(f, DEFAULT_STATS), 11)
        self.assertEqual([node["path"] for node in describe_nodes(f)],
                         [(), ("left",), ("left", "input"), ("right",)])
        same = replace_node(f, ("left",), op="percent", amount=100)
        self.assertEqual(same["left"]["input"], f["left"]["input"])
        self.assertNotEqual(same, f)

    def test_invalid_paths_and_budget_never_change_source(self):
        formula = {"op": "constant", "value": 8}
        unchanged = deepcopy(formula)
        invalids = [
            (("input",), "stat", "invalid_path"),
            (("left",), "constant", "invalid_path"),
            (("left", "right", "left", "right", "input", "left"), "stat",
             "invalid_path"),
        ]
        for path, op, code in invalids:
            with self.subTest(path=path):
                with self.assertRaises(AbilityError) as caught:
                    replace_node(formula, path, op=op)
                self.assertEqual(caught.exception.code, code)
        with self.assertRaises(AbilityError):
            replace_node(formula, (), op="lambda")
        with self.assertRaises(AbilityError):
            replace_node(formula, (), op="constant", value=True)
        with self.assertRaises(AbilityError):
            replace_node(formula, (), op="percent", amount=999)
        for _ in range(5):
            formula = replace_node(formula, (), op="percent")
        old = deepcopy(formula)
        with self.assertRaises(AbilityError) as caught:
            replace_node(formula, (), op="percent")
        self.assertEqual(caught.exception.code, "formula_budget")
        self.assertEqual(formula, old)
        self.assertEqual(unchanged, {"op": "constant", "value": 8})

    def test_formula_node_budget_refuses_large_compositions(self):
        formula = {"op": "constant", "value": 1}
        for _ in range(4):
            formula = replace_node(formula, (), op="add")
        # Longest path depth 4 remains legal.
        self.assertEqual(len(describe_nodes(formula)), 9)
        previous = deepcopy(formula)
        for _ in range(1):
            formula = replace_node(formula, (), op="add")
        self.assertEqual(len(describe_nodes(formula)), 11)
        with self.assertRaises(AbilityError):
            replace_node(formula, (), op="add")
        self.assertEqual(len(describe_nodes(previous)), 9)

    def test_balance_lab_cannot_claim_runtime_damage_or_mutate_document(self):
        spec = new_ability("r43_arc")
        spec["profiles"] = ["ACTION_REALTIME"]
        spec["timing"] = {"ACTION_REALTIME": {"windup": 4, "cooldown": 10}}
        spec["cost"] = {"resource": "stamina", "amount": 5}
        formula = replace_node(spec["effects"][0]["formula"],
                               (), op="percent", amount=125)
        formula = replace_node(formula, ("input",), op="stat", name="magic")
        spec["effects"][0]["formula"] = formula
        before = deepcopy(spec)
        first, second = balance_lab(spec), balance_lab(spec)
        self.assertEqual(first, second)
        self.assertFalse(first["simulation"])
        self.assertEqual(spec, before)
        self.assertEqual(len(first["cases"]), len(CASES))
        self.assertEqual(first["cases"][1]["raw_damage_sum"], 15)
        self.assertEqual(first["cases"][2]["raw_damage_sum"], 35)
        self.assertIn("sans", first["note"])

    def test_raw_balance_rejects_malformed_statistics(self):
        spec = new_ability()
        for cases in ((), [("bad", {"attack": True, "magic": 1,
                                     "defense": 1, "resistance": 1})],
                      [("", DEFAULT_STATS)]):
            with self.subTest(cases=cases):
                with self.assertRaises(AbilityError):
                    balance_lab(spec, cases=cases)

    def test_action_complex_ast_roundtrip_revision_and_no_ct_override(self):
        session = AuthoringSession.new(*reference_project())
        draft = AbilityDraft.create(session, "r43_combo")
        draft.set_header(
            name="Combo", profiles=["ACTION_REALTIME"], resource="stamina",
            cost=5, team="enemy", shape="diamond", min_range=0,
            max_range=4, radius=1,
            timing={"ACTION_REALTIME": {"windup": 2, "cooldown": 15}})
        expr = replace_node(draft.document["effects"][0]["formula"],
                            (), op="add")
        expr = replace_node(expr, ("right",), op="percent", amount=125)
        expr = replace_node(expr, ("right", "input"), op="stat",
                            name="attack")
        draft.edit_effect(0, kind="damage", formula=expr, element="fire",
                          status="", duration=1, scope="enemies")
        before = session.snapshot().to_dict()
        digest = digest_ability(draft.document)
        report = draft.preview(mode="ACTION_REALTIME").report
        self.assertEqual(report["impact"]["digest"], digest)
        self.assertEqual(session.snapshot().to_dict(), before)
        draft.apply()
        updated = session.snapshot().to_dict()
        self.assertEqual(updated["content"], before["content"])
        self.assertEqual(updated["project"]["extensions"]["org.drawtemp.abilities"]
                         ["data"]["abilities"][0]["effects"][0]["formula"], expr)
        session.undo()
        self.assertEqual(session.snapshot().to_dict(), before)
        session.redo()
        self.assertEqual(session.snapshot().to_dict(), updated)

        loaded = AbilityDraft.load(session, "r43_combo")
        loaded.document["name"] = "Combo (révisé)"
        loaded.preview(mode="ACTION_REALTIME")
        loaded.apply()
        self.assertEqual(
            AbilityDraft.load(session, "r43_combo").document["effects"][0]["formula"],
            expr)


if __name__ == "__main__":
    unittest.main()

"""R37.A headless contract regression tests (no implicit CT behavior change)."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from drawtemp.sdk.ai_decision import (
    AIDecisionError, evaluate_decision, new_blackboard, update_blackboard,
    validate_blackboard, validate_context,
)


def context(mode="realtime"):
    return {"schema_version": 1, "actor_id": "guard_1", "mode": mode,
            "tick": 120, "seed": 42,
            "facts": {"enemy_visible": True, "distance": 2, "hp": 20}}


def policies():
    return [
        {"id": "patrol", "action": "patrol", "base": 5,
         "when": {"enemy_visible": False}, "terms": {}},
        {"id": "retreat", "action": "flee", "base": 6,
         "when": {"enemy_visible": True}, "terms": {"hp": -1}},
        {"id": "chase", "action": "chase", "base": 3,
         "when": {"enemy_visible": True},
         "terms": {"distance": -1, "blackboard.alert": 6}},
    ]


class AIContractTests(unittest.TestCase):
    def assert_code(self, code, fn):
        with self.assertRaises(AIDecisionError) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)

    def test_schema_roundtrip_actor_and_tick_are_explicit(self):
        state = new_blackboard("guard_1")
        self.assertEqual(validate_blackboard(json.loads(json.dumps(state))), state)
        updated = update_blackboard(state, {"alert": 1, "status": "warned"},
                                    tick=119)
        self.assertEqual(state["values"], {})
        self.assertEqual(updated["values"], {"alert": 1, "status": "warned"})
        self.assertEqual(updated, json.loads(json.dumps(updated)))
        self.assertEqual(validate_context(json.loads(json.dumps(context()))),
                         context())
        self.assert_code("time_regression",
                         lambda: update_blackboard(updated, {"alert": 0}, tick=118))
        self.assertEqual(updated["values"]["alert"], 1)

    def test_explainable_guard_decision_with_deterministic_digest(self):
        board = update_blackboard(new_blackboard("guard_1"),
                                  {"alert": 1}, tick=100)
        original = deepcopy((context(), board, policies()))
        report = evaluate_decision(*original)
        self.assertEqual(report["action"], "chase")
        self.assertEqual(report["policy_id"], "chase")
        self.assertEqual(report["score"], 7)  # 3 - 2 + 6
        self.assertEqual(report["mode"], "realtime")
        self.assertFalse(report["used_fallback"])
        self.assertEqual([r["id"] for r in report["candidates"]],
                         ["chase", "patrol", "retreat"])
        self.assertEqual(report["candidates"][0]["terms"],
                         [{"fact": "blackboard.alert", "value": 1,
                           "weight": 6, "contribution": 6},
                          {"fact": "distance", "value": 2,
                           "weight": -1, "contribution": -2}])
        self.assertEqual(report["candidates"][1]["reasons"],
                         ["condition:enemy_visible"])
        self.assertEqual((context(), board, policies()), original)
        shuffled = list(reversed(policies()))
        self.assertEqual(evaluate_decision(context(), board, shuffled), report)
        self.assertEqual(evaluate_decision(context(), board, policies()), report)
        self.assertEqual(len(report["digest"]), 64)

    def test_fallback_missing_facts_and_type_equality(self):
        board = new_blackboard("guard_1")
        report = evaluate_decision(context(), board, policies())
        self.assertFalse(report["used_fallback"])
        self.assertEqual(report["action"], "flee")  # retreat has numeric hp
        # Distinguish condition mismatch from excluded missing term.
        chase = next(row for row in report["candidates"] if row["id"] == "chase")
        self.assertFalse(chase["eligible"])
        self.assertEqual(chase["reasons"],
                         ["missing_or_non_numeric:blackboard.alert"])
        all_false = [{"id": "guard", "action": "patrol", "base": 0,
                      "when": {"enemy_visible": False}, "terms": {}}]
        report = evaluate_decision(context(), board, all_false, fallback="wait")
        self.assertTrue(report["used_fallback"])
        self.assertIsNone(report["policy_id"])
        self.assertEqual(report["action"], "wait")
        # JSON equality alone would let bool True match int 1: forbid this.
        wrong_type = deepcopy(all_false)
        wrong_type[0]["when"] = {"enemy_visible": 1}
        self.assertEqual(evaluate_decision(context(), board, wrong_type)
                         ["action"], "wait")

    def test_tie_break_independent_of_policy_insertion_order_and_mode(self):
        rows = [{"id": p, "action": p, "base": 9, "when": {}, "terms": {}}
                for p in ("zeta", "alpha")]
        board = new_blackboard("guard_1")
        for mode in ("ct", "realtime"):
            first = evaluate_decision(context(mode), board, rows)
            second = evaluate_decision(context(mode), board, list(reversed(rows)))
            self.assertEqual(first, second)
            self.assertEqual(first["action"], "alpha")

    def test_rejects_forged_shapes_future_schema_and_unsafe_payload(self):
        base = context()
        invalid = [
            ("unsupported_schema", {"schema_version": True}),
            ("unsupported_schema", {"schema_version": 2}),
            ("invalid_mode", {"mode": "live"}),
            ("invalid_number", {"tick": True}),
            ("invalid_number", {"seed": -1}),
            ("invalid_id", {"actor_id": "../guard"}),
            ("invalid_shape", {"script": "eval('x')"}),
            ("fact_budget", {"facts": {"k" + str(n): n for n in range(65)}}),
            ("invalid_value", {"facts": {"data": {"exec": "unsafe"}}}),
            ("invalid_value", {"facts": {"speed": 0.1}}),
        ]
        for code, change in invalid:
            with self.subTest(change=change):
                self.assert_code(code, lambda change=change:
                                 validate_context({**base, **change}))
        self.assert_code("unsupported_schema", lambda:
                         validate_blackboard({**new_blackboard("guard_1"),
                                              "schema_version": 2}))
        self.assert_code("invalid_shape", lambda:
                         validate_blackboard({**new_blackboard("guard_1"),
                                              "payload": "eval"}))
        self.assert_code("invalid_value", lambda:
                         update_blackboard(new_blackboard("guard_1"),
                                           {"meta": []}, tick=3))

    def test_budget_scoring_and_bad_policies_fail_closed(self):
        board = new_blackboard("guard_1")
        row = {"id": "hit", "action": "attack", "base": 0,
               "when": {}, "terms": {}}
        self.assert_code("policy_budget", lambda:
                         evaluate_decision(context(), board, [row] * 65))
        self.assert_code("duplicate_policy", lambda:
                         evaluate_decision(context(), board, [row, row]))
        self.assert_code("invalid_shape", lambda:
                         evaluate_decision(context(), board,
                                           [{**row, "python": "exec"}]))
        self.assert_code("invalid_reference", lambda:
                         evaluate_decision(context(), board,
                                           [{**row, "terms": {"blackboard.": 1}}]))
        self.assert_code("invalid_number", lambda:
                         evaluate_decision(context(), board,
                                           [{**row, "terms": {"hp": True}}]))
        self.assert_code("invalid_number", lambda:
                         evaluate_decision(context(), board,
                                           [{**row, "base": float("nan")}]))
        self.assert_code("actor_mismatch", lambda:
                         evaluate_decision(context(), new_blackboard("other"),
                                           [row]))
        future = update_blackboard(board, {"known": 1}, tick=121)
        self.assert_code("future_blackboard", lambda:
                         evaluate_decision(context(), future, [row]))
        big = context()
        big["facts"] = {"v" + str(i): 1000000 for i in range(16)}
        overflow = {**row, "terms": {"v" + str(i): 1024 for i in range(16)}}
        self.assert_code("score_overflow", lambda:
                         evaluate_decision(big, board, [overflow]))

    def test_no_ui_import_and_sdk_public_alias(self):
        code = """
import sys
class DenyUI:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('tkinter', 'PySide6', 'PyQt6'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, DenyUI())
from drawtemp.sdk import evaluate_decision, new_blackboard
assert new_blackboard('guard')['schema_version'] == 1
"""
        result = subprocess.run([sys.executable, "-c", code],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

"""R37.C deterministic Behavior Tree and canonical authoring regression gates."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

from drawtemp.sdk.ai_decision import AIDecisionError, new_blackboard
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.behavior_tree import (
    BehaviorTreeDebugger, evaluate_behavior_tree, validate_behavior_tree,
)
from drawtemp.studio.ai_tree_authoring import BehaviorTreeDraft
from sporebound.advanced_ai import EXTENSION
from sporebound.game_session import GameSession
from tests_standalone.test_r37_ai_session import enable, realtime_fixture


def tree():
    return {
        "schema_version": 1, "root": "root",
        "nodes": [
            {"id": "root", "kind": "selector",
             "children": ["hunt", "rest"]},
            {"id": "hunt", "kind": "sequence",
             "children": ["see_enemy", "chase"]},
            {"id": "see_enemy", "kind": "condition",
             "fact": "enemy_visible", "equals": True},
            {"id": "chase", "kind": "action", "action": "chase"},
            {"id": "rest", "kind": "action", "action": "patrol"},
        ],
    }


def context(visible=True):
    return {"schema_version": 1, "actor_id": "guard_1",
            "mode": "realtime", "tick": 10, "seed": 42,
            "facts": {"enemy_visible": visible}}


class BehaviorTreeTests(unittest.TestCase):
    def assert_code(self, code, function):
        with self.assertRaises(AIDecisionError) as error:
            function()
        self.assertEqual(error.exception.code, code)

    def test_selector_sequence_running_action_without_execution(self):
        before = tree()
        board = new_blackboard("guard_1")
        report = evaluate_behavior_tree(context(), board, before)
        self.assertEqual(report["action"], "chase")
        self.assertEqual(report["status"], "running")
        self.assertEqual(report["visited"], 4)
        self.assertEqual([row["node_id"] for row in report["trace"]],
                         ["see_enemy", "chase", "hunt", "root"])
        self.assertEqual(report["selected_node"], "chase")
        self.assertFalse(report["used_fallback"])
        self.assertEqual(len(report["digest"]), 64)
        self.assertEqual(report, evaluate_behavior_tree(context(), board, before))
        reordered = deepcopy(before)
        reordered["nodes"].reverse()
        self.assertEqual(report, evaluate_behavior_tree(context(), board, reordered))
        self.assertEqual(before, tree())  # tick did not edit authored nodes
        self.assertEqual(board["values"], {})

    def test_false_missing_and_typed_conditions(self):
        board = new_blackboard("guard_1")
        false_report = evaluate_behavior_tree(context(False), board, tree())
        self.assertEqual(false_report["action"], "patrol")
        self.assertEqual(false_report["trace"][0]["reason"],
                         "mismatch:enemy_visible")
        missing = context()
        missing["facts"] = {}
        report = evaluate_behavior_tree(missing, board, tree())
        self.assertEqual(report["trace"][0]["reason"],
                         "missing_fact:enemy_visible")
        unexpected = tree()
        unexpected["nodes"][2]["equals"] = 1
        self.assertEqual(
            evaluate_behavior_tree(context(True), board, unexpected)["action"],
            "patrol")  # bool True must not match int 1

    def test_inverter_and_no_action_fallback(self):
        document = {
            "schema_version": 1, "root": "not_enemy",
            "nodes": [
                {"id": "not_enemy", "kind": "decorator",
                 "op": "invert", "child": "enemy"},
                {"id": "enemy", "kind": "condition",
                 "fact": "enemy_visible", "equals": True},
            ],
        }
        report = evaluate_behavior_tree(context(False), new_blackboard("guard_1"),
                                        document, fallback="wait")
        self.assertEqual(report["status"], "success")
        self.assertTrue(report["used_fallback"])
        self.assertEqual(report["action"], "wait")
        self.assertEqual(report["trace"][-1]["reason"], "invert:failure")

    def test_debugger_step_and_breakpoint_are_read_only(self):
        report = evaluate_behavior_tree(
            context(), new_blackboard("guard_1"), tree())
        debugger = BehaviorTreeDebugger(report, breakpoints=("chase",))
        self.assertEqual(debugger.state()["cursor"], 0)
        self.assertEqual(debugger.step()["node_id"], "see_enemy")
        stop = debugger.resume()
        self.assertTrue(stop["paused"])
        self.assertEqual(stop["event"]["node_id"], "chase")
        self.assertEqual(debugger.resume()["paused"], False)
        self.assertTrue(debugger.state()["complete"])
        self.assertIsNone(debugger.step())
        self.assertEqual(report["action"], "chase")

    def test_reject_malformed_cycles_orphan_shared_and_budget(self):
        specimens = [
            ("unsupported_schema", lambda x: x.update(schema_version=True)),
            ("invalid_tree", lambda x: x.update(extra="script")),
            ("duplicate_node", lambda x: x["nodes"].append(
                deepcopy(x["nodes"][0]))),
            ("unknown_child", lambda x: x["nodes"][0]["children"].append("ghost")),
            ("invalid_tree_node", lambda x: x["nodes"][2].update(eval="unsafe")),
            ("unsupported_node", lambda x: x["nodes"][2].update(kind="python")),
            ("invalid_tree", lambda x: x["nodes"][1]["children"].append("rest")),
            ("invalid_tree", lambda x: x["nodes"][0]["children"].append("root")),
            ("tree_budget", lambda x: x["nodes"].extend([
                {"id": "extra" + str(i), "kind": "action",
                 "action": "wait"} for i in range(65)])),
        ]
        for code, edit in specimens:
            candidate = tree()
            edit(candidate)
            with self.subTest(code=code):
                self.assert_code(code, lambda: validate_behavior_tree(candidate))
        nested = {"schema_version": 1, "root": "root", "nodes": []}
        for i in range(16):
            ident = "root" if i == 0 else "node" + str(i)
            nxt = "node" + str(i + 1)
            nested["nodes"].append(
                {"id": ident, "kind": "decorator", "op": "invert", "child": nxt})
        nested["nodes"].append(
            {"id": "node16", "kind": "action", "action": "wait"})
        self.assert_code("tree_budget", lambda: validate_behavior_tree(nested))

    def test_project_tree_session_preview_and_legacy_policy_untouched(self):
        content, project = realtime_fixture()
        policies = deepcopy(project.extensions[EXTENSION]["data"]["agents"][0]["policies"])
        original = GameSession.new(content, project, "main", seed=19)
        self.assertIn("candidates", original.ai_decision_preview("merchant"))
        editor = AuthoringSession.new(content, project)
        draft = BehaviorTreeDraft(editor, "merchant")
        self.assertEqual(draft.document()["root"], "root")
        # Construct selector: sequence(condition activity=sleep, rest action)
        # followed by default wait action.
        sequence = draft.add("root", "sequence")
        condition = draft.add(sequence, "condition",
                              fact="activity", equals="sleep")
        draft.reorder(condition, -1)
        draft.edit(
            next(n["id"] for n in draft.document()["nodes"]
                 if n["id"].startswith("wait") and n["id"] != "wait1"),
            action="rest")
        draft.reorder(sequence, -1)
        self.assertEqual(editor.revision, 0)
        old_tree = draft.document()
        draft.apply()
        self.assertEqual(editor.revision, 1)
        manifest = editor.snapshot().to_dict()["project"]
        saved_agent = manifest["extensions"][EXTENSION]["data"]["agents"][0]
        self.assertEqual(saved_agent["tree"], validate_behavior_tree(old_tree))
        self.assertNotIn("policies", saved_agent)
        from sporebound.game_project import GameProject
        modified_project = GameProject.from_dict(manifest, content)
        runtime = GameSession.new(content, modified_project, "main", seed=19)
        report = runtime.ai_decision_preview("merchant")
        self.assertEqual(report["action"], "rest")
        self.assertEqual(report["selected_node"], next(
            n["id"] for n in old_tree["nodes"]
            if n.get("action") == "rest"))
        self.assertEqual(report, runtime.ai_decision_preview("merchant"))
        editor.undo()
        restored_agent = editor.snapshot().to_dict()["project"][
            "extensions"][EXTENSION]["data"]["agents"][0]
        self.assertEqual(restored_agent["policies"], policies)
        self.assertNotIn("tree", restored_agent)
        editor.redo()
        self.assertEqual(editor.snapshot().to_dict()["project"], manifest)

    def test_draft_rejects_mutation_without_partial_change_and_stale(self):
        content, project = realtime_fixture()
        editor = AuthoringSession.new(content, project)
        draft = BehaviorTreeDraft(editor, "merchant")
        original = draft.document()
        for failure in (lambda: draft.remove("root"),
                        lambda: draft.edit("wait1", action="not-an-id"),
                        lambda: draft.add("wait1", "action"),
                        lambda: draft.reorder("wait1", -1)):
            with self.assertRaises(ValueError):
                failure()
            self.assertEqual(draft.document(), original)
        wrapped = draft.wrap_inverter("wait1")
        self.assertEqual(draft.document()["nodes"][-1]["id"], wrapped)
        validate_behavior_tree(draft.document())
        unrelated = editor.preview_project(
            lambda p: {**p, "subtitle": "Edited elsewhere"})
        editor.apply(unrelated)
        with self.assertRaises(ValueError):
            draft.apply()

    def test_headless_import_excludes_qt(self):
        source = """
import sys
class DenyUI:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6','PyQt6','tkinter'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, DenyUI())
from drawtemp.sdk.behavior_tree import validate_behavior_tree
from drawtemp.studio.ai_tree_authoring import BehaviorTreeDraft
"""
        result = subprocess.run(
            [sys.executable, "-c", source],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

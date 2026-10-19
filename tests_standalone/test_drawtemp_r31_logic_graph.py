"""R31.A — safe visual graph contracts and canonical R9 integration."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import subprocess
import sys
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.logic_graph import (
    LogicGraphError, NAMESPACE, apply_graph, compile_r9_trigger,
    graphs_from_project, preview_graph, validate_graph,
)
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from sporebound.event_composer import condition


def lever_graph():
    return {
        "schema_version": 1,
        "id": "lever",
        "mission_id": MISSION,
        "entry": "interact",
        "nodes": [
            {"id": "interact", "kind": "event",
             "params": {"kind": "interact", "object_id": "lever"}},
            {"id": "message", "kind": "action",
             "params": {"kind": "message", "text": "La porte s'ouvre"}},
            {"id": "danger", "kind": "action",
             "params": {"kind": "hazard", "pos": [1, 3], "amount": 2}},
        ],
        "edges": [
            {"from": "interact", "out": "next", "to": "message", "in": "flow"},
            {"from": "message", "out": "next", "to": "danger", "in": "flow"},
        ],
    }


class LogicGraphContractTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.session = AuthoringSession.new(self.content, self.project)

    def test_compiles_by_flow_edges_not_display_order(self):
        graph = lever_graph()
        first = compile_r9_trigger(graph)
        graph["nodes"].reverse()
        graph["edges"].reverse()
        self.assertEqual(first, compile_r9_trigger(graph))
        self.assertEqual(first["id"], "r31_lever")
        self.assertEqual(first["condition"], "interact")
        self.assertEqual(first["actions"], [
            {"kind": "message", "text": "La porte s'ouvre"},
            {"kind": "hazard", "pos": [1, 3], "amount": 2},
        ])
        graph["nodes"][0]["params"]["amount"] = 55
        self.assertEqual(first["actions"][1]["amount"], 2)

    def test_rejects_invalid_graphs_and_untrusted_code(self):
        invalid = [
            ("unsupported_schema", lambda g: g.update(schema_version=4)),
            ("unsupported_schema", lambda g: g.update(schema_version=True)),
            ("invalid_shape", lambda g: g.update(shell="exec")),
            ("invalid_id", lambda g: g.update(id="../../unsafe")),
            ("invalid_entry", lambda g: g.update(entry="message")),
            ("unsupported_node", lambda g: g["nodes"][1].update(kind="eval")),
            ("unsupported_node", lambda g: g["nodes"][1]["params"].update(kind="python")),
            ("invalid_parameter", lambda g: g["nodes"][1]["params"].update(text="")),
            ("invalid_parameter", lambda g: g["nodes"][2]["params"].update(amount=True)),
            ("invalid_shape", lambda g: g["edges"][0].update(script="!")),
            ("port_type", lambda g: g["edges"][0].update(out="boolean")),
            ("dangling_edge", lambda g: g["edges"][0].update(to="ghost")),
            ("multiple_connections", lambda g: g["edges"][1].update({"from": "interact"})),
            ("cycle", lambda g: g["edges"][1].update({"from": "danger"})),
        ]
        for code, mutate in invalid:
            with self.subTest(code=code):
                graph = lever_graph()
                mutate(graph)
                with self.assertRaises(LogicGraphError) as raised:
                    validate_graph(graph)
                self.assertEqual(raised.exception.code, code)
        cyclic = lever_graph()
        cyclic["edges"][0]["from"] = "danger"
        cyclic["edges"][1]["to"] = "interact"
        with self.assertRaises(LogicGraphError):
            validate_graph(cyclic)

    def test_tick_requires_int_not_bool_and_bounded(self):
        graph = lever_graph()
        graph["nodes"][0]["params"] = {"kind": "tick", "tick": 10}
        self.assertEqual(compile_r9_trigger(graph)["value"], 10)
        graph["nodes"][0]["params"]["tick"] = True
        with self.assertRaises(LogicGraphError):
            compile_r9_trigger(graph)
        graph["nodes"][0]["params"]["tick"] = 1000001
        with self.assertRaises(LogicGraphError):
            compile_r9_trigger(graph)

    def test_atomic_preview_undo_redo_and_native_r9_preview(self):
        original = self.session.snapshot().to_dict()
        plan = preview_graph(self.session, lever_graph())
        self.assertEqual(self.session.snapshot().to_dict(), original)
        self.session.apply(plan)
        state = self.session.snapshot().to_dict()
        self.assertEqual(self.session.revision, 1)
        self.assertEqual(graphs_from_project(state["project"]), [lever_graph()])
        event = EventStudio(self.session).event(MISSION, "r31_lever")
        self.assertEqual(event, compile_r9_trigger(lever_graph()))
        outcome = EventStudio(self.session).preview(MISSION, "r31_lever")
        self.assertTrue(outcome["report"]["isolated"])
        self.assertEqual(outcome["report"]["outcome"], "applied")
        self.session.undo()
        self.assertEqual(self.session.snapshot().to_dict()["content"], original["content"])
        self.assertEqual(self.session.snapshot().to_dict()["project"], original["project"])
        self.session.redo()
        self.assertEqual(self.session.snapshot().to_dict()["content"], state["content"])
        self.assertEqual(self.session.snapshot().to_dict()["project"], state["project"])

    def test_graph_edits_one_transaction_and_stale_previews_rejected(self):
        apply_graph(self.session, lever_graph())
        plan = preview_graph(self.session, {
            **lever_graph(),
            "nodes": [{**n, "params": {"kind": "message", "text": "Modifié"}}
                      if n["id"] == "message" else n for n in lever_graph()["nodes"]],
        })
        self.session.undo()
        with self.assertRaises(AuthoringError) as raised:
            self.session.apply(plan)
        self.assertEqual(raised.exception.code, "stale_revision")
        self.session.redo()
        self.session.apply(preview_graph(self.session, {
            **lever_graph(),
            "nodes": [{**n, "params": {"kind": "message", "text": "Modifié"}}
                      if n["id"] == "message" else n for n in lever_graph()["nodes"]],
        }))
        self.assertEqual(EventStudio(self.session).event(MISSION, "r31_lever")
                         ["actions"][0]["text"], "Modifié")

    def test_fail_closed_collision_and_no_partial_commit(self):
        native = EventStudio(self.session)
        native.create(MISSION, "r31_lever", condition("tick", tick=0),
                      [{"kind": "message", "text": "Native R9"}])
        before = self.session.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            apply_graph(self.session, lever_graph())
        self.assertEqual(self.session.snapshot().to_dict(), before)

        self.session.undo()
        apply_graph(self.session, lever_graph())
        native.set_condition(MISSION, "r31_lever", condition("tick", tick=0))
        before = self.session.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            apply_graph(self.session, lever_graph())
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_save_reload_legacy_project_and_graph_metadata(self):
        legacy = self.session.snapshot().to_dict()
        self.assertEqual(graphs_from_project(legacy["project"]), [])
        apply_graph(self.session, lever_graph())
        with TemporaryDirectory() as directory:
            path = Path(directory) / "logic.json"
            self.session.save_as(path)
            restored = AuthoringSession.open(path)
            self.assertEqual(graphs_from_project(restored.snapshot().to_dict()
                                                 ["project"]), [lever_graph()])
            self.assertIn(NAMESPACE, restored.snapshot().to_dict()
                          ["project"]["extensions"])
            self.assertEqual(EventStudio(restored).event(MISSION, "r31_lever"),
                             compile_r9_trigger(lever_graph()))

    def test_headless_contract_does_not_import_qt(self):
        source = """
import sys
class NoQt:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6', 'PyQt6', 'tkinter'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, NoQt())
from drawtemp.sdk.logic_graph import validate_graph, compile_r9_trigger
"""
        result = subprocess.run([sys.executable, "-c", source],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

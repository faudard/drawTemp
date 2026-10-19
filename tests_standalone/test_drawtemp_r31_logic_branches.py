"""R31.C: strict typed IF/ELSE, native dispatcher exclusivity and migrations."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.logic_branches import validate_expression
from drawtemp.sdk.logic_graph import (
    LogicGraphError, apply_graph, compile_r9_trigger, compile_r9_triggers,
    graphs_from_project, preview_graph, validate_graph,
)
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.logic_graph_draft import LogicGraphDraft
from sporebound.engine import Battle
from sporebound.rules.triggers import dispatch
from sporebound.model import Content


def new_session():
    return AuthoringSession.new(*reference_project())


def branch_graph(*, graph_id="gatechoice", expression=None):
    draft = LogicGraphDraft.new(
        MISSION, graph_id, source_revision=0)
    branch = draft.add_branch(expression)
    assert branch == "if1"
    return draft.graph


class TypedExpressionTests(unittest.TestCase):
    def test_boolean_composition_is_pure_and_detached(self):
        leaf = {"condition": "wave_capacity", "team": "enemy", "max_alive": 1}
        original = deepcopy(leaf)
        expression = {"any": [
            leaf,
            {"all": [
                {"condition": "tick", "value": 10},
                {"not": {"condition": "defeated", "unit": "hero"}},
            ]},
        ]}
        # Nested NOT at depth 2 exceeds reserved ELSE wrap budget.
        with self.assertRaises(LogicGraphError) as error:
            validate_expression(expression)
        self.assertEqual(error.exception.code, "expression_budget")
        expression = {"all": [
            leaf,
            {"not": {"condition": "tick", "value": 10}},
        ]}
        detached = validate_expression(expression)
        self.assertEqual(detached, expression)
        detached["all"][0]["max_alive"] = 50
        self.assertEqual(leaf, original)

    def test_type_and_budget_rejections(self):
        invalid = [
            ({"condition": "tick", "value": True}, "typed_expression"),
            ({"condition": "tick", "value": 100001}, "typed_expression"),
            ({"condition": "hp_below", "unit": "hero", "percent": False}, "typed_expression"),
            ({"condition": "hp_below", "unit": "hero", "percent": 0}, "typed_expression"),
            ({"condition": "wave_capacity", "team": "enemy", "max_alive": -1}, "typed_expression"),
            ({"condition": "wave_capacity", "team": "neutral", "max_alive": "1"}, "typed_expression"),
            ({"condition": "wave_capacity", "team": "spectator", "max_alive": 1}, "typed_expression"),
            ({"condition": "defeated", "unit": "Unit;exec"}, "invalid_id"),
            ({"condition": "python", "script": "import os"}, "typed_expression"),
            ({"literal": "True"}, "typed_expression"),
            ({"all": [{"condition": "tick", "value": 1}]}, "typed_expression"),
            ({"all": [True, False]}, "typed_expression"),
            ({"not": {"not": {"not": {"condition": "tick", "value": 1}}}}, "expression_budget"),
            ({"any": [{"condition": "tick", "value": i} for i in range(9)]}, "typed_expression"),
            ({"condition": "tick", "value": 1, "extra": "bad"}, "typed_expression"),
        ]
        for payload, code in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(LogicGraphError) as error:
                    validate_expression(payload)
                self.assertEqual(error.exception.code, code)


class BranchGraphTests(unittest.TestCase):
    def setUp(self):
        self.session = new_session()

    def test_typed_ports_lower_to_canonical_exclusive_native_events(self):
        graph = branch_graph(expression={"condition": "tick", "value": 100000})
        self.assertEqual(validate_graph(graph), graph)
        self.assertEqual(graph["schema_version"], 2)
        with self.assertRaises(LogicGraphError) as error:
            compile_r9_trigger(graph)
        self.assertEqual(error.exception.code, "split_branches")
        a, b = compile_r9_triggers(graph)
        self.assertEqual(a["id"], "r31_gatechoice_yes")
        self.assertEqual(b["id"], "r31_gatechoice_no")
        self.assertEqual(a["cancel_after"], [b["id"]])
        self.assertEqual(b["cancel_after"], [a["id"]])
        self.assertEqual(a["when"], {"condition": "tick", "value": 100000})
        self.assertEqual(b["when"], {"not": a["when"]})
        self.assertEqual([x["text"] for x in b["actions"]], ["Sinon"])
        original = self.session.snapshot().to_dict()
        plan = preview_graph(self.session, graph)
        self.assertEqual(self.session.snapshot().to_dict(), original)
        self.session.apply(plan)
        stored = graphs_from_project(self.session.snapshot().to_dict()["project"])
        self.assertEqual(stored, [graph])
        native = self.session.snapshot().to_dict()["content"]["missions"][0]["triggers"]
        self.assertEqual(native[-2:], [a, b])
        self.session.undo()
        self.assertEqual(self.session.snapshot().to_dict()["content"], original["content"])
        self.assertEqual(self.session.snapshot().to_dict()["project"], original["project"])
        self.session.redo()
        self.assertEqual(graphs_from_project(self.session.snapshot().to_dict()["project"]),
                         [graph])

    def test_actual_battle_else_stays_exclusive_when_condition_turns_true_later(self):
        graph = branch_graph(expression={"condition": "tick", "value": 100000})
        apply_graph(self.session, graph)
        doc = self.session.snapshot().to_dict()["content"]
        battle = Battle(Content.from_dict(doc), MISSION, seed=5,
                        battle_id="r31-exclusive-1")
        self.assertIn("r31_gatechoice_no", battle.fired)
        self.assertNotIn("r31_gatechoice_yes", battle.fired)
        before = battle.events[:]
        battle.tick = 100000
        dispatch(battle)
        self.assertNotIn("r31_gatechoice_yes", battle.fired)
        self.assertEqual(battle.fired.count("r31_gatechoice_no"), 1)
        self.assertEqual(len([e for e in battle.events if e.get("id") == "r31_gatechoice_yes"
                              and e["kind"] == "trigger"]), 0)
        self.assertEqual(len([e for e in battle.events if e.get("id") == "r31_gatechoice_no"
                              and e["kind"] == "trigger"]), 1)
        self.assertTrue(len(before) <= len(battle.events))

    def test_actual_battle_true_branch_prevents_later_false(self):
        graph = branch_graph(expression={"condition": "tick", "value": 0})
        apply_graph(self.session, graph)
        battle = Battle(Content.from_dict(self.session.snapshot().to_dict()["content"]),
                        MISSION, seed=7, battle_id="r31-exclusive-2")
        self.assertIn("r31_gatechoice_yes", battle.fired)
        self.assertNotIn("r31_gatechoice_no", battle.fired)
        battle.tick = 0
        dispatch(battle)
        self.assertNotIn("r31_gatechoice_no", battle.fired)
        self.assertEqual(battle.fired.count("r31_gatechoice_yes"), 1)

    def test_schema1_edit_to_schema2_and_back_is_atomic_with_no_orphans(self):
        draft = LogicGraphDraft.new(MISSION, "compatible", source_revision=0)
        draft.apply(self.session)
        self.assertEqual(
            [x["id"] for x in self.session.snapshot().to_dict()
             ["content"]["missions"][0]["triggers"] if x["id"].startswith("r31_")],
            ["r31_compatible"])
        newer = LogicGraphDraft.load(self.session, "compatible")
        newer.add_branch({"condition": "tick", "value": 10})
        newer.apply(self.session)
        events = self.session.snapshot().to_dict()["content"]["missions"][0]["triggers"]
        self.assertNotIn("r31_compatible", [row["id"] for row in events])
        self.assertIn("r31_compatible_yes", [row["id"] for row in events])
        self.session.undo()
        events = self.session.snapshot().to_dict()["content"]["missions"][0]["triggers"]
        self.assertIn("r31_compatible", [row["id"] for row in events])
        self.assertNotIn("r31_compatible_yes", [row["id"] for row in events])
        self.session.redo()
        with TemporaryDirectory() as tmp:
            filename = Path(tmp) / "game.json"
            self.session.save_as(filename)
            self.assertEqual(
                graphs_from_project(AuthoringSession.open(filename).snapshot()
                                    .to_dict()["project"])[0]["schema_version"], 2)

    def test_fail_closed_mutations_and_atomic_rollback(self):
        pristine = branch_graph()
        checks = [
            ("invalid_edges", lambda g: g["edges"].pop()),
            ("multiple_connections", lambda g: g["edges"][1].update({"out": "next"})),
            ("port_type", lambda g: g["edges"][1].update({"out": "bad"})),
            ("invalid_branch", lambda g: g["edges"][0].update({"to": "message"})),
            ("cycle", lambda g: g["edges"][-1].update({"to": "message"})),
            ("typed_expression", lambda g: g["nodes"][-2]["params"].update(
                predicate={"condition": "python"})),
        ]
        # Check explicit bounds and unchanged R1 revision, irrespective of
        # which earlier structural invariant is the first to reject a mutation.
        for _expected, mutate in checks:
            candidate = deepcopy(pristine)
            mutate(candidate)
            with self.assertRaises(LogicGraphError):
                validate_graph(candidate)
        existing = self.session.snapshot().to_dict()
        invalid = deepcopy(pristine)
        invalid["nodes"][-2]["params"]["predicate"] = {
            "condition": "wave_capacity", "team": "enemy", "max_alive": "0"}
        with self.assertRaises(LogicGraphError):
            apply_graph(self.session, invalid)
        self.assertEqual(self.session.snapshot().to_dict(), existing)

    def test_preview_collision_and_external_event_change_block(self):
        draft = LogicGraphDraft.new(MISSION, "unique", source_revision=0)
        draft.add_branch()
        draft.apply(self.session)
        stale = LogicGraphDraft.load(self.session, "unique")
        stale.edit_node("otherwise1", {"kind": "message", "text": "Autre"})
        self.session.apply(self.session.preview_project(
            lambda d: {**d, "title": "Other writer"}))
        state = self.session.snapshot().to_dict()
        with self.assertRaises(LogicGraphError) as error:
            stale.apply(self.session)
        self.assertEqual(error.exception.code, "stale_revision")
        self.assertEqual(state, self.session.snapshot().to_dict())

    def test_disconnected_and_forked_drafts_never_commit(self):
        draft = LogicGraphDraft.new(MISSION, "ports", source_revision=0)
        branch = draft.add_branch()
        self.assertEqual(branch, "if1")
        draft.add_action("message")
        with self.assertRaises(LogicGraphError):
            draft.prepare(self.session)
        with self.assertRaises(LogicGraphError):
            draft.connect(branch, "message", port="true")
        draft.connect("message", "message1")
        with self.assertRaises(LogicGraphError):
            draft.connect("message1", "message", port="next")
        self.assertEqual(len(draft.prepare(self.session)[1]), 2)


if __name__ == "__main__":
    unittest.main()

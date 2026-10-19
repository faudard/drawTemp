"""R31.F: typed battle-local variables on real R9 registry, replay and authoring."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.logic_graph import LogicGraphError, compile_r9_triggers, graphs_from_project
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.logic_graph_draft import LogicGraphDraft
from drawtemp.studio.logic_debugger import LogicGraphDebugger
from sporebound.engine import Battle
from sporebound.logic_variables import (
    has_logic_variables, install_logic_variable_rules, variables_from_journal,
)
from sporebound.model import Content, RuleError
from sporebound.rules import default_rules
from sporebound.tactical_rpg3 import authored_rules_for_document


def new_session():
    return AuthoringSession.new(*reference_project())


def bool_graph():
    draft = LogicGraphDraft.new(MISSION, "bool_vars", source_revision=0)
    identifier = draft.add_variable_after("message", "r31_gate_open", value=True)
    draft.add_check_after(identifier, "r31_gate_open", value=True)
    return draft


def integer_graph():
    draft = LogicGraphDraft.new(MISSION, "int_vars", source_revision=0)
    set_id = draft.add_variable_after("message", "r31_score", value=7)
    add_id = draft.add_variable_after(
        set_id, "r31_score", mode="add", value=4)
    draft.add_check_after(add_id, "r31_score", operator="gte", value=11)
    return draft


class TypedVariableTests(unittest.TestCase):
    def test_boolean_set_check_compiles_and_replays_on_original_dispatcher(self):
        session = new_session()
        graph = bool_graph()
        compiled = compile_r9_triggers(graph.graph)
        self.assertEqual(graph.graph["schema_version"], 4)
        self.assertEqual(len(compiled), 2)
        self.assertEqual(compiled[0]["actions"][-1],
                         {"kind": "logic_set", "name": "r31_gate_open", "value": True})
        self.assertEqual(compiled[1]["when"], {
            "condition": "logic_compare", "name": "r31_gate_open",
            "operator": "eq", "value": True})
        before = session.snapshot().to_dict()
        graph.apply(session)
        state = session.snapshot().to_dict()
        self.assertEqual(graphs_from_project(state["project"]), [graph.document()])
        raw = state["content"]
        self.assertTrue(has_logic_variables(raw))
        rules = authored_rules_for_document(raw)
        self.assertIn("logic_set", rules.trigger_actions)
        self.assertIn("logic_compare", rules.trigger_conditions)
        content = Content.from_dict(raw, rules=rules)
        battle = Battle(content, MISSION, seed=31, battle_id="r31-typed-bool")
        self.assertEqual(variables_from_journal(battle), {"r31_gate_open": True})
        self.assertIn("r31_bool_vars_s0", battle.fired)
        self.assertIn("r31_bool_vars_s1", battle.fired)
        recorded = battle.recording()
        restored = Battle.replay(recorded)
        self.assertEqual(restored.digest(), battle.digest())
        self.assertEqual(variables_from_journal(restored),
                         variables_from_journal(battle))
        self.assertEqual(restored.rules.manifest(), battle.rules.manifest())
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "variables.json"
            session.save_as(path)
            reopened = AuthoringSession.open(path)
            self.assertEqual(graphs_from_project(
                reopened.snapshot().to_dict()["project"]), [graph.document()])
        session.undo()
        self.assertEqual(session.snapshot().to_dict()["content"], before["content"])
        session.redo()
        self.assertEqual(session.snapshot().to_dict()["content"], state["content"])

    def test_integer_assignment_increment_compare_and_detached_debug(self):
        session = new_session()
        graph = integer_graph()
        graph.apply(session)
        raw = session.snapshot().to_dict()["content"]
        battle = Battle(Content.from_dict(
            raw, rules=authored_rules_for_document(raw)),
            MISSION, seed=19, battle_id="r31-int")
        self.assertEqual(variables_from_journal(battle), {"r31_score": 11})
        self.assertEqual([row["value"] for row in battle.events
                          if row["kind"] == "logic_variable"],
                         [7, 11])
        self.assertEqual(Battle.replay(battle.recording()).digest(), battle.digest())
        before = session.snapshot().to_dict()
        debugger = LogicGraphDebugger(session, "int_vars")
        report = debugger.report()["report"]
        self.assertEqual(report["battle_variables"], {})
        self.assertEqual(report["variable_scope"], "battle")
        debugger.step()
        self.assertEqual(debugger.report()["report"]["battle_variables"],
                         {"r31_score": 11})
        self.assertEqual(session.snapshot().to_dict(), before)

    def test_game_session_checkpoint_restores_battle_variable_journal(self):
        from sporebound.game_session import GameSession
        session = new_session()
        bool_graph().apply(session)
        snap = session.snapshot().to_dict()
        raw = snap["content"]
        content = Content.from_dict(raw)
        from sporebound.game_project import GameProject
        project = GameProject.from_dict(snap["project"], content)
        campaign_id = project.campaigns[0]["id"]
        game = GameSession(content, project, campaign_id, seed=14)
        # Complete the reference project's opening story dialogue before combat.
        if game.active_scene() is not None:
            game.choose_story_option("enter")
        battle = game.start_mission(MISSION)
        self.assertIsNotNone(battle)
        self.assertEqual(variables_from_journal(game.battle),
                         {"r31_gate_open": True})
        checkpoint = game.recording()
        restored = GameSession.from_recording(checkpoint, content, project)
        self.assertEqual(variables_from_journal(restored.battle),
                         {"r31_gate_open": True})
        self.assertEqual(restored.recording(), checkpoint)
        self.assertEqual(game.rules.manifest(), restored.rules.manifest())

    def test_nonmatching_predicate_cannot_enter_second_stage(self):
        session = new_session()
        draft = LogicGraphDraft.new(MISSION, "false_gate", source_revision=0)
        written = draft.add_variable_after("message", "r31_door", value=False)
        draft.add_check_after(written, "r31_door", value=True)
        draft.apply(session)
        data = session.snapshot().to_dict()["content"]
        b = Battle(Content.from_dict(
            data, rules=authored_rules_for_document(data)),
            MISSION, seed=1, battle_id="false-gate")
        self.assertIn("r31_false_gate_s0", b.fired)
        self.assertNotIn("r31_false_gate_s1", b.fired)
        self.assertEqual(variables_from_journal(b), {"r31_door": False})

    def test_legacy_rules_and_manifest_are_unchanged(self):
        session = new_session()
        raw = session.snapshot().to_dict()["content"]
        self.assertFalse(has_logic_variables(raw))
        self.assertEqual(authored_rules_for_document(raw).manifest(),
                         default_rules().manifest())
        self.assertNotIn("logic_set", default_rules().trigger_actions)
        self.assertNotIn("logic_compare", default_rules().trigger_conditions)

    def test_invalid_names_types_and_operators_fail_without_session_changes(self):
        session = new_session()
        initial = session.snapshot().to_dict()
        values = [(None, True), ("admin", True), ("r31_x", "eval"),
                  ("r31_x", 1000001), ("r31_x", -1000001)]
        for name, value in values:
            draft = LogicGraphDraft.new(
                MISSION, "failed", source_revision=session.revision)
            with self.subTest(name=name, value=value):
                with self.assertRaises((LogicGraphError, RuleError, ValueError)):
                    draft.add_variable_after("message", name, value=value)
        draft = LogicGraphDraft.new(MISSION, "comparison", source_revision=0)
        with self.assertRaises((LogicGraphError, RuleError)):
            draft.add_check_after(
                "message", "r31_bool", operator="gte", value=True)
        with self.assertRaises((LogicGraphError, RuleError)):
            draft.add_check_after(
                "message", "r31_bool", operator="eval", value=1)
        self.assertEqual(session.snapshot().to_dict(), initial)

    def test_boolean_add_and_integer_overflow_fail_closed(self):
        from sporebound.logic_variables import add_variable
        session = new_session()
        draft = bool_graph()
        draft.apply(session)
        raw = session.snapshot().to_dict()["content"]
        battle = Battle(Content.from_dict(raw, rules=authored_rules_for_document(raw)),
                        MISSION, seed=77, battle_id="no-bool-add")
        old = deepcopy(battle.events)
        with self.assertRaises(RuleError):
            add_variable(battle, {"kind": "logic_add", "name": "r31_gate_open",
                                  "amount": 1})
        self.assertEqual(old, battle.events)
        draft = LogicGraphDraft.new(MISSION, "max_int", source_revision=0)
        draft.add_variable_after("message", "r31_number", value=1000000)
        fresh = new_session()
        draft.apply(fresh)  # assignment of the maximal signed value is valid
        overflowing = LogicGraphDraft.load(fresh, "max_int")
        overflowing.add_variable_after(
            "variable1", "r31_number", mode="add", value=1)
        overflowing.apply(fresh)
        raw = fresh.snapshot().to_dict()["content"]
        content = Content.from_dict(raw)
        with self.assertRaises(RuleError):
            Battle(content, MISSION, seed=11, battle_id="overflow-guard")

    def test_revision_stale_breaks_debug_after_undo(self):
        session = new_session()
        bool_graph().apply(session)
        debugger = LogicGraphDebugger(session, "bool_vars")
        session.undo()
        from drawtemp.sdk.authoring import AuthoringError
        with self.assertRaises(AuthoringError) as error:
            debugger.step()
        self.assertEqual(error.exception.code, "stale_revision")


if __name__ == "__main__":
    unittest.main()

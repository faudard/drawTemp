"""R31.D: native EventDebugger projection, not a competing game interpreter."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.logic_graph import LogicGraphError, graphs_from_project
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from drawtemp.studio.logic_debugger import LogicGraphDebugger
from drawtemp.studio.logic_graph_draft import LogicGraphDraft
from sporebound.event_composer import condition


def session_with_graph(*, branched=False, predicate=None, graph_id="debug"):
    session = AuthoringSession.new(*reference_project())
    draft = LogicGraphDraft.new(MISSION, graph_id, source_revision=0)
    if branched:
        draft.add_branch(predicate or {"condition": "tick", "value": 0})
    draft.apply(session)
    return session, draft.document()


class LogicDebugSessionTests(unittest.TestCase):
    def test_linear_graph_one_event_pre_effect_breakpoint_and_action_trace(self):
        session, graph = session_with_graph()
        snapshot = session.snapshot().to_dict()
        controller = LogicGraphDebugger(session, "debug", scenario="initial", tick=0)
        initial = controller.report()
        self.assertTrue(initial["report"]["isolated"])
        self.assertIsNone(initial["report"]["replay_verified"])
        self.assertEqual(initial["report"]["step_granularity"], "native_trigger")
        self.assertEqual(initial["report"]["fired_ids"], [])
        controller.breakpoint("start")
        pending = controller.resume()["report"]
        self.assertEqual(pending["paused_on"], "r31_debug")
        self.assertEqual(pending["paused_node"], "start")
        self.assertEqual(pending["fired_ids"], [])
        event = controller.inspect("start")
        self.assertEqual(event["native_events"][0]["event_id"], "r31_debug")
        self.assertTrue(event["native_events"][0]["condition_passed"])
        assert controller.inspect("message")["action"]["kind"] == "message"
        with self.assertRaises(LogicGraphError) as error:
            controller.breakpoint("message")
        self.assertEqual(error.exception.code, "breakpoint_granularity")
        fired = controller.step()["report"]
        self.assertEqual(fired["fired_ids"], ["r31_debug"])
        self.assertEqual(fired["node_states"]["message"], "executed")
        self.assertEqual(fired["timeline"][0]["node_ids"], ["message"])
        self.assertEqual(fired["timeline"][0]["scope"], "whole_native_trigger")
        self.assertEqual(snapshot, session.snapshot().to_dict(),
                         "Debug must NEVER mutate real AuthoringSession")

    def test_if_else_both_arms_visible_and_exclusive_under_real_dispatch(self):
        session, graph = session_with_graph(branched=True)
        snapshot = session.snapshot().to_dict()
        controller = LogicGraphDebugger(session, "debug", tick=0)
        state = controller.report()["report"]
        self.assertEqual(state["chain_ids"], ["r31_debug_yes", "r31_debug_no"])
        self.assertEqual(len(state["native_states"]), 2)
        controller.breakpoint("if1")
        breakpoint = controller.resume()["report"]
        self.assertEqual(breakpoint["paused_on"], "r31_debug_yes")
        self.assertEqual(breakpoint["paused_node"], "if1")
        self.assertFalse(breakpoint["timeline"])
        fired = controller.step()["report"]
        self.assertEqual(fired["fired_ids"], ["r31_debug_yes"])
        self.assertEqual(fired["native_states"]["r31_debug_no"]["state"],
                         "cancelled")
        self.assertEqual(fired["node_states"]["message"], "executed")
        self.assertEqual(fired["node_states"]["otherwise1"], "cancelled")
        self.assertEqual(fired["timeline"][0]["node_ids"], ["message"])
        self.assertIsNone(fired["replay_verified"])
        self.assertEqual(session.snapshot().to_dict(), snapshot)
        inspect = controller.inspect("if1")
        self.assertEqual({row["event_id"] for row in inspect["native_events"]},
                         {"r31_debug_yes", "r31_debug_no"})
        second = controller.step()["report"]
        self.assertEqual(second["fired_ids"], ["r31_debug_yes"])

    def test_else_fires_and_true_cannot_reactivate_on_changed_time(self):
        session, _ = session_with_graph(
            branched=True, predicate={"condition": "tick", "value": 100000})
        debugger = LogicGraphDebugger(session, "debug", tick=0)
        state = debugger.step()["report"]
        self.assertEqual(state["fired_ids"], ["r31_debug_no"])
        self.assertEqual(state["native_states"]["r31_debug_yes"]["state"],
                         "cancelled")
        # Only the throwaway Battle changes; there is no alternate executor.
        debugger._engine.battle.tick = 100000
        self.assertEqual(debugger.step()["report"]["fired_ids"],
                         ["r31_debug_no"])

    def test_revision_bound_including_undo_and_restart(self):
        session, _ = session_with_graph()
        debug = LogicGraphDebugger(session, "debug")
        restarted = debug.restart(scenario="initial", tick=10)
        self.assertEqual(restarted.tick, 10)
        self.assertEqual(restarted.scenario, "initial")
        session.undo()
        for call in (debug.report, debug.step, debug.resume,
                     lambda: debug.inspect("message"),
                     lambda: debug.breakpoint("start"),
                     debug.restart):
            with self.subTest(call=call):
                with self.assertRaises(AuthoringError) as raised:
                    call()
                self.assertEqual(raised.exception.code, "stale_revision")

    def test_native_r9_divergence_rejected_before_sandbox(self):
        session, graph = session_with_graph()
        EventStudio(session).set_condition(
            MISSION, "r31_debug", condition("tick", tick=42))
        with self.assertRaises(LogicGraphError) as raised:
            LogicGraphDebugger(session, "debug")
        self.assertEqual(raised.exception.code, "native_event_conflict")
        self.assertEqual(graphs_from_project(session.snapshot().to_dict()
                                             ["project"]), [graph])

    def test_missing_invalid_and_unsaved_graph_refused_without_mutation(self):
        session = AuthoringSession.new(*reference_project())
        initial = session.snapshot().to_dict()
        for invalid in ("unknown", "script", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(LogicGraphError):
                    LogicGraphDebugger(session, invalid)
        self.assertEqual(session.snapshot().to_dict(), initial)
        session, _ = session_with_graph()
        for opts in (
                {"tick": -1},
                {"tick": True},
                {"scenario": "eval"},
                {"tick": 100001},
        ):
            with self.subTest(opts=opts):
                with self.assertRaises(LogicGraphError):
                    LogicGraphDebugger(session, "debug", **opts)

    def test_state_reports_are_detached_and_breakpoint_type_checked(self):
        session, graph = session_with_graph(branched=True)
        debugger = LogicGraphDebugger(session, "debug")
        first = debugger.report()
        first["report"]["node_states"]["message"] = "injected"
        first["report"]["timeline"].append({"fake": True})
        self.assertNotIn("injected", debugger.report()["report"]["node_states"].values())
        self.assertFalse(debugger.report()["report"]["timeline"])
        with self.assertRaises(LogicGraphError):
            debugger.breakpoint("unknown")
        with self.assertRaises(LogicGraphError):
            debugger.breakpoint("if1", enabled=1)
        before = session.snapshot().to_dict()
        debugger.breakpoint("if1")
        self.assertEqual(session.snapshot().to_dict(), before)

    def test_headless_debugger_does_not_load_qt(self):
        script = (
            "import sys\n"
            "class DenyQt:\n"
            " def find_spec(self, fullname, path=None, target=None):\n"
            "  if fullname.split('.')[0] in ('PySide6','PyQt6','tkinter'):\n"
            "   raise AssertionError(fullname)\n"
            "sys.meta_path.insert(0,DenyQt())\n"
            "from drawtemp.studio.logic_debugger import LogicGraphDebugger\n"
        )
        result = subprocess.run([sys.executable, "-c", script],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

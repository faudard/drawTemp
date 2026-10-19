"""R31.E native R9 waits and journal flags: actual Battle/replay, no new scheduler."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.logic_graph import (
    LogicGraphError, apply_graph, compile_r9_triggers, graphs_from_project,
    validate_graph,
)
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.logic_graph_draft import LogicGraphDraft
from drawtemp.studio.logic_debugger import LogicGraphDebugger
from sporebound.engine import Battle
from sporebound.model import Content
from sporebound.rules.triggers import dispatch
from sporebound.temporal_events import temporal_status


def new_session():
    return AuthoringSession.new(*reference_project())


def wait_graph(graph_id="awaiting", ticks=3):
    draft = LogicGraphDraft.new(MISSION, graph_id, source_revision=0)
    draft.add_wait_after("message", ticks)
    return draft.graph


class SequenceContractTests(unittest.TestCase):
    def setUp(self):
        self.session = new_session()

    def test_wait_graph_v3_roundtrip_atomic_undo_and_native_timing(self):
        graph = wait_graph()
        self.assertEqual(validate_graph(graph), graph)
        stages = compile_r9_triggers(graph)
        self.assertEqual(len(stages), 2)
        self.assertEqual(stages[0]["id"], "r31_awaiting_s0")
        self.assertEqual(stages[1]["id"], "r31_awaiting_s1")
        self.assertEqual(stages[1]["after"], [stages[0]["id"]])
        self.assertEqual(stages[1]["delay_ticks"], 3)
        self.assertEqual(stages[1]["condition"], "tick")
        self.assertEqual(stages[1]["actions"][0]["text"], "Après attente")
        before = self.session.snapshot().to_dict()
        apply_graph(self.session, graph)
        saved = self.session.snapshot().to_dict()
        self.assertEqual(
            saved["content"]["missions"][0]["triggers"][-2:], stages)
        self.assertEqual(graphs_from_project(saved["project"]), [graph])
        self.session.undo()
        self.assertEqual(self.session.snapshot().to_dict()["content"],
                         before["content"])
        self.session.redo()
        self.assertEqual(self.session.snapshot().to_dict()["project"],
                         saved["project"])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "jeanne.json"
            self.session.save_as(path)
            reopened = AuthoringSession.open(path)
            self.assertEqual(graphs_from_project(
                reopened.snapshot().to_dict()["project"]), [graph])

    def test_native_timing_is_journal_derived_and_replay_checks_digest(self):
        apply_graph(self.session, wait_graph(ticks=2))
        data = self.session.snapshot().to_dict()["content"]
        battle = Battle(Content.from_dict(data), MISSION,
                        seed=13, battle_id="r31-wait-replay")
        self.assertIn("r31_awaiting_s0", battle.fired)
        self.assertNotIn("r31_awaiting_s1", battle.fired)
        self.assertEqual(temporal_status(
            battle, next(row for row in battle.mission.triggers
                         if row["id"] == "r31_awaiting_s1"))["state"],
                         "scheduled")
        initial = battle.recording()
        self.assertEqual(Battle.replay(initial).digest(), battle.digest())
        # Generate authentic commands (no fabricated Battle event journal).
        for _ in range(25):
            if "r31_awaiting_s1" in battle.fired or battle.result:
                break
            if battle.active_id is None:
                break
            battle.execute({"kind": "end"})
        self.assertIn("r31_awaiting_s1", battle.fired)
        self.assertEqual(Battle.replay(battle.recording()).digest(),
                         battle.digest())
        self.assertEqual(battle.fired.count("r31_awaiting_s0"), 1)
        self.assertEqual(battle.fired.count("r31_awaiting_s1"), 1)

    def test_flag_reads_existing_native_trigger_completion(self):
        from sporebound.event_composer import condition
        from drawtemp.studio.events import EventStudio
        EventStudio(self.session).create(
            MISSION, "prior_event", condition("tick", tick=7),
            [{"kind": "message", "text": "Drapeau activé"}])
        draft = LogicGraphDraft.new(
            MISSION, "flagged", source_revision=self.session.revision)
        draft.add_flag_after("message", "prior_event")
        compiled = compile_r9_triggers(draft.graph)
        self.assertEqual(compiled[1]["after"],
                         ["r31_flagged_s0", "prior_event"])
        draft.apply(self.session)
        data = self.session.snapshot().to_dict()["content"]
        battle = Battle(Content.from_dict(data), MISSION,
                        seed=4, battle_id="r31-flag-test")
        self.assertIn("r31_flagged_s0", battle.fired)
        self.assertNotIn("r31_flagged_s1", battle.fired)
        gate = next(x for x in battle.mission.triggers
                    if x["id"] == "r31_flagged_s1")
        self.assertEqual(temporal_status(battle, gate)["state"], "waiting")
        battle.tick = 7
        dispatch(battle)
        self.assertIn("prior_event", battle.fired)
        self.assertIn("r31_flagged_s1", battle.fired)
        self.assertEqual(temporal_status(battle, gate)["state"], "fired")

    def test_flag_reference_must_exist_and_cycles_fail_closed(self):
        graph = LogicGraphDraft.new(
            MISSION, "unknownflag", source_revision=0)
        graph.add_flag_after("message", "not_present")
        before = self.session.snapshot().to_dict()
        with self.assertRaises((LogicGraphError, AuthoringError, ValueError)):
            apply_graph(self.session, graph.graph)
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_invalid_waits_and_drafts_rejected_before_mutating_project(self):
        for value in (0, -1, True, "8", 10001):
            with self.subTest(value=value):
                draft = LogicGraphDraft.new(
                    MISSION, "reject", source_revision=self.session.revision)
                original = draft.document()
                with self.assertRaises(LogicGraphError):
                    draft.add_wait_after("message", value)
                self.assertEqual(draft.document(), original)
        candidate = wait_graph()
        corruptions = [
            lambda g: g["nodes"][-2]["params"].update(ticks=0),
            lambda g: g["edges"].append(deepcopy(g["edges"][-1])),
            lambda g: g["edges"][-1].update(out="true"),
            lambda g: g["nodes"].append({
                "id": "evil", "kind": "eval", "params": {"code": "import os"}}),
            lambda g: g.update(schema_version=5),
        ]
        for mutate in corruptions:
            invalid = deepcopy(candidate)
            mutate(invalid)
            with self.assertRaises(LogicGraphError):
                validate_graph(invalid)
        self.assertEqual(self.session.revision, 0)

    def test_consecutive_waits_and_max_stages_are_bounded(self):
        draft = LogicGraphDraft.new(MISSION, "budget", source_revision=0)
        for _ in range(15):
            end = draft.graph["edges"][-1]["to"]
            draft.add_wait_after(end, 1)
        self.assertEqual(len(compile_r9_triggers(draft.graph)), 16)
        with self.assertRaises(LogicGraphError):
            draft.add_wait_after(draft.graph["nodes"][-1]["id"], 1)

    def test_graph_migration_v1_to_v3_keeps_unrelated_native_events(self):
        draft = LogicGraphDraft.new(MISSION, "migration", source_revision=0)
        draft.apply(self.session)
        prior = self.session.snapshot().to_dict()["content"]
        upgraded = LogicGraphDraft.load(self.session, "migration")
        upgraded.add_wait_after("message", 3)
        upgraded.apply(self.session)
        now = self.session.snapshot().to_dict()["content"]
        ids = [row["id"] for row in now["missions"][0]["triggers"]]
        self.assertNotIn("r31_migration", ids)
        self.assertIn("r31_migration_s0", ids)
        self.assertIn("r31_migration_s1", ids)
        self.session.undo()
        self.assertEqual(self.session.snapshot().to_dict()["content"], prior)

    def test_debugger_maps_scheduled_stages_without_claiming_replay_proof(self):
        apply_graph(self.session, wait_graph())
        initial = self.session.snapshot().to_dict()
        debugger = LogicGraphDebugger(self.session, "awaiting")
        self.assertEqual(debugger.event_ids,
                         ("r31_awaiting_s0", "r31_awaiting_s1"))
        self.assertEqual(debugger.step()["report"]["fired_ids"],
                         ["r31_awaiting_s0"])
        state = debugger.report()["report"]
        self.assertEqual(state["node_states"]["wait1"], "scheduled")
        self.assertEqual(debugger.inspect("wait1")["native_events"][0]
                         ["temporal"]["state"], "scheduled")
        self.assertIsNone(state["replay_verified"])
        self.assertEqual(self.session.snapshot().to_dict(), initial)


if __name__ == "__main__":
    unittest.main()

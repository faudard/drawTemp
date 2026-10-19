"""R31.D — visual graph debugger projected from the one canonical R9 Battle.

The persisted graph's native triggers are verified byte-for-byte before a
throwaway EventDebugger can run. No new interpreter, scheduler, gameplay save,
or authenticated replay claim. Step means one whole native trigger, not one
individual action.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.logic_graph import (
    LogicGraphError, _ordered_nodes, compile_r9_triggers,
    graphs_from_project, validate_graph,
)
from sporebound.event_debugger import EventDebugger, format_debug_report
from sporebound.temporal_events import temporal_status


class LogicGraphDebugger:
    """Bounded, revision-bound adapter: nodes -> native events -> real Battle."""

    def __init__(self, session: AuthoringSession, graph_id: str, *,
                 scenario="initial", tick=0):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected the shared R1 AuthoringSession")
        if scenario not in ("initial", "satisfied", "unsatisfied"):
            raise LogicGraphError("invalid_scenario", "Unknown debug scenario")
        if type(tick) is not int or not 0 <= tick <= 100000:
            raise LogicGraphError("invalid_tick", "Debug tick must be 0..100000")
        snapshot = session.snapshot().to_dict()
        graph = next((row for row in graphs_from_project(snapshot["project"])
                      if row["id"] == graph_id), None)
        if graph is None:
            raise LogicGraphError("unknown_graph", "Save a visual graph before debugging it")
        self.graph = validate_graph(graph)
        native = compile_r9_triggers(graph)
        mission_id = graph["mission_id"]
        mission = next((row for row in snapshot["content"]["missions"]
                        if row["id"] == mission_id), None)
        if mission is None:
            raise LogicGraphError("unknown_mission", "Visual graph mission does not exist")
        current = {row["id"]: row for row in mission.get("triggers", ())}
        if any(current.get(row["id"]) != row for row in native):
            raise LogicGraphError(
                "native_event_conflict",
                "The visual graph and R9 events differ; refresh before debugging")
        ids = [row["id"] for row in native]
        indexes = [i for i, row in enumerate(mission.get("triggers", ()))
                   if row["id"] in ids]
        if (len(indexes) != len(ids) or indexes != list(range(indexes[0],
                                                            indexes[0] + len(ids)))
                or [mission["triggers"][i]["id"] for i in indexes] != ids):
            raise LogicGraphError("native_event_conflict",
                                  "Native event ordering was modified externally")
        self._session = session
        self.source_revision = session.revision
        self.graph_id = graph_id
        self.mission_id = mission_id
        self.scenario = scenario
        self.tick = tick
        self.event_to_actions = {}
        self.node_to_events = {}
        entry = graph["entry"]
        if graph["schema_version"] == 1:
            ordered = _ordered_nodes(graph)
            self.event_to_actions[ids[0]] = [n["id"] for n in ordered[1:]]
            self.node_to_events[entry] = tuple(ids)
        else:
            from drawtemp.sdk.logic_branches import validate_branch_graph
            paths, _ = validate_branch_graph(graph)
            self.event_to_actions = {
                ids[0]: [n["id"] for n in paths["true"]],
                ids[1]: [n["id"] for n in paths["false"]],
            }
            branch = next(n["id"] for n in graph["nodes"]
                          if n["kind"] == "branch")
            self.node_to_events[entry] = tuple(ids)
            self.node_to_events[branch] = tuple(ids)
            self._branch_node = branch
        for eid, node_ids in self.event_to_actions.items():
            for node_id in node_ids:
                self.node_to_events[node_id] = (eid,)
        self.event_ids = tuple(ids)
        self._engine = EventDebugger(
            snapshot["content"], mission_id, ids[0], tick=tick,
            scenario=scenario, included_event_ids=ids)

    def _current(self):
        if self._session.revision != self.source_revision:
            raise AuthoringError(
                "stale_revision", "logic_debug",
                "The project changed; restart visual graph debugging")

    def _read(self, report):
        self._current()
        raw = deepcopy(report)
        native_states = {}
        for eid in self.event_ids:
            event = self._engine.by_id[eid]
            native_states[eid] = temporal_status(self._engine.battle, event)
        for event in raw["timeline"]:
            event["node_ids"] = list(self.event_to_actions[event["event_id"]])
            event["scope"] = "whole_native_trigger"
        node_states = {}
        fired = set(raw["fired_ids"])
        for node in self.graph["nodes"]:
            identifier = node["id"]
            events = self.node_to_events.get(identifier, ())
            if node["kind"] == "action":
                state = "executed" if events[0] in fired else (
                    native_states[events[0]]["state"] if
                    "cancel_after" in self._engine.by_id[events[0]]
                    else "waiting")
            else:
                state = "fired" if any(eid in fired for eid in events) else (
                    "paused" if raw["paused_on"] in events else "waiting")
            node_states[identifier] = state
        raw["native_states"] = deepcopy(native_states)
        raw["node_states"] = node_states
        raw["paused_node"] = (
            getattr(self, "_branch_node", self.graph["entry"])
            if raw["paused_on"] is not None else None)
        raw["graph_id"] = self.graph_id
        raw["schema_version"] = self.graph["schema_version"]
        raw["step_granularity"] = "native_trigger"
        raw["isolated"] = True
        raw["replay_verified"] = None
        return {
            "source_revision": self.source_revision,
            "report": raw,
            "lines": format_debug_report(raw),
        }

    def report(self):
        return self._read(self._engine.report())

    def breakpoint(self, node_id, enabled=True):
        self._current()
        if type(enabled) is not bool:
            raise LogicGraphError("invalid_breakpoint", "Enabled must be a boolean")
        if node_id not in self.node_to_events:
            raise LogicGraphError("unknown_node", "Node is not in saved visual graph")
        kind = next(n["kind"] for n in self.graph["nodes"]
                    if n["id"] == node_id)
        if kind == "action":
            raise LogicGraphError(
                "breakpoint_granularity",
                "Action-level breakpoints are not supported by the R9 dispatcher")
        for eid in self.node_to_events[node_id]:
            self._engine.set_breakpoint(eid, enabled)
        return self.report()

    def step(self):
        self._current()
        return self._read(self._engine.step())

    def resume(self):
        self._current()
        return self._read(self._engine.continue_to_breakpoint())

    def inspect(self, node_id):
        self._current()
        events = self.node_to_events.get(node_id)
        if not events:
            raise LogicGraphError("unknown_node", "Unknown node")
        node = next(n for n in self.graph["nodes"] if n["id"] == node_id)
        results = []
        for eid in events:
            event = self._engine.by_id[eid]
            trace = self._engine.inspect(eid)
            results.append({
                "event_id": eid,
                "condition_passed": trace["passed"],
                "conditions": trace["conditions"],
                "temporal": temporal_status(self._engine.battle, event),
                "fired": eid in self._engine.battle.fired,
            })
        action = None
        if node["kind"] == "action":
            eid = events[0]
            index = self.event_to_actions[eid].index(node_id)
            action = deepcopy(self._engine.by_id[eid]["actions"][index])
        return {
            "source_revision": self.source_revision,
            "node_id": node_id,
            "kind": node["kind"],
            "native_events": results,
            "action": action,
            "step_granularity": "native_trigger",
            "isolated": True,
            "replay_verified": None,
        }

    def restart(self, *, scenario=None, tick=None):
        self._current()
        return type(self)(
            self._session, self.graph_id,
            scenario=self.scenario if scenario is None else scenario,
            tick=self.tick if tick is None else tick,
        )

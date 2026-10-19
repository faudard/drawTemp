"""R31.B visual graph draft: temporary UI state, never a second game database.

Only apply_graph commits to the shared R1 AuthoringSession. Incomplete drafts
are allowed for authoring, but can never be previewed or saved as game data.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.logic_graph import (
    LogicGraphError, MAX_NODES, compile_r9_triggers, graphs_from_project,
    preview_graph, validate_graph,
)


def _error(code, message):
    raise LogicGraphError(code, message)


class LogicGraphDraft:
    """Detached editor buffer with strict commands and revision tracking."""

    def __init__(self, graph, *, source_revision):
        self.graph = deepcopy(graph)
        self.source_revision = source_revision

    @classmethod
    def new(cls, mission_id, graph_id, *, source_revision):
        return cls({
            "schema_version": 1,
            "id": graph_id,
            "mission_id": mission_id,
            "entry": "start",
            "nodes": [
                {"id": "start", "kind": "event",
                 "params": {"kind": "tick", "tick": 0}},
                {"id": "message", "kind": "action",
                 "params": {"kind": "message", "text": "Nouveau message"}},
            ],
            "edges": [
                {"from": "start", "out": "next", "to": "message", "in": "flow"},
            ],
        }, source_revision=source_revision)

    @classmethod
    def load(cls, session, graph_id):
        project = session.snapshot().to_dict()["project"]
        graph = next((row for row in graphs_from_project(project)
                      if row["id"] == graph_id), None)
        if graph is None:
            _error("unknown_graph", "Unknown visual graph")
        return cls(graph, source_revision=session.revision)

    def document(self):
        return deepcopy(self.graph)

    def node(self, node_id):
        node = next((node for node in self.graph["nodes"]
                     if node["id"] == node_id), None)
        if node is None:
            _error("unknown_node", "Unknown node: " + str(node_id))
        return deepcopy(node)

    def _used_ids(self):
        return {node["id"] for node in self.graph["nodes"]}

    def _next_id(self, base):
        for i in range(1, MAX_NODES + 2):
            candidate = base + str(i)
            if candidate not in self._used_ids():
                return candidate
        _error("node_budget", "No free node ID in this graph")

    def add_action(self, kind="message", params=None):
        if len(self.graph["nodes"]) >= MAX_NODES:
            _error("node_budget", "Maximum 64 nodes")
        presets = {
            "message": {"kind": "message", "text": "Nouveau message"},
            "despawn": {"kind": "despawn", "unit": "enemy"},
            "hazard": {"kind": "hazard", "pos": [0, 0], "amount": 1},
        }
        if kind not in presets:
            _error("unsupported_node", "Unknown visual action")
        from drawtemp.sdk.logic_graph import _validate_params
        payload = deepcopy(presets[kind] if params is None else params)
        _validate_params("action", payload)
        if payload["kind"] != kind:
            _error("invalid_parameter", "Mismatched action kind")
        identifier = self._next_id(kind)
        self.graph["nodes"].append(
            {"id": identifier, "kind": "action", "params": payload})
        return identifier

    def add_branch(self, predicate=None):
        """Upgrade a validated linear v1 graph into a strict two-arm v2 DAG."""
        if self.graph["schema_version"] != 1:
            _error("invalid_branch", "Only one IF/ELSE is allowed per graph")
        validate_graph(self.graph)
        predicate = ({"condition": "wave_capacity", "team": "enemy",
                      "max_alive": 0} if predicate is None else predicate)
        from drawtemp.sdk.logic_branches import validate_expression
        validate_expression(predicate)
        if len(self.graph["nodes"]) + 2 > MAX_NODES:
            _error("node_budget", "Too many nodes for IF/ELSE")
        new = deepcopy(self.graph)
        old = next(edge for edge in new["edges"] if edge["from"] == new["entry"])
        target = old["to"]
        branch = self._next_id("if")
        otherwise = self._next_id("otherwise")
        if otherwise == branch:
            _error("invalid_id", "Overlapping branch identities")
        new["schema_version"] = 2
        new["nodes"].extend([
            {"id": branch, "kind": "branch",
             "params": {"kind": "if", "predicate": deepcopy(predicate)}},
            {"id": otherwise, "kind": "action",
             "params": {"kind": "message", "text": "Sinon"}},
        ])
        new["edges"].remove(old)
        new["edges"].extend([
            {"from": new["entry"], "out": "next", "to": branch, "in": "flow"},
            {"from": branch, "out": "true", "to": target, "in": "flow"},
            {"from": branch, "out": "false", "to": otherwise, "in": "flow"},
        ])
        validate_graph(new)
        self.graph = new
        return branch

    def insert_gate_after(self, action_id, *, kind, params):
        """Splice a wait/flag after one action, preserving a valid linear path.

        An end-of-sequence gate creates a typed message placeholder for its
        mandatory second action stage. The R1 project is not mutated.
        """
        if self.graph["schema_version"] not in (1, 3):
            _error("invalid_sequence", "Only linear graphs accept wait/flag gates")
        if self.node(action_id)["kind"] != "action":
            _error("port_type", "Select an action before inserting a gate")
        from drawtemp.sdk.logic_sequence import validate_gate_params
        validate_gate_params(kind, params)
        validate_graph(self.graph)
        next_edge = next((edge for edge in self.graph["edges"]
                          if edge["from"] == action_id), None)
        extra = 1 if next_edge is not None else 2
        if len(self.graph["nodes"]) + extra > MAX_NODES:
            _error("node_budget", "A wait/flag would exceed 64 nodes")
        candidate = deepcopy(self.graph)
        existing_ids = {node["id"] for node in candidate["nodes"]}
        gate_id = self._next_id("wait" if kind == "wait" else "flag")
        existing_ids.add(gate_id)
        candidate["nodes"].append({
            "id": gate_id, "kind": kind, "params": deepcopy(params)})
        if next_edge is not None:
            candidate["edges"].remove(next_edge)
            target_id = next_edge["to"]
        else:
            target_id = next("message" + str(index)
                             for index in range(1, MAX_NODES + 2)
                             if "message" + str(index) not in existing_ids)
            candidate["nodes"].append({
                "id": target_id, "kind": "action",
                "params": {"kind": "message", "text": "Après attente" if kind == "wait"
                           else "Après événement"}})
        candidate["edges"].extend([
            {"from": action_id, "out": "next", "to": gate_id, "in": "flow"},
            {"from": gate_id, "out": "next", "to": target_id, "in": "flow"},
        ])
        candidate["schema_version"] = 3
        validate_graph(candidate)
        self.graph = candidate
        return gate_id

    def add_wait_after(self, action_id, ticks=1):
        return self.insert_gate_after(action_id, kind="wait",
                                      params={"kind": "ticks", "ticks": ticks})

    def add_flag_after(self, action_id, event_id):
        return self.insert_gate_after(action_id, kind="flag", params={
            "kind": "event_fired", "event_id": event_id})

    def copy_action(self, node_id):
        node = self.node(node_id)
        if node["kind"] != "action":
            _error("invalid_operation", "The unique event entry cannot be copied")
        return self.add_action(node["params"]["kind"], node["params"])

    def edit_node(self, node_id, params):
        node = self.node(node_id)
        from drawtemp.sdk.logic_graph import _validate_params
        if node["kind"] in ("wait", "flag"):
            from drawtemp.sdk.logic_sequence import validate_gate_params
            validate_gate_params(node["kind"], params)
        elif node["kind"] == "branch":
            from drawtemp.sdk.logic_branches import validate_expression
            if type(params) is not dict or set(params) != {"kind", "predicate"} or params["kind"] != "if":
                _error("typed_expression", "Expected IF with pure boolean predicate")
            validate_expression(params["predicate"])
        else:
            _validate_params(node["kind"], params)
        candidate = deepcopy(self.graph)
        for row in candidate["nodes"]:
            if row["id"] == node_id:
                row["params"] = deepcopy(params)
        self.graph = candidate

    def connect(self, source, target, *, port="next"):
        a, b = self.node(source), self.node(target)
        if source == target or b["kind"] != "action":
            _error("port_type", "Connection must target an action flow input")
        if (a["kind"] == "branch" and port not in ("true", "false")) or (
                a["kind"] != "branch" and port != "next"):
            _error("port_type", "Incompatible typed output")
        if any(e["from"] == source and e["out"] == port for e in self.graph["edges"]):
            _error("multiple_connections", "Typed output already connected")
        if any(e["to"] == target for e in self.graph["edges"]):
            _error("multiple_connections", "Target flow already connected")
        downstream = {}
        for edge in self.graph["edges"]:
            downstream.setdefault(edge["from"], set()).add(edge["to"])
        pending, seen = [target], set()
        while pending:
            current = pending.pop()
            if current == source:
                _error("cycle", "Connection would create a cycle")
            if current in seen:
                continue
            seen.add(current)
            pending.extend(downstream.get(current, ()))
        self.graph["edges"].append({
            "from": source, "out": port, "to": target, "in": "flow"})

    def disconnect(self, source, target):
        count = len(self.graph["edges"])
        self.graph["edges"] = [e for e in self.graph["edges"]
                               if (e["from"], e["to"]) != (source, target)]
        if len(self.graph["edges"]) == count:
            _error("unknown_edge", "No connection found")

    def remove_action(self, node_id):
        if self.node(node_id)["kind"] != "action":
            _error("invalid_operation", "Cannot delete event or control node")
        self.graph["nodes"] = [n for n in self.graph["nodes"]
                               if n["id"] != node_id]
        self.graph["edges"] = [e for e in self.graph["edges"]
                               if node_id not in (e["from"], e["to"])]

    def prepare(self, session):
        """Validate native R9 and canonical pair; stale drafts never commit."""
        if session.revision != self.source_revision:
            _error("stale_revision", "Project changed; reload this graph before applying")
        compiled = compile_r9_triggers(self.graph)
        plan = preview_graph(session, self.graph)
        return plan, compiled[0] if len(compiled) == 1 else compiled

    def apply(self, session):
        plan, compiled = self.prepare(session)
        result = session.apply(plan)
        self.source_revision = session.revision
        return result, compiled

    def validate(self):
        return validate_graph(self.graph)

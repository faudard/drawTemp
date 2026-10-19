"""R31.B visual graph draft: temporary UI state, never a second game database.

Only apply_graph commits to the shared R1 AuthoringSession. Incomplete drafts
are allowed for authoring, but can never be previewed or saved as game data.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.logic_graph import (
    LogicGraphError, MAX_NODES, compile_r9_trigger, graphs_from_project,
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

    def copy_action(self, node_id):
        node = self.node(node_id)
        if node["kind"] != "action":
            _error("invalid_operation", "The unique event entry cannot be copied")
        return self.add_action(node["params"]["kind"], node["params"])

    def edit_node(self, node_id, params):
        node = self.node(node_id)
        from drawtemp.sdk.logic_graph import _validate_params
        _validate_params(node["kind"], params)
        candidate = deepcopy(self.graph)
        for row in candidate["nodes"]:
            if row["id"] == node_id:
                row["params"] = deepcopy(params)
        self.graph = candidate

    def connect(self, source, target):
        a, b = self.node(source), self.node(target)
        if source == target or b["kind"] != "action":
            _error("port_type", "Connection must target another action's flow port")
        if any(e["from"] == source for e in self.graph["edges"]):
            _error("multiple_connections", "Source next port already connected")
        if any(e["to"] == target for e in self.graph["edges"]):
            _error("multiple_connections", "Target flow port already connected")
        cursor = target
        seen = set()
        downstream = {e["from"]: e["to"] for e in self.graph["edges"]}
        while cursor in downstream and cursor not in seen:
            seen.add(cursor)
            cursor = downstream[cursor]
            if cursor == source:
                _error("cycle", "Connection would create a cycle")
        self.graph["edges"].append({
            "from": source, "out": "next", "to": target, "in": "flow"})

    def disconnect(self, source, target):
        count = len(self.graph["edges"])
        self.graph["edges"] = [e for e in self.graph["edges"]
                               if (e["from"], e["to"]) != (source, target)]
        if len(self.graph["edges"]) == count:
            _error("unknown_edge", "No connection found")

    def remove_action(self, node_id):
        if self.node(node_id)["kind"] != "action":
            _error("invalid_operation", "Cannot delete the event entry")
        self.graph["nodes"] = [n for n in self.graph["nodes"]
                               if n["id"] != node_id]
        self.graph["edges"] = [e for e in self.graph["edges"]
                               if node_id not in (e["from"], e["to"])]

    def prepare(self, session):
        """Validate native R9 and canonical pair; stale drafts never commit."""
        if session.revision != self.source_revision:
            _error("stale_revision", "Project changed; reload this graph before applying")
        compiled = compile_r9_trigger(self.graph)
        plan = preview_graph(session, self.graph)
        return plan, compiled

    def apply(self, session):
        plan, compiled = self.prepare(session)
        result = session.apply(plan)
        self.source_revision = session.revision
        return result, compiled

    def validate(self):
        return validate_graph(self.graph)

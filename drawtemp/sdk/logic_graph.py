"""R31.A–E versioned visual authoring compiled into native R9 Mission.triggers.

Schema v1 retains linear flows; v2 provides typed IF/ELSE; v3 adds bounded
linear delays and journal-backed event flags. No second gameplay runtime.
"""
from __future__ import annotations

from copy import deepcopy
import re

from drawtemp.sdk.authoring import AuthoringSession
from sporebound import event_composer

NAMESPACE = "org.drawtemp.logic"
SCHEMA_VERSION = 1
MAX_NODES = 64
MAX_GRAPHS = 16
_ID = re.compile(r"[a-z][a-z0-9_-]{0,55}\Z")


class LogicGraphError(ValueError):
    """Stable, actionable diagnostics for the Studio and import pipeline."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise LogicGraphError(code, message)


def _id(value, label):
    if type(value) is not str or _ID.fullmatch(value) is None:
        _fail("invalid_id", label + " must use 1..56 lowercase ASCII characters")


def _exact(row, keys, label):
    if type(row) is not dict or set(row) != keys:
        _fail("invalid_shape", label + " has missing or unsupported keys")


def _bounded_text(value, label, limit=256):
    if type(value) is not str or not value.strip() or len(value) > limit:
        _fail("invalid_parameter", label + " must be non-empty text (max " +
              str(limit) + " characters)")


def _validate_params(kind, params):
    if type(params) is not dict:
        _fail("invalid_parameter", "Node params must be an object")
    if kind == "event":
        trigger = params.get("kind")
        if trigger == "tick":
            _exact(params, {"kind", "tick"}, "tick event")
            if type(params["tick"]) is not int or not 0 <= params["tick"] <= 1000000:
                _fail("invalid_parameter", "tick must be an integer in 0..1000000")
        elif trigger == "interact":
            _exact(params, {"kind", "object_id"}, "interact event")
            _bounded_text(params["object_id"], "object_id", 64)
        else:
            _fail("unsupported_node", "Unsupported R9 event condition")
    elif kind == "action":
        action = params.get("kind")
        if action == "message":
            _exact(params, {"kind", "text"}, "message action")
            _bounded_text(params["text"], "message", 256)
        elif action == "despawn":
            _exact(params, {"kind", "unit"}, "despawn action")
            _bounded_text(params["unit"], "unit", 64)
        elif action == "hazard":
            _exact(params, {"kind", "pos", "amount"}, "hazard action")
            pos = params["pos"]
            if type(pos) is not list or len(pos) != 2 or any(
                    type(v) is not int or not 0 <= v <= 4095 for v in pos):
                _fail("invalid_parameter", "hazard.pos must contain two integer cells")
            if type(params["amount"]) is not int or not 1 <= params["amount"] <= 10000:
                _fail("invalid_parameter", "hazard.amount must be 1..10000")
        else:
            _fail("unsupported_node", "This action is not in the R31.A allowlist")
    else:
        _fail("unsupported_node", "Only event and action nodes are supported")


def _ordered_nodes(graph):
    """Reject cycles, forks and disconnected nodes instead of hanging the Player."""
    nodes = {}
    for node in graph["nodes"]:
        _exact(node, {"id", "kind", "params"}, "node")
        _id(node["id"], "node id")
        if node["id"] in nodes:
            _fail("duplicate_node", "Duplicate node id: " + node["id"])
        _validate_params(node["kind"], node["params"])
        nodes[node["id"]] = node
    if len(nodes) < 2 or len(nodes) > MAX_NODES:
        _fail("node_budget", "A graph requires 2..64 nodes")
    entry = graph["entry"]
    if entry not in nodes or nodes[entry]["kind"] != "event":
        _fail("invalid_entry", "Entry must refer to an event node")
    if sum(node["kind"] == "event" for node in nodes.values()) != 1:
        _fail("invalid_entry", "R31.A requires exactly one event node")
    outgoing, incoming = {}, set()
    if len(graph["edges"]) != len(nodes) - 1:
        _fail("invalid_edges", "R31.A requires one linear flow edge per step")
    for edge in graph["edges"]:
        _exact(edge, {"from", "out", "to", "in"}, "edge")
        source, target = edge["from"], edge["to"]
        if type(source) is not str or type(target) is not str:
            _fail("invalid_shape", "Edge endpoints must be node ID strings")
        if source not in nodes or target not in nodes:
            _fail("dangling_edge", "Edge references an unknown node")
        if edge["out"] != "next" or edge["in"] != "flow":
            _fail("port_type", "Only flow(next -> flow) ports are compatible")
        if target == entry or nodes[target]["kind"] != "action":
            _fail("port_type", "Only action nodes accept an incoming flow")
        if source in outgoing or target in incoming:
            _fail("multiple_connections", "R31.A does not allow forks or joins")
        outgoing[source] = target
        incoming.add(target)
    if entry in incoming or any(node_id != entry and node_id not in incoming
                                for node_id in nodes):
        _fail("disconnected", "Each action must have exactly one predecessor")
    result, visited, current = [], set(), entry
    while current is not None:
        if current in visited:
            _fail("cycle", "Visual flow contains a cycle")
        visited.add(current)
        result.append(nodes[current])
        current = outgoing.get(current)
    if len(visited) != len(nodes):
        _fail("cycle", "Graph contains a loop or unreachable action")
    return result


def validate_graph(graph):
    """Validate a detached JSON-compatible R31.1 authoring document."""
    _exact(graph, {"schema_version", "id", "mission_id", "entry",
                   "nodes", "edges"}, "graph")
    if type(graph["schema_version"]) is not int or graph["schema_version"] not in (1, 2, 3):
        _fail("unsupported_schema", "Only visual graph schemas 1, 2 and 3 are supported")
    _id(graph["id"], "graph id")
    _id(graph["mission_id"], "mission id")
    _id(graph["entry"], "entry id")
    if type(graph["nodes"]) is not list or type(graph["edges"]) is not list:
        _fail("invalid_shape", "nodes and edges must be arrays")
    if graph["schema_version"] == 1:
        _ordered_nodes(graph)
    elif graph["schema_version"] == 2:
        from drawtemp.sdk.logic_branches import validate_branch_graph
        validate_branch_graph(graph)
    else:
        from drawtemp.sdk.logic_sequence import ordered_sequence
        ordered_sequence(graph)
    return deepcopy(graph)


def compile_r9_trigger(graph):
    """Lower safe visual flow to the existing validated R9 trigger model.

    The Battle/Event Graph interprets this trigger using its original timing,
    CT, replay and save rules. There is no visual-script runtime in R31.A.
    """
    graph = validate_graph(graph)
    if graph["schema_version"] != 1:
        _fail("split_branches", "Use compile_r9_triggers for IF/ELSE graphs")
    ordered = _ordered_nodes(graph)
    params = ordered[0]["params"]
    if params["kind"] == "tick":
        condition = event_composer.condition("tick", tick=params["tick"])
    else:
        condition = event_composer.condition("interact",
                                             object_id=params["object_id"])
    actions = []
    for node in ordered[1:]:
        payload = node["params"]
        actions.append(event_composer.action(
            payload["kind"], **{k: deepcopy(v) for k, v in payload.items()
                                if k != "kind"}))
    return {"id": "r31_" + graph["id"], **condition, "actions": actions}


def compile_r9_triggers(graph):
    """Return stable, validated R9 trigger sequence, one or two per graph."""
    graph = validate_graph(graph)
    if graph["schema_version"] == 1:
        return [compile_r9_trigger(graph)]
    if graph["schema_version"] == 2:
        from drawtemp.sdk.logic_branches import compile_branch_triggers
        return compile_branch_triggers(graph)
    from drawtemp.sdk.logic_sequence import compile_sequence_triggers
    return compile_sequence_triggers(graph)


def _stored_graphs(project):
    extensions = project.get("extensions", {})
    if type(extensions) is not dict:
        _fail("invalid_storage", "GameProject extensions must be an object")
    spec = extensions.get(NAMESPACE)
    if spec is None:
        return []
    if (type(spec) is not dict or spec.get("schema_version") != 1 or
            type(spec.get("data")) is not dict or
            set(spec["data"]) != {"graphs"} or
            type(spec["data"]["graphs"]) is not list):
        _fail("invalid_storage", "R31 graph extension needs explicit migration")
    graphs = [validate_graph(g) for g in spec["data"]["graphs"]]
    if len(graphs) > MAX_GRAPHS or len({g["id"] for g in graphs}) != len(graphs):
        _fail("invalid_storage", "Too many or duplicate visual graphs")
    return graphs


def graphs_from_project(project):
    """Return detached authoring graphs; legacy projects remain untouched."""
    if hasattr(project, "to_dict"):
        project = project.to_dict()
    if type(project) is not dict:
        _fail("invalid_storage", "Expected canonical GameProject")
    return _stored_graphs(project)


def preview_graph(session: AuthoringSession, graph):
    """Stage BOTH Content trigger and GameProject graph in one R1 transaction.

    Existing native R9 events are never silently overwritten. A graph edited
    in parallel with a native R9 editor is rejected rather than clobbered.
    """
    if not isinstance(session, AuthoringSession):
        raise TypeError("Expected canonical AuthoringSession")
    authored = validate_graph(graph)
    compiled = compile_r9_triggers(authored)

    def edit(content, project):
        graphs = _stored_graphs(project)
        previous = next((g for g in graphs if g["id"] == authored["id"]), None)
        if previous is not None and previous["mission_id"] != authored["mission_id"]:
            _fail("mission_change", "Move between missions needs explicit migration")
        mission = next((m for m in content["missions"]
                        if m["id"] == authored["mission_id"]), None)
        if mission is None:
            _fail("unknown_mission", "Graph mission does not exist")
        old_compiled = compile_r9_triggers(previous) if previous is not None else []
        old_by_id = {row["id"]: row for row in old_compiled}
        events = mission.setdefault("triggers", [])
        existing = {row["id"]: row for row in events}
        for identifier, original in old_by_id.items():
            if existing.get(identifier) != original:
                _fail("native_event_conflict", "R9 event changed outside Logic Studio")
        if old_by_id:
            positions = [i for i, row in enumerate(events)
                         if row["id"] in old_by_id]
            if (positions != list(range(positions[0], positions[0] + len(old_by_id))) or
                    [events[i]["id"] for i in positions] !=
                    [row["id"] for row in old_compiled]):
                _fail("native_event_conflict",
                      "R9 branch ordering was changed by another editor")
        for row in compiled:
            if row["id"] in existing and row["id"] not in old_by_id:
                _fail("native_event_conflict", "R9 event id already belongs to another author")
        if previous is None and len(graphs) >= MAX_GRAPHS:
            _fail("graph_budget", "At most 16 visual graphs per project")
        if previous is not None:
            graphs = [g for g in graphs if g["id"] != authored["id"]]
        graphs.append(deepcopy(authored))
        # Atomic multi-trigger update: mutual cancel_after refs must exist
        # together during Content validation. Preserve foreign R9 order.
        old_ids = set(old_by_id)
        insertion = next((i for i, row in enumerate(events) if row["id"] in old_ids),
                         len(events))
        untouched = [row for row in events if row["id"] not in old_ids]
        mission["triggers"] = (untouched[:insertion] + deepcopy(compiled) +
                               untouched[insertion:])
        from sporebound.model import Content
        from sporebound.tactical_rpg3 import authored_rules_for_document
        content = Content.from_dict(
            content, rules=authored_rules_for_document(content)).to_dict()
        project.setdefault("extensions", {})[NAMESPACE] = {
            "schema_version": 1,
            "data": {"graphs": graphs},
            "references": [{"kind": "mission", "id": identifier}
                           for identifier in sorted({g["mission_id"] for g in graphs})],
        }
        return content, project

    return session.preview_pair(edit, kind="r31.logic.graph",
                                mission_id=authored["mission_id"],
                                views=("workspace", "inspector", "renderer"))


def apply_graph(session: AuthoringSession, graph):
    """Explicit commit with AuthoringSession history, revision and Undo/Redo."""
    return session.apply(preview_graph(session, graph))

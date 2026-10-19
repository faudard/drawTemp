"""R31.A — safe, versioned visual authoring compiled into R9 Mission.triggers.

This is a headless authoring compiler, NOT a second gameplay scheduler or
arbitrary Python scripting engine. Only an intentionally small linear subset
is accepted until R31.B adds branching, typed expressions and step debugging.
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
    if type(graph["schema_version"]) is not int or graph["schema_version"] != SCHEMA_VERSION:
        _fail("unsupported_schema", "Graph schema requires explicit migration")
    _id(graph["id"], "graph id")
    _id(graph["mission_id"], "mission id")
    _id(graph["entry"], "entry id")
    if type(graph["nodes"]) is not list or type(graph["edges"]) is not list:
        _fail("invalid_shape", "nodes and edges must be arrays")
    _ordered_nodes(graph)
    return deepcopy(graph)


def compile_r9_trigger(graph):
    """Lower safe visual flow to the existing validated R9 trigger model.

    The Battle/Event Graph interprets this trigger using its original timing,
    CT, replay and save rules. There is no visual-script runtime in R31.A.
    """
    graph = validate_graph(graph)
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


def _stored_graphs(project):
    spec = project.get("extensions", {}).get(NAMESPACE)
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
    compiled = compile_r9_trigger(authored)

    def edit(content, project):
        graphs = _stored_graphs(project)
        previous = next((g for g in graphs if g["id"] == authored["id"]), None)
        if previous is not None and previous["mission_id"] != authored["mission_id"]:
            _fail("mission_change", "Move between missions needs explicit migration")
        mission = next((m for m in content["missions"]
                        if m["id"] == authored["mission_id"]), None)
        if mission is None:
            _fail("unknown_mission", "Graph mission does not exist")
        current = next((row for row in mission.get("triggers", ())
                        if row["id"] == compiled["id"]), None)
        if previous is None and current is not None:
            _fail("native_event_conflict", "An R9 event already owns this id")
        if previous is not None and current != compile_r9_trigger(previous):
            _fail("native_event_conflict", "The R9 trigger changed outside the graph")
        if previous is None and len(graphs) >= MAX_GRAPHS:
            _fail("graph_budget", "At most 16 visual graphs per project")
        if previous is not None:
            graphs = [g for g in graphs if g["id"] != authored["id"]]
        graphs.append(deepcopy(authored))
        content = event_composer.save_event(
            content, authored["mission_id"], compiled["id"],
            {key: deepcopy(value) for key, value in compiled.items()
             if key not in {"id", "actions"}}, compiled["actions"])
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

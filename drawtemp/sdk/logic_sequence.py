"""R31.E — bounded linear wait and journal-backed event-flag graph lowering.

One native R9 trigger per action stage. No runtime queues, mutable visual
variables, extra replay schema or Python user scripting. A flag is a *read-only*
bool derived from the canonical Battle fired-event journal (R9 'after').
"""
from __future__ import annotations

from copy import deepcopy
import re

MAX_STAGES = 16
MAX_NODES = 64
_REF = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")


def _fail(code, message):
    from drawtemp.sdk.logic_graph import LogicGraphError
    raise LogicGraphError(code, message)


def validate_gate_params(kind, params):
    from drawtemp.sdk.logic_graph import _exact
    if kind == "wait":
        _exact(params, {"kind", "ticks"}, "wait params")
        if params["kind"] != "ticks" or type(params["ticks"]) is not int or not 1 <= params["ticks"] <= 10000:
            _fail("invalid_wait", "Wait requires an integer of 1..10000 logical ticks")
    elif kind == "flag":
        _exact(params, {"kind", "event_id"}, "journal flag params")
        ref = params["event_id"]
        if params["kind"] != "event_fired" or type(ref) is not str or _REF.fullmatch(ref) is None:
            _fail("invalid_flag", "Journal flag requires a valid R9 event ID")
    else:
        _fail("unsupported_node", "Only wait and event_fired flag gates are supported")


def ordered_sequence(graph):
    """Strict linear graph: event, action+, (wait|flag, action+)+.

    Returns ordered nodes. Rejects all forks, loops, dangling refs, nodes past
    budget and empty segments before any native R9 Content can be mutated.
    """
    from drawtemp.sdk.logic_graph import _exact, _id, _validate_params
    nodes = {}
    for node in graph["nodes"]:
        _exact(node, {"id", "kind", "params"}, "node")
        _id(node["id"], "node id")
        if node["id"] in nodes:
            _fail("duplicate_node", "Duplicate node ID")
        if node["kind"] in ("wait", "flag"):
            validate_gate_params(node["kind"], node["params"])
        else:
            _validate_params(node["kind"], node["params"])
        nodes[node["id"]] = node
    if not 4 <= len(nodes) <= MAX_NODES:
        _fail("node_budget", "R31.E sequence requires 4..64 nodes")
    entry = graph["entry"]
    if entry not in nodes or nodes[entry]["kind"] != "event":
        _fail("invalid_entry", "Sequence requires a canonical event entry")
    if sum(n["kind"] == "event" for n in nodes.values()) != 1:
        _fail("invalid_entry", "Only one event entry is permitted")
    if len(graph["edges"]) != len(nodes) - 1:
        _fail("invalid_edges", "A deterministic sequence has one edge per step")
    outgoing, incoming = {}, set()
    for edge in graph["edges"]:
        _exact(edge, {"from", "out", "to", "in"}, "edge")
        source, target = edge["from"], edge["to"]
        if type(source) is not str or type(target) is not str:
            _fail("invalid_shape", "Edge endpoints must be strings")
        if source not in nodes or target not in nodes:
            _fail("dangling_edge", "Unknown sequence endpoint")
        if edge["out"] != "next" or edge["in"] != "flow":
            _fail("port_type", "Sequence requires typed next → flow edges")
        if target == entry:
            _fail("port_type", "Entry cannot have an incoming flow edge")
        if source in outgoing or target in incoming:
            _fail("multiple_connections", "Forks and joins are not supported")
        outgoing[source] = target
        incoming.add(target)
    if len(incoming) != len(nodes) - 1:
        _fail("disconnected", "All nodes need one predecessor")
    ordered, visited, cursor = [], set(), entry
    while cursor is not None:
        if cursor in visited:
            _fail("cycle", "Visual sequence contains a cycle")
        visited.add(cursor)
        ordered.append(nodes[cursor])
        cursor = outgoing.get(cursor)
    if len(visited) != len(nodes):
        _fail("disconnected", "Sequence contains unreachable nodes or a loop")
    stages = 1
    prior = "event"
    for node in ordered[1:]:
        kind = node["kind"]
        if kind in ("wait", "flag"):
            if prior != "action":
                _fail("empty_stage", "Wait/flag must follow an action stage")
            stages += 1
        elif kind == "action":
            pass
        else:
            _fail("unsupported_node", "Unknown sequence node kind")
        prior = kind
    if prior != "action":
        _fail("empty_stage", "A wait or flag needs at least one subsequent action")
    if stages <= 1:
        _fail("invalid_sequence", "Sequence must contain a wait or journal flag")
    if stages > MAX_STAGES:
        _fail("stage_budget", "A graph compiles to at most 16 native R9 stages")
    return ordered


def sequence_stages(graph):
    """Pure ordered projection used by debugger to assign node ↔ R9 event IDs."""
    ordered = ordered_sequence(graph)
    stages = []
    segment = {"action_nodes": [], "gating_node": None,
               "wait_ticks": None, "flag_id": None}
    for node in ordered[1:]:
        if node["kind"] == "action":
            segment["action_nodes"].append(node["id"])
        else:
            stages.append(segment)
            segment = {"action_nodes": [], "gating_node": node["id"],
                       "wait_ticks": node["params"]["ticks"] if node["kind"] == "wait" else None,
                       "flag_id": node["params"]["event_id"] if node["kind"] == "flag" else None}
    stages.append(segment)
    return stages


def compile_sequence_triggers(graph):
    from drawtemp.sdk.logic_graph import validate_graph
    from sporebound import event_composer
    validate_graph(graph)
    stages = sequence_stages(graph)
    prefix = "r31_" + graph["id"]
    ids = [prefix + "_s" + str(index) for index in range(len(stages))]
    if any(len(identifier) > 64 for identifier in ids):
        _fail("invalid_id", "Graph ID exceeds the canonical R9 stage ID budget")
    by_node = {node["id"]: node for node in graph["nodes"]}
    event = by_node[graph["entry"]]["params"]
    native = []
    for index, segment in enumerate(stages):
        if index == 0:
            if event["kind"] == "tick":
                cond = event_composer.condition("tick", tick=event["tick"])
            else:
                cond = event_composer.condition("interact", object_id=event["object_id"])
        else:
            cond = event_composer.condition("tick", tick=0)
            after = [ids[index - 1]]
            if segment["flag_id"] is not None:
                flag = segment["flag_id"]
                if flag in ids:
                    # Read from journal only, but don't implicitly allow forward
                    # refs to same-graph future events or duplicate predecessor.
                    if flag not in ids[:index]:
                        _fail("invalid_flag", "Journal flag cannot reference future stage")
                if flag not in after:
                    after.append(flag)
                else:
                    _fail("invalid_flag", "Journal flag duplicates this stage predecessor")
            cond["after"] = after
            if segment["wait_ticks"] is not None:
                cond["delay_ticks"] = segment["wait_ticks"]
        actions = []
        for node_id in segment["action_nodes"]:
            payload = by_node[node_id]["params"]
            actions.append(event_composer.action(
                payload["kind"], **{key: deepcopy(value) for key, value in payload.items()
                                    if key != "kind"}))
        native.append({"id": ids[index], **cond, "actions": actions})
    return native

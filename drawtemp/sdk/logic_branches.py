"""R31.C: statically typed, bounded boolean predicates and two-arm DAG lowering.

The native R9 dispatcher is the *only* executor. A true/false branch compiles
to two one-shot R9 triggers that cancel each other through the existing
canonical Battle event journal, even if predicates change on a later tick.
"""
from __future__ import annotations

from copy import deepcopy


MAX_EXPRESSION_DEPTH = 4
MAX_EXPRESSION_NODES = 32
MAX_NODES = 64


def _fail(code, message):
    from drawtemp.sdk.logic_graph import LogicGraphError
    raise LogicGraphError(code, message)


def _keys(obj, expected, context):
    if type(obj) is not dict or set(obj) != expected:
        _fail("typed_expression", context + ": missing or unsupported fields")


def _identifier(obj, what):
    from drawtemp.sdk.logic_graph import _id
    _id(obj, what)


def validate_expression(expression, *, depth=0, count=None):
    """Pure bool expression. No arbitrary variable lookup, Python or side effects."""
    if count is None:
        count = [0]
    count[0] += 1
    if count[0] > MAX_EXPRESSION_NODES or depth >= MAX_EXPRESSION_DEPTH:
        _fail("expression_budget", "Expression depth/nodes exceed canonical R9 limits")
    if type(expression) is not dict:
        _fail("typed_expression", "A condition must be a typed boolean expression")
    if "condition" in expression:
        kind = expression["condition"]
        if kind in ("hp_below",):
            _keys(expression, {"condition", "unit", "percent"}, "HP condition")
            _identifier(expression["unit"], "unit")
            if type(expression["percent"]) is not int or not 1 <= expression["percent"] <= 99:
                _fail("typed_expression", "HP percentage must be an integer 1..99")
        elif kind == "defeated":
            _keys(expression, {"condition", "unit"}, "Defeated condition")
            _identifier(expression["unit"], "unit")
        elif kind == "wave_capacity":
            _keys(expression, {"condition", "team", "max_alive"}, "Team count condition")
            if expression["team"] not in ("enemy", "player", "neutral"):
                _fail("typed_expression", "Invalid team enum")
            if type(expression["max_alive"]) is not int or not 0 <= expression["max_alive"] <= 100000:
                _fail("typed_expression", "max_alive must be an integer 0..100000")
        elif kind == "tick":
            _keys(expression, {"condition", "value"}, "Tick comparison")
            if type(expression["value"]) is not int or not 0 <= expression["value"] <= 100000:
                _fail("typed_expression", "Tick must be an integer 0..100000")
        else:
            _fail("typed_expression", "Unsupported pure R9 condition: " + str(kind))
        return deepcopy(expression)
    _keys(expression, {next(iter(expression))} if expression else {"never"}, "Boolean operator")
    operator = next(iter(expression))
    if operator == "not":
        validate_expression(expression["not"], depth=depth+1, count=count)
    elif operator in ("all", "any"):
        children = expression[operator]
        if type(children) is not list or not 2 <= len(children) <= 8:
            _fail("typed_expression", "AND/OR takes 2..8 boolean expressions")
        for child in children:
            validate_expression(child, depth=depth+1, count=count)
    else:
        _fail("typed_expression", "Only AND/OR/NOT of pure boolean predicates are permitted")
    return deepcopy(expression)


def validate_branch_graph(graph):
    """A safe strict fork: entry -> branch, two disjoint ordered action tails.

    R31.C does not serialize generic joins, nested IFs, loops or timers.
    """
    from drawtemp.sdk.logic_graph import _exact, _id, _validate_params
    nodes = {}
    for node in graph["nodes"]:
        _exact(node, {"id", "kind", "params"}, "node")
        _id(node["id"], "node id")
        if node["id"] in nodes:
            _fail("duplicate_node", "Duplicate node")
        if node["kind"] == "branch":
            _exact(node["params"], {"kind", "predicate"}, "branch parameters")
            if node["params"]["kind"] != "if":
                _fail("typed_expression", "Only an IF branch is supported")
            validate_expression(node["params"]["predicate"])
        else:
            _validate_params(node["kind"], node["params"])
        nodes[node["id"]] = node
    if not 5 <= len(nodes) <= MAX_NODES:
        _fail("node_budget", "Branch graph needs 5..64 nodes (entry, branch and 2 actions)")
    if graph["entry"] not in nodes or nodes[graph["entry"]]["kind"] != "event":
        _fail("invalid_entry", "Branch graph needs an event entry")
    branches = [key for key, node in nodes.items() if node["kind"] == "branch"]
    if len(branches) != 1 or sum(n["kind"] == "event" for n in nodes.values()) != 1:
        _fail("invalid_branch", "R31.C requires one entry and one IF node")
    branch_id = branches[0]
    if len(graph["edges"]) != len(nodes)-1:
        _fail("invalid_edges", "Branches must be connected without dangling nodes or joins")
    outgoing, incoming = {}, {}
    for edge in graph["edges"]:
        _exact(edge, {"from", "out", "to", "in"}, "edge")
        source, target, port = edge["from"], edge["to"], edge["out"]
        if type(source) is not str or type(target) is not str:
            _fail("invalid_shape", "Edge IDs must be strings")
        if source not in nodes or target not in nodes:
            _fail("dangling_edge", "Unknown graph endpoint")
        if edge["in"] != "flow":
            _fail("port_type", "Only typed flow inputs are allowed")
        source_kind = nodes[source]["kind"]
        target_kind = nodes[target]["kind"]
        if source_kind == "branch":
            if port not in ("true", "false"):
                _fail("port_type", "IF output port must be true/false")
        elif port != "next":
            _fail("port_type", "Only next outputs may leave events and actions")
        if target_kind == "event" or (target_kind == "branch" and source != graph["entry"]):
            _fail("port_type", "Only entry may connect into IF")
        if (source, port) in outgoing or target in incoming:
            _fail("multiple_connections", "Typed output or flow input connected twice")
        outgoing[(source, port)] = target
        incoming[target] = source
    if outgoing.get((graph["entry"], "next")) != branch_id:
        _fail("invalid_branch", "Entry must flow directly to IF")
    if incoming.get(branch_id) != graph["entry"]:
        _fail("invalid_branch", "IF must have entry as its only predecessor")
    visited = {graph["entry"], branch_id}
    paths = {}
    for port in ("true", "false"):
        current = outgoing.get((branch_id, port))
        if current is None or nodes[current]["kind"] != "action":
            _fail("invalid_branch", "IF requires an action on each true/false output")
        path = []
        while current is not None:
            if current in visited:
                _fail("cycle", "Branch tails must be disjoint and acyclic")
            if nodes[current]["kind"] != "action":
                _fail("port_type", "Only actions can follow an IF output")
            visited.add(current)
            path.append(nodes[current])
            current = outgoing.get((current, "next"))
        paths[port] = path
    if len(visited) != len(nodes):
        _fail("disconnected", "All graph nodes must be reachable exactly once")
    return paths, nodes[branch_id]["params"]["predicate"]


def compile_branch_triggers(graph):
    """Use the original trigger dispatcher, guarded by opposing R9 predicates.

    cancel_after makes either arm irrevocable; true/false cannot both fire,
    even if the underlying HP/team/tick predicate changes over time.
    """
    from drawtemp.sdk.logic_graph import _validate_params
    paths, expression = validate_branch_graph(graph)
    entry = next(node for node in graph["nodes"] if node["id"] == graph["entry"])
    params = entry["params"]
    from sporebound import event_composer
    if params["kind"] == "tick":
        condition = event_composer.condition("tick", tick=params["tick"])
    else:
        condition = event_composer.condition("interact", object_id=params["object_id"])
    prefix = "r31_" + graph["id"]
    # An ID may grow beyond R9's 64-char limit when suffixed.
    ids = (prefix + "_yes", prefix + "_no")
    if any(len(identifier) > 64 for identifier in ids):
        _fail("invalid_id", "Graph ID is too long for branch event IDs")
    result = []
    for port, current, other in (("true", ids[0], ids[1]),
                                 ("false", ids[1], ids[0])):
        actions = []
        for node in paths[port]:
            payload = node["params"]
            actions.append(event_composer.action(
                payload["kind"], **{k: deepcopy(v) for k, v in payload.items()
                                    if k != "kind"}))
        predicate = deepcopy(expression) if port == "true" else {"not": deepcopy(expression)}
        # Native "when" is evaluated by sporebound.rules.triggers.matches_composite.
        result.append({"id": current, **deepcopy(condition),
                       "when": predicate,
                       "cancel_after": [other],
                       "actions": actions})
    return result

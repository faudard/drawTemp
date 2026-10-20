"""R37.C — bounded, deterministic Behavior Trees for read-only AI proposals.

Trees are authored through the canonical R37 GameProject extension. A tick is
pure: it never executes the chosen action, edits a blackboard, changes Battle
state or consumes random numbers. Actions return RUNNING (the owning game may
then validate/execute the proposal), while conditions return SUCCESS/FAILURE.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from .ai_decision import (
    AIDecisionError, _id, _reference, _scalar, validate_blackboard,
    validate_context,
)

MAX_NODES = 64
MAX_DEPTH = 16
MAX_CHILDREN = 16
SUCCESS, FAILURE, RUNNING = "success", "failure", "running"


def _fail(code, message):
    raise AIDecisionError(code, message)


def _exact(node, names):
    if type(node) is not dict or set(node) != names:
        _fail("invalid_tree_node", "Malformed behavior tree node")


def _digest(document):
    data = json.dumps(document, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return sha256(data).hexdigest()


def validate_behavior_tree(tree):
    """Validate and detach a strict rooted tree (no shared children/cycles)."""
    if type(tree) is not dict or set(tree) != {"schema_version", "root", "nodes"}:
        _fail("invalid_tree", "Expected schema_version, root and nodes")
    if type(tree["schema_version"]) is not int or tree["schema_version"] != 1:
        _fail("unsupported_schema", "Only behavior tree schema v1 is supported")
    _id(tree["root"], "root")
    nodes = tree["nodes"]
    if type(nodes) is not list or not 1 <= len(nodes) <= MAX_NODES:
        _fail("tree_budget", "Behavior Trees support 1..64 nodes")
    table = {}
    for node in nodes:
        if type(node) is not dict:
            _fail("invalid_tree_node", "Node must be an object")
        _id(node.get("id"), "node id")
        name = node["id"]
        if name in table:
            _fail("duplicate_node", "Duplicate behavior node: " + name)
        kind = node.get("kind")
        if kind in ("sequence", "selector"):
            _exact(node, {"id", "kind", "children"})
            children = node["children"]
            if (type(children) is not list
                    or not 1 <= len(children) <= MAX_CHILDREN
                    or len(set(c for c in children if type(c) is str))
                    != len(children)):
                _fail("tree_budget", "Composite requires 1..16 distinct children")
            for child in children:
                _id(child, "child")
        elif kind == "decorator":
            _exact(node, {"id", "kind", "op", "child"})
            if node["op"] != "invert":
                _fail("unsupported_node", "Only inverter decorator is supported")
            _id(node["child"], "child")
        elif kind == "condition":
            _exact(node, {"id", "kind", "fact", "equals"})
            _reference(node["fact"])
            _scalar(node["equals"])
        elif kind == "action":
            _exact(node, {"id", "kind", "action"})
            _id(node["action"], "action")
        else:
            _fail("unsupported_node", "Unknown behavior node kind")
        table[name] = deepcopy(node)
    if tree["root"] not in table:
        _fail("missing_root", "Root node does not exist")
    parents = {name: 0 for name in table}
    for node in table.values():
        children = (node["children"] if "children" in node
                    else [node["child"]] if "child" in node else [])
        for child in children:
            if child not in parents:
                _fail("unknown_child", "Missing behavior child: " + child)
            parents[child] += 1
    if parents[tree["root"]] != 0 or any(
            count != 1 for name, count in parents.items()
            if name != tree["root"]):
        _fail("invalid_tree", "Tree nodes must have exactly one parent, except root")
    visited = set()

    def visit(name, depth):
        if depth > MAX_DEPTH:
            _fail("tree_budget", "Behavior tree depth exceeds 16")
        if name in visited:
            _fail("cycle", "Behavior tree contains a cycle")
        visited.add(name)
        node = table[name]
        children = (node["children"] if "children" in node
                    else [node["child"]] if "child" in node else [])
        for child in children:
            visit(child, depth + 1)

    visit(tree["root"], 1)
    if len(visited) != len(table):
        _fail("unreachable_node", "Behavior tree contains disconnected nodes")
    return {"schema_version": 1, "root": tree["root"],
            "nodes": [table[name] for name in sorted(table)]}


def evaluate_behavior_tree(context, blackboard, tree, *, fallback="wait"):
    """Tick a compiled tree exactly once; return trace plus action proposal.

    Composite statuses follow ordinary BT rules. An action leaf returns
    RUNNING, so a sequence never continues past a proposed action as though
    the game had executed it. Pure conditions only inspect fixed-tick facts.
    """
    context = validate_context(context)
    blackboard = validate_blackboard(blackboard)
    tree = validate_behavior_tree(tree)
    _id(fallback, "fallback")
    if context["actor_id"] != blackboard["actor_id"]:
        _fail("actor_mismatch", "AI memory belongs to a different actor")
    if blackboard["updated_tick"] > context["tick"]:
        _fail("future_blackboard", "AI memory is newer than this decision tick")
    by_id = {n["id"]: n for n in tree["nodes"]}
    facts = dict(context["facts"])
    facts.update({"blackboard." + key: value for key, value
                  in blackboard["values"].items()})
    trace = []
    selected = None

    def evaluate(node_id):
        nonlocal selected
        node = by_id[node_id]
        kind = node["kind"]
        reason = ""
        if kind == "condition":
            key = node["fact"]
            if key not in facts:
                result, reason = FAILURE, "missing_fact:" + key
            elif (type(facts[key]) is type(node["equals"])
                  and facts[key] == node["equals"]):
                result, reason = SUCCESS, "matched:" + key
            else:
                result, reason = FAILURE, "mismatch:" + key
        elif kind == "action":
            result, reason = RUNNING, "proposed:" + node["action"]
            selected = {"node_id": node_id, "action": node["action"]}
        elif kind == "decorator":
            child_status = evaluate(node["child"])
            result = (FAILURE if child_status == SUCCESS
                      else SUCCESS if child_status == FAILURE
                      else RUNNING)
            reason = "invert:" + child_status
        elif kind == "sequence":
            result = SUCCESS
            for child in node["children"]:
                child_status = evaluate(child)
                if child_status != SUCCESS:
                    result = child_status
                    break
            reason = "sequence:" + result
        else:
            result = FAILURE
            for child in node["children"]:
                child_status = evaluate(child)
                if child_status != FAILURE:
                    result = child_status
                    break
            reason = "selector:" + result
        trace.append({"node_id": node_id, "kind": kind,
                      "status": result, "reason": reason})
        return result

    status = evaluate(tree["root"])
    # Bounded by static validation: at most 64 visited nodes, 16 levels.
    if len(trace) > MAX_NODES:
        _fail("tree_budget", "Exceeded runtime node budget")
    report = {
        "schema_version": 1, "actor_id": context["actor_id"],
        "mode": context["mode"], "tick": context["tick"],
        "seed": context["seed"], "blackboard_tick": blackboard["updated_tick"],
        "tree_root": tree["root"], "status": status,
        "selected_node": selected["node_id"] if selected else None,
        "action": selected["action"] if selected else fallback,
        "used_fallback": selected is None, "visited": len(trace),
        "trace": trace,
    }
    report["inputs_digest"] = _digest({
        "context": context, "blackboard": blackboard, "tree": tree,
        "fallback": fallback})
    report["digest"] = _digest(report)
    return report


class BehaviorTreeDebugger:
    """Read-only trace cursor for step, breakpoint and deterministic inspection.

    This replays a previously evaluated proposal; it never changes game time.
    """
    def __init__(self, report, breakpoints=()):
        if type(report) is not dict or type(report.get("trace")) is not list:
            _fail("invalid_trace", "Expected a Behavior Tree evaluation trace")
        if len(report["trace"]) > MAX_NODES:
            _fail("tree_budget", "Behavior Tree trace is too long")
        self._report = deepcopy(report)
        self._breakpoints = set(breakpoints)
        if not all(type(item) is str for item in self._breakpoints):
            _fail("invalid_trace", "Breakpoint IDs must be strings")
        self._cursor = 0

    def step(self):
        if self._cursor >= len(self._report["trace"]):
            return None
        event = deepcopy(self._report["trace"][self._cursor])
        self._cursor += 1
        return event

    def resume(self):
        """Continue until a breakpoint or the last evaluated node."""
        while self._cursor < len(self._report["trace"]):
            event = self.step()
            if event["node_id"] in self._breakpoints:
                return {"paused": True, "event": event,
                        "cursor": self._cursor}
        return {"paused": False, "event": None, "cursor": self._cursor}

    def state(self):
        return {"cursor": self._cursor, "total": len(self._report["trace"]),
                "complete": self._cursor == len(self._report["trace"]),
                "visited": deepcopy(self._report["trace"][:self._cursor]),
                "next_node": (self._report["trace"][self._cursor]["node_id"]
                              if self._cursor < len(self._report["trace"])
                              else None)}


__all__ = ["validate_behavior_tree", "evaluate_behavior_tree",
           "BehaviorTreeDebugger", "SUCCESS", "FAILURE", "RUNNING"]

"""Bounded, deterministic, one-shot strategic event graphs for multi-front sieges.

Conditions read only authenticated Battle/strategic timeline events or current
front state. Effects reuse the existing front-link mechanics; no battle results
are fabricated. The graph never evaluates user-authored Python expressions.
"""
from copy import deepcopy
from .model import require
from . import front_links

FRONT_STATES = {"active", "victory", "defeat", "withdrawn", "partial",
                "negotiated", "reclaimed"}
TIMELINE_EVENTS = {
    "campaign_battle_resolved", "campaign_front_negotiated",
    "campaign_front_partial", "campaign_front_withdrawn",
    "convoy_arrived", "campaign_counteroffensive_started",
    "front_link_applied", "campaign_recovery_victory",
    "campaign_recovery_defeat",
}
EFFECTS = front_links.EFFECTS | {"set_doctrine", "signal"}


def _id(text):
    return isinstance(text, str) and 0 < len(text) <= 64 and all(
        c.isalnum() or c in "_-" for c in text)


def _condition(node, content, missions, *, depth=0, budget=None, deps=None):
    require(depth <= 6 and isinstance(node, dict) and len(node) == 1,
            "Invalid strategic condition or excessive nesting")
    budget[0] -= 1
    require(budget[0] >= 0, "Strategic condition is too large")
    kind, value = next(iter(node.items()))
    if kind in ("all", "any"):
        require(isinstance(value, list) and 1 <= len(value) <= 8,
                "AND/OR requires 1..8 operands")
        for item in value:
            _condition(item, content, missions, depth=depth+1,
                       budget=budget, deps=deps)
    elif kind == "not":
        _condition(value, content, missions, depth=depth+1,
                   budget=budget, deps=deps)
    elif kind == "turn_at_least":
        require(type(value) is int and 0 <= value <= 10000,
                "Invalid strategic turn threshold")
    elif kind == "front_status":
        require(isinstance(value, dict) and set(value) == {"front", "status"}
                and value["front"] in missions and value["status"] in FRONT_STATES,
                "Invalid front status condition")
    elif kind == "fired":
        require(_id(value), "Invalid dependency id")
        deps.add(value)
    elif kind == "battle_event":
        require(isinstance(value, dict)
                and set(value) == {"front", "kind", "value"}
                and value["front"] in missions and value["kind"] in front_links.EVENTS,
                "Invalid tactical event condition")
        field = front_links.EVENT_FIELDS[value["kind"]]
        # Reuse the existing exact validation of tactical objects/events.
        source = value["front"]
        target = next((name for name in missions if name != source), None)
        require(target is not None, "Tactical proof needs another siege front")
        example = {"id": "test_condition", "source": source,
                   "event": value["kind"],
                   "match": {field: value["value"]},
                   "effects": [{"kind": "reduce_strength", "front": target,
                                "amount": 1}]}
        front_links.validate(content, missions, [example])
    elif kind == "timeline_event":
        require(isinstance(value, dict)
                and set(value) == {"front", "kind"}
                and value["front"] in missions
                and value["kind"] in TIMELINE_EVENTS,
                "Invalid strategic event predicate")
    else:
        require(False, "Unknown strategic condition: " + str(kind))


def validate(content, missions, graph, *, final=None):
    require(isinstance(graph, list) and len(graph) <= 64,
            "Strategic event graph must contain at most 64 nodes")
    ids, dependencies = set(), {}
    for node in graph:
        require(isinstance(node, dict)
                and set(node) == {"id", "when", "effects"}
                and _id(node["id"]) and node["id"] not in ids,
                "Invalid or duplicate strategic node id")
        ids.add(node["id"])
        deps = set()
        _condition(node["when"], content, missions, budget=[48], deps=deps)
        dependencies[node["id"]] = deps
        require(isinstance(node["effects"], list)
                and 1 <= len(node["effects"]) <= 8,
                "Strategic node requires 1..8 effects")
        for effect in node["effects"]:
            require(isinstance(effect, dict) and effect.get("kind") in EFFECTS,
                    "Invalid strategic effect")
            kind = effect["kind"]
            if kind == "signal":
                require(set(effect) == {"kind", "text"}
                        and isinstance(effect["text"], str)
                        and 0 < len(effect["text"]) <= 160,
                        "Invalid strategic signal")
                continue
            require(effect.get("front") in missions,
                    "Unknown strategic effect front")
            if kind in {"reduce_opposition", "reduce_strength"}:
                require(set(effect) == {"kind", "front", "amount"}
                        and type(effect["amount"]) is int
                        and 1 <= effect["amount"] <= 10000
                        and effect["front"] != final,
                        "Invalid strategic attrition or final boss target")
            elif kind in {"open_door", "disable_defense"}:
                require(set(effect) == {"kind", "front", "object"}
                        and isinstance(effect["object"], str),
                        "Invalid strategic object effect")
                obj = front_links._object(
                    content, missions, effect["front"], effect["object"])
                require(obj is not None and obj["kind"] ==
                        ("door" if kind == "open_door" else "defense"),
                        "Strategic object is missing or incompatible")
            elif kind == "block_reinforcements":
                require(set(effect) == {"kind", "front"},
                        "Invalid interdiction effect")
            elif kind == "set_doctrine":
                require(set(effect) == {"kind", "front", "doctrine"}
                        and effect["doctrine"] in {"hold", "assault", "delay", "retreat"},
                        "Invalid strategic doctrine")
    for id, deps in dependencies.items():
        require(deps <= ids and id not in deps,
                "Unknown or self-referencing strategic dependency")
    # Deterministic topological order; firing dependencies before dependents
    # allows one synchronization to cascade without hidden extra turns.
    order = []
    remaining = {k: set(v) for k, v in dependencies.items()}
    while remaining:
        ready = sorted(k for k, deps in remaining.items() if not deps)
        require(ready, "Cyclic strategic event dependencies")
        for key in ready:
            order.append(key)
            del remaining[key]
        for deps in remaining.values():
            deps.difference_update(ready)
    return order


def matches(session, expression):
    kind, value = next(iter(expression.items()))
    if kind == "all":
        return all(matches(session, n) for n in value)
    if kind == "any":
        return any(matches(session, n) for n in value)
    if kind == "not":
        return not matches(session, value)
    if kind == "turn_at_least":
        return session.timeline.turn >= value
    if kind == "front_status":
        return (session.timeline.fronts[value["front"]]["status"] ==
                value["status"])
    if kind == "fired":
        return value in session.fired_graph
    if kind == "battle_event":
        battle = session.battles.get(value["front"])
        field = front_links.EVENT_FIELDS[value["kind"]]
        return bool(battle and any(
            event["kind"] == value["kind"] and event.get(field) == value["value"]
            for event in battle.events))
    if kind == "timeline_event":
        return any(e["kind"] == value["kind"] and
                   e.get("front") == value["front"]
                   for e in session.timeline.events)
    raise AssertionError("Unvalidated strategic event condition")


def _apply(session, effect):
    kind = effect["kind"]
    if kind == "signal":
        session.timeline.events.append({
            "turn": session.timeline.turn,
            "kind": "strategic_signal", "text": effect["text"]})
        return
    front = effect["front"]
    if kind in {"reduce_opposition", "reduce_strength"}:
        front_links._reduce_force(
            session, front, effect["amount"],
            field="opposition" if kind == "reduce_opposition" else "strength",
            losing_team="enemy" if kind == "reduce_opposition" else "player",
            result="victory" if kind == "reduce_opposition" else "defeat")
    elif kind == "open_door":
        front_links._modify_object(session, front, effect["object"], {"open": True})
    elif kind == "disable_defense":
        front_links._modify_object(session, front, effect["object"], {"disabled": True})
    elif kind == "block_reinforcements":
        session.blocked_reinforcements.add(front)
        session.pending_reinforcements.pop(front, None)
        battle = session.battles.get(front)
        if battle is not None:
            front_links._suppress_waves(battle)
            battle.emit("reinforcements_blocked")
    elif kind == "set_doctrine":
        if session.timeline.fronts[front]["status"] == "active":
            session.timeline.set_doctrine(front, effect["doctrine"])


def synchronize(session):
    """Mutate only at a journaled command boundary, once per node."""
    if not session.initial_event_graph:
        return []
    index = {node["id"]: node for node in session.initial_event_graph}
    fired = []
    for id in session.graph_order:
        node = index[id]
        if id not in session.fired_graph and matches(session, node["when"]):
            for effect in node["effects"]:
                _apply(session, effect)
            session.fired_graph.add(id)
            session.timeline.events.append({
                "turn": session.timeline.turn, "kind": "strategic_event_fired",
                "id": id})
            fired.append(id)
    return fired


def upsert(blueprint, content, node):
    """Pure Studio operation: rejected edits leave the project untouched."""
    from .siege_authoring import validate_blueprint
    draft = deepcopy(blueprint)
    rows = draft.setdefault("event_graph", [])
    require(isinstance(node, dict) and "id" in node,
            "Strategic node requires an id")
    rows[:] = [row for row in rows if row["id"] != node["id"]] + [deepcopy(node)]
    validate_blueprint(draft, content, {draft["campaign_id"]})
    return draft


def remove(blueprint, content, node_id):
    from .siege_authoring import validate_blueprint
    draft = deepcopy(blueprint)
    require(any(row["id"] == node_id for row in draft.get("event_graph", [])),
            "Unknown strategic node")
    draft["event_graph"] = [
        row for row in draft["event_graph"] if row["id"] != node_id]
    if not draft["event_graph"]:
        draft.pop("event_graph")
    validate_blueprint(draft, content, {draft["campaign_id"]})
    return draft


def preview(blueprint, content, turns=8):
    """Read-only strategic projection; it never simulates tactical victories."""
    from .siege_authoring import make_session
    require(type(turns) is int and 0 <= turns <= 40,
            "Invalid strategic preview length")
    session = make_session(blueprint, content)
    rows = [{"turn": 0, "fired": [], "state": session.timeline.state()}]
    for _ in range(turns):
        before = set(session.fired_graph)
        session.advance()
        rows.append({"turn": session.timeline.turn,
                     "fired": sorted(session.fired_graph - before),
                     "state": session.timeline.state()})
    return rows

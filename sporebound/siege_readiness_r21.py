"""R21.C — Read-only siege preparation from canonical Battle/Front state.

A preview runs the *existing* object interaction on a detached Battle copy.
Only Battle.execute / MultiFrontSession.execute may commit a siege action.
No second gate damage formula, object registry, RNG advance or save format.
"""
from copy import deepcopy

from .model import RuleError, require

OPERABLE = frozenset({"ram", "catapult", "switch", "door"})


def _object(mission, object_id):
    return next((row for row in mission.objects if row["id"] == object_id), None)


def siege_operation_preview(battle, object_id):
    """Describe the exact immediate effect of an interaction if issued now.

    Does not predict turns, the future crew location, offscreen losses or RNG
    outcomes. The authoritative _interact handler decides legality and effect
    on a deep copy; no side effects can escape into the live Battle.
    """
    require(type(object_id) is str and bool(object_id), "Invalid siege object id")
    obj = _object(battle.mission, object_id)
    require(obj is not None and obj["kind"] in OPERABLE,
            "Unknown operable siege object")
    linked = _object(battle.mission, obj.get("link")) if "link" in obj else None
    before_gate = linked if linked is not None and linked["kind"] == "door" else None
    actor = battle.active
    result = {
        "object": object_id, "kind": obj["kind"],
        "actor": actor.id if actor is not None else None,
        "ready": False, "phase": "unavailable", "reason": None,
        "position": list(obj["pos"]), "next_position": None,
        "target_gate": before_gate["id"] if before_gate else None,
        "gate_hp": before_gate.get("hp") if before_gate else None,
        "gate_hp_after": None,
        "gate_open_after": None,
        "certainty": "current_state_only",
    }
    if battle.result or battle.deploying or actor is None or not actor.alive:
        result["reason"] = "No active eligible crew or battle is not started"
        return result

    shadow = deepcopy(battle)
    events_before = len(shadow.events)
    try:
        shadow._interact(shadow.active, object_id)
    except RuleError as error:
        result["reason"] = str(error)
        return result

    changed = _object(shadow.mission, object_id)
    target = (_object(shadow.mission, before_gate["id"])
              if before_gate is not None else None)
    events = shadow.events[events_before:]
    kinds = {row["kind"] for row in events}
    result["ready"] = True
    if "ram_advanced" in kinds:
        result["phase"] = "advance"
    elif "gate_breached" in kinds:
        result["phase"] = "breach"
    elif "siege_hit" in kinds:
        result["phase"] = "strike"
    elif obj["kind"] in {"switch", "door"}:
        result["phase"] = "open"
    else:
        result["phase"] = "interact"
    result["next_position"] = list(changed["pos"])
    if target is not None:
        result["gate_hp_after"] = target.get("hp")
        result["gate_open_after"] = bool(target.get("open", False))
    return result


def siege_front_readiness(session):
    """Current strategic facts, including unopened fronts and one-shot links.

    Unopened front entries are authored geometry plus committed overrides,
    explicitly labelled as such; they are not simulated tactical Battles.
    """
    result = {
        "turn": session.timeline.turn,
        "focused": session.timeline.focused,
        "fronts": [], "causal_links": [],
        "blocked_reinforcements": sorted(session.blocked_reinforcements),
        "operations": [],
        "certainty": "observed_or_authored_not_predicted",
    }
    for name in sorted(session.missions):
        strategic = session.timeline.fronts[name]
        live = session.battles.get(name)
        if live is not None:
            objects = live.mission.objects
        else:
            objects = deepcopy(session.content.missions[session.missions[name]].objects)
            overrides = session.front_overrides.get(name, {})
            for obj in objects:
                obj.update(deepcopy(overrides.get(obj["id"], {})))
        infrastructure = []
        for obj in sorted(objects, key=lambda item: item["id"]):
            if obj["kind"] == "door":
                infrastructure.append({
                    "id": obj["id"], "kind": "door",
                    "open": bool(obj.get("open", False)),
                    "hp": obj.get("hp"), "position": list(obj["pos"])})
            elif obj["kind"] in {"ram", "catapult"}:
                infrastructure.append({
                    "id": obj["id"], "kind": obj["kind"],
                    "hp": obj.get("hp", obj.get("max_hp")),
                    "position": list(obj["pos"]), "team": obj.get("team", "player")})
        result["fronts"].append({
            "id": name, "mission": session.missions[name],
            "focus": name == session.timeline.focused,
            "materialized": live is not None,
            "source": "live" if live is not None else "authored_plus_committed_overrides",
            "status": strategic["status"],
            "strength": strategic["strength"],
            "opposition": strategic["opposition"],
            "doctrine": strategic["doctrine"],
            "infrastructure": infrastructure,
        })
    result["causal_links"] = [
        {"id": link["id"], "source": link["source"],
         "event": link["event"], "match": deepcopy(link["match"]),
         "targets": sorted({effect["front"] for effect in link["effects"]}),
         "applied": link["id"] in session.applied_links}
        for link in sorted(session.links, key=lambda item: item["id"])]
    current = session.active
    if not current.result and not current.deploying:
        result["operations"] = [
            siege_operation_preview(current, obj["id"])
            for obj in sorted(current.mission.objects, key=lambda item: item["id"])
            if obj["kind"] in OPERABLE]
    return result

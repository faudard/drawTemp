"""2.5.4.4 — transactional authoring for existing SiegeCampaign/RoutesPolicy.

Only existing game-engine policy fields are authored.  Mutations validate
against the *real* MultiFrontSession constructor before returning a blueprint.
No outcome, victory, replay entry or runtime choice is synthesized here.
"""
from copy import deepcopy

from .model import require
from .siege_authoring import validate_blueprint

OUTCOMES = ("victory", "partial", "negotiated", "reclaimed")


def validate(bp, content):
    validate_blueprint(bp, content, {bp["campaign_id"]})
    # The schema validator alone does not instantiate the opt-in route policy.
    from .siege_authoring import make_session
    return make_session(bp, content)


def commit(bp, content, spec):
    updated = deepcopy(bp)
    updated["campaign"] = deepcopy(spec)
    validate(updated, content)
    return updated


def _campaign(bp):
    require(bp.get("campaign") is not None,
            "Define a final sector and at least one prerequisite first")
    return deepcopy(bp["campaign"])


def _routes(spec):
    require("routes" in spec, "Enable alternative routes first")
    return spec["routes"]


def enable(bp, content, *, alternative="direct"):
    spec = _campaign(bp)
    require("routes" not in spec, "Alternative routes already enabled")
    require(alternative != "breach" and isinstance(alternative, str)
            and 0 < len(alternative) <= 64
            and all(c.isalnum() or c in "_-" for c in alternative),
            "Invalid alternative route id")
    require("logistics" in bp and "supplies" in bp["logistics"],
            "Alternative routes require configured strategic supplies")
    spec["routes"] = {
        "breach": {"required": deepcopy(spec["required_fronts"]),
                   "supplies": 0, "strength_loss": 0},
        alternative: {"required": {}, "supplies": 1, "strength_loss": 1},
    }
    spec["recovery"] = {}
    spec["treaties"] = {}
    return commit(bp, content, spec)


def disable(bp, content):
    spec = _campaign(bp)
    require("routes" in spec, "Alternative routes not enabled")
    for key in ("routes", "recovery", "treaties", "counteroffensives"):
        spec.pop(key, None)
    return commit(bp, content, spec)


def route(bp, content, name, prerequisites, supplies, strength_loss):
    spec = _campaign(bp)
    routes = _routes(spec)
    require(isinstance(name, str) and name and len(name) <= 64 and
            all(c.isalnum() or c in "_-" for c in name), "Invalid route id")
    routes[name] = {"required": deepcopy(prerequisites),
                    "supplies": supplies, "strength_loss": strength_loss}
    return commit(bp, content, spec)


def delete_route(bp, content, name):
    spec = _campaign(bp)
    routes = _routes(spec)
    require(name != "breach" and name in routes, "Cannot remove the breach route")
    require(len(routes) > 2, "Disable alternative routes to remove the last option")
    del routes[name]
    return commit(bp, content, spec)


def partial(bp, content, front, event, obj, cost, target, loss):
    spec = _campaign(bp)
    spec["partial"][front] = {"event": event, "object": obj, "cost": cost,
                              "target": target, "target_loss": loss}
    return commit(bp, content, spec)


def negotiation(bp, content, front, supplies, target, loss):
    spec = _campaign(bp)
    spec["negotiation"][front] = {"supplies": supplies, "target": target,
                                  "target_loss": loss}
    return commit(bp, content, spec)


def retreat(bp, content, front, target, loss):
    spec = _campaign(bp)
    spec["retreat"][front] = {"target": target, "target_loss": loss}
    return commit(bp, content, spec)


def delete_choice(bp, content, category, front):
    require(category in {"partial", "negotiation", "retreat"}, "Unknown outcome type")
    spec = _campaign(bp)
    require(front in spec[category], "Unknown campaign outcome")
    del spec[category][front]
    return commit(bp, content, spec)


def treaty(bp, content, front, source, event, obj, stand_down):
    spec = _campaign(bp)
    require("routes" in spec, "Enable alternative routes before a treaty")
    require(front in spec["negotiation"],
            "Add the negotiation cost and target to this front first")
    row = {"requires_front": source, "event": event, "object": obj}
    if stand_down:
        row["final_stand_down"] = list(stand_down)
    spec["treaties"][front] = row
    return commit(bp, content, spec)


def delete_treaty(bp, content, front):
    spec = _campaign(bp)
    require("routes" in spec and front in spec["treaties"],
            "Unknown treaty")
    del spec["treaties"][front]
    return commit(bp, content, spec)


def recovery(bp, content, front, mission, supplies, strength_loss, reclaimed_strength):
    spec = _campaign(bp)
    require("routes" in spec, "Enable alternative routes before reconquest")
    spec["recovery"][front] = {
        "mission": mission, "supplies": supplies,
        "strength_loss": strength_loss,
        "reclaimed_strength": reclaimed_strength}
    return commit(bp, content, spec)


def delete_recovery(bp, content, front):
    spec = _campaign(bp)
    require("routes" in spec and front in spec["recovery"], "Unknown recovery")
    require(front not in spec.get("counteroffensives", {}),
            "Remove the counteroffensive first")
    del spec["recovery"][front]
    return commit(bp, content, spec)


def counteroffensive(bp, content, front, after_turn, mission, strength_loss, opposition_gain):
    spec = _campaign(bp)
    require("routes" in spec and front in spec["recovery"],
            "Configure a reconquest mission for this front first")
    spec.setdefault("counteroffensives", {})[front] = {
        "after_turn": after_turn, "mission": mission,
        "strength_loss": strength_loss, "opposition_gain": opposition_gain}
    return commit(bp, content, spec)


def delete_counteroffensive(bp, content, front):
    spec = _campaign(bp)
    require(front in spec.get("counteroffensives", {}),
            "Unknown counteroffensive")
    del spec["counteroffensives"][front]
    if not spec["counteroffensives"]:
        spec.pop("counteroffensives")
    return commit(bp, content, spec)


def preview(bp, content):
    session = validate(bp, content)
    campaign = session.campaign.state(session)
    return {
        "route": campaign.get("route", "breach"),
        "available": sorted(session.route_policy.routes)
            if session.route_policy else ["breach"],
        "locked": not campaign["unlocked"],
        "required": deepcopy(campaign["required"]),
        "supply_pool": (deepcopy(session.logistics.supplies)
                        if session.logistics is not None else None),
        "recovery": sorted(session.route_policy.recovery)
            if session.route_policy else [],
        "treaties": sorted(session.route_policy.treaties)
            if session.route_policy else [],
        "counteroffensives": sorted(session.route_policy.counteroffensives)
            if session.route_policy else [],
    }

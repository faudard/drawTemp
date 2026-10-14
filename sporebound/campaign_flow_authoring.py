"""R5.13 visual Campaign Flow authoring commands (no Tk, no new schema).

All operations produce a fully validated GameProject. The existing Studio
history records one committed project snapshot per user action.
"""
from __future__ import annotations

from copy import deepcopy

from .game_project import GameProject
from .model import require
from .narrative import _condition
from .story_conditions import predicate, typed_value, update_expression


TARGETS = ("gate", "ending")
OUTCOMES = ("victory", "defeat")
EFFECTS = ("set_flag", "add_flag", "unlock_mission", "recruit_hero",
           "grant_item", "equip_hero", "gold", "wound", "heal_wound")


def _commit(project, content, flow):
    payload = project.to_dict()
    # An empty campaign_flow is intentionally absent from legacy projects.
    if any(flow.get(section) for section in ("gates", "outcomes", "endings")):
        payload["campaign_flow"] = flow
    else:
        payload.pop("campaign_flow", None)
    return GameProject.from_dict(payload, content)


def condition_for(project, target, name):
    require(target in TARGETS, "Unknown campaign condition target")
    section = "gates" if target == "gate" else "endings"
    return deepcopy(project.campaign_flow.get(section, {}).get(name))


def change_condition(project, content, target, name, action, *,
                     path=(), kind="flag_eq", key="", value="", operator="all"):
    """Create, replace, append, wrap or delete a selected condition node."""
    require(target in TARGETS, "Unknown campaign condition target")
    if target == "gate":
        require(name in content.missions, "Unknown gated mission")
    else:
        # The existing validation checks safe new ending ids.
        require(isinstance(name, str) and bool(name), "Missing ending id")
    expression = condition_for(project, target, name)
    if action in {"replace", "append"}:
        leaf = predicate(kind, key, value, content=content)
    else:
        leaf = None
    result = update_expression(expression, action, path=path, leaf=leaf,
                               operator=operator)
    if result is not None:
        _condition(result, content)
    flow = deepcopy(project.campaign_flow)
    section = flow.setdefault("gates" if target == "gate" else "endings", {})
    if result is None:
        section.pop(name, None)
        if not section:
            flow.pop("gates" if target == "gate" else "endings", None)
    else:
        section[name] = result
    return _commit(project, content, flow)


def build_effect(kind, name="", value="", *, content=None):
    """Typed form values, never raw effect JSON from a user-facing control."""
    require(kind in EFFECTS, "Unknown campaign consequence")
    name = name.strip()
    value = value.strip()
    if kind == "set_flag":
        effect = {"kind": kind, "flag": name, "value": typed_value(value)}
    elif kind == "add_flag":
        number = typed_value(value)
        require(type(number) is int, "Flag increment requires an integer")
        effect = {"kind": kind, "flag": name, "amount": number}
    elif kind == "unlock_mission":
        effect = {"kind": kind, "mission": name}
    elif kind == "recruit_hero":
        effect = {"kind": kind, "hero": name}
    elif kind == "grant_item":
        number = typed_value(value)
        require(type(number) is int, "Item quantity requires an integer")
        effect = {"kind": kind, "item": name, "quantity": number}
    elif kind == "equip_hero":
        effect = {"kind": kind, "hero": name, "item": value}
    elif kind == "gold":
        number = typed_value(value)
        require(type(number) is int, "Gold delta requires an integer")
        effect = {"kind": kind, "amount": number}
    else:
        effect = {"kind": kind, "hero": name, "wound": value}
    if content is not None:
        # Exact canonical flow validation, including the existing narrative
        # effect vocabulary and known tactical heroes/equipment.
        from .campaign_flow import validate_flow
        mission = next(iter(content.missions))
        validate_flow({"outcomes": {mission: {"victory": [effect]}}}, content)
    return effect


def effect_fields(effect):
    """Populate the two form fields from one canonical effect."""
    kind = effect["kind"]
    if kind in {"set_flag", "add_flag"}:
        return kind, effect["flag"], str(effect.get("value", effect.get("amount", ""))).lower() if type(effect.get("value")) is bool else str(effect.get("value", effect.get("amount", "")))
    if kind == "unlock_mission":
        return kind, effect["mission"], ""
    if kind == "recruit_hero":
        return kind, effect["hero"], ""
    if kind == "grant_item":
        return kind, effect["item"], str(effect["quantity"])
    if kind == "equip_hero":
        return kind, effect["hero"], effect["item"]
    if kind == "gold":
        return kind, "", str(effect["amount"])
    return kind, effect["hero"], effect["wound"]


def outcome_effects(project, mission, result):
    require(result in OUTCOMES, "Unknown mission result")
    return deepcopy(project.campaign_flow.get("outcomes", {}).get(mission, {}).get(result, []))


def change_effect(project, content, mission, result, action, *,
                  index=None, effect=None, destination=None):
    """Transactional list editing; reject invalid indexes and excess effects."""
    require(mission in content.missions, "Unknown consequence mission")
    require(result in OUTCOMES, "Unknown mission result")
    require(action in {"add", "replace", "delete", "move"}, "Unknown effect operation")
    flow = deepcopy(project.campaign_flow)
    outcomes = flow.setdefault("outcomes", {})
    by_result = outcomes.setdefault(mission, {})
    effects = by_result.setdefault(result, [])
    if action == "add":
        require(isinstance(effect, dict) and len(effects) < 20,
                "Maximum 20 effects per outcome")
        effects.append(deepcopy(effect))
    else:
        require(type(index) is int and 0 <= index < len(effects),
                "Select an existing effect")
        if action == "replace":
            require(isinstance(effect, dict), "Expected effect")
            effects[index] = deepcopy(effect)
        elif action == "delete":
            effects.pop(index)
        else:
            require(type(destination) is int and
                    0 <= destination < len(effects),
                    "Effect destination is outside the list")
            effects.insert(destination, effects.pop(index))
    if not effects:
        by_result.pop(result)
    if not by_result:
        outcomes.pop(mission)
    if not outcomes:
        flow.pop("outcomes", None)
    return _commit(project, content, flow)


def preview_condition(project, target, name, progress):
    """Read-only evaluation against the actual or new-game campaign snapshot."""
    from .narrative import matches
    expr = condition_for(project, target, name)
    if expr is None:
        return {"defined": False, "matches": target == "gate",
                "expression": None}
    return {"defined": True, "matches": matches(expr, progress),
            "expression": expr}

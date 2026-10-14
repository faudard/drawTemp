"""R5.B Campaign Flow: project-owned conditions and verified cross-mission effects.

Keeps Content.next_missions and StoryBook as the canonical routing/choice engines.
No effects are run inside Battle; only authenticated mission settlement commits them.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from .model import require
from .narrative import _condition, _effect, matches


def definition_digest(flow):
    if not flow:
        return ""
    return hashlib.sha256(json.dumps(flow, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_flow(flow, content):
    require(isinstance(flow, dict) and set(flow) <= {"gates", "outcomes", "endings"},
            "Campaign flow must contain gates, outcomes and/or endings")
    require(len(flow.get("gates", {})) <= 256 and
            len(flow.get("outcomes", {})) <= 256 and
            len(flow.get("endings", {})) <= 64, "Campaign flow exceeds authoring limits")
    gates, outcomes, endings = (flow.get(key, {}) for key in
                               ("gates", "outcomes", "endings"))
    require(all(isinstance(x, dict) for x in (gates, outcomes, endings)),
            "Campaign flow sections must be objects")
    for mission, condition in gates.items():
        require(mission in content.missions, "Unknown gated mission: " + str(mission))
        _condition(condition, content)
    from .character_growth31 import WOUNDS
    heroes = {unit.id for mission in content.missions.values()
              for unit in mission.units if unit.team == "player"}
    for mission, results in outcomes.items():
        require(mission in content.missions and isinstance(results, dict) and
                bool(results) and set(results) <= {"victory", "defeat"},
                "Invalid mission consequence")
        for outcome, effects in results.items():
            require(isinstance(effects, list) and len(effects) <= 20,
                    "Invalid consequence effects")
            for effect in effects:
                require(isinstance(effect, dict), "Consequence must be an object")
                if effect.get("kind") in {"wound", "heal_wound"}:
                    require(set(effect) == {"kind", "hero", "wound"} and
                            effect["hero"] in heroes and effect["wound"] in WOUNDS,
                            "Unknown hero or wound in campaign consequence")
                else:
                    _effect(effect, content)
    for ending, condition in endings.items():
        require(isinstance(ending, str) and 0 < len(ending) <= 64 and
                all(c.isalnum() or c in "-_" for c in ending),
                "Invalid campaign ending id")
        _condition(condition, content)


def verify_save(progress, flow):
    """Legacy slots remain valid for legacy projects; newly authored flows
    require an explicit migration, never a silent reinterpretation of a slot.
    """
    require(progress.flow_digest == definition_digest(flow),
            "Campaign flow differs from saved campaign; explicit migration required")
    require(all(isinstance(key, str) and key.count(":") == 1 and
                key.rsplit(":", 1)[1] in {"victory", "defeat"}
                for key in progress.flow_ledger), "Invalid campaign consequence ledger")


def available_missions(progress, flow):
    gates = flow.get("gates", {})
    return [mid for mid in progress.unlocked if mid not in progress.completed
            and (mid not in gates or matches(gates[mid], progress))]


def _apply_effect(progress, effect):
    kind = effect["kind"]
    if kind == "set_flag":
        progress.story_flags[effect["flag"]] = deepcopy(effect["value"])
    elif kind == "add_flag":
        before = progress.story_flags.get(effect["flag"], 0)
        require(type(before) is int, "Cannot add to a non-numeric campaign flag")
        updated = before + effect["amount"]
        require(-1000000 <= updated <= 1000000, "Campaign flag out of bounds")
        progress.story_flags[effect["flag"]] = updated
    elif kind == "gold":
        updated = progress.gold + effect["amount"]
        require(0 <= updated <= 1000000, "Campaign gold out of bounds")
        progress.gold = updated
    elif kind == "grant_item":
        name = effect["item"]
        amount = progress.inventory.get(name, 0) + effect["quantity"]
        require(amount <= 1000000, "Campaign inventory out of bounds")
        progress.inventory[name] = amount
    elif kind == "unlock_mission":
        if effect["mission"] not in progress.unlocked:
            progress.unlocked.append(effect["mission"])
    elif kind == "recruit_hero":
        uid = effect["hero"]
        require(not progress.story_flags.get("recruited_" + uid, False),
                "Campaign hero already recruited")
        progress.hero(uid)
        progress.story_flags["recruited_" + uid] = True
    elif kind == "equip_hero":
        uid = effect["hero"]
        require(not any("recruit:" + uid in unit.tags
                        for mission in progress._flow_content.missions.values()
                        for unit in mission.units)
                or progress.story_flags.get("recruited_" + uid) is True,
                "Hero has not been recruited")
        progress.equip(progress._flow_content, uid, effect["item"])
    elif kind in {"wound", "heal_wound"}:
        wounds = progress.hero(effect["hero"]).wounds
        if kind == "wound":
            if effect["wound"] not in wounds:
                require(len(wounds) < 2, "Maximum persistent hero wounds reached")
                wounds.append(effect["wound"])
        elif effect["wound"] in wounds:
            wounds.remove(effect["wound"])


def settle(progress, flow, mission, result, *, content=None):
    """Return a new progress snapshot; never mutate the provided live campaign.

    A defeat may precede a later victory, but each outcome is committed at most
    once per mission. The outer GameSession/PlayerSession persists atomically.
    """
    verify_save(progress, flow)
    require(result in {"victory", "defeat"}, "Campaign outcome is not final")
    effects = flow.get("outcomes", {}).get(mission, {}).get(result, [])
    key = mission + ":" + result
    if key in progress.flow_ledger or not effects:
        return progress
    updated = deepcopy(progress)
    # equip_hero uses the exact validated tactical Content (never side data).
    if any(effect["kind"] == "equip_hero" for effect in effects):
        require(content is not None, "Equipment consequence requires Content")
        updated._flow_content = content
    try:
        for effect in effects:
            _apply_effect(updated, effect)
    finally:
        if hasattr(updated, "_flow_content"):
            del updated._flow_content
    require(len(updated.flow_ledger) < 512, "Campaign consequence ledger exhausted")
    updated.flow_ledger.append(key)
    return updated


def inspect_campaign(progress, flow):
    """Read-only inspector shared by Studio, CLI and independent Player."""
    verify_save(progress, flow)
    flags = deepcopy(progress.story_flags)
    prefixes = {
        "reputation": ("reputation_", "trust_"),
        "supplies": ("supplies_", "provisions_"),
        "fortifications": ("fortification_", "gate_", "wall_"),
        "allies": ("allies_", "recruited_"),
        "enemies": ("enemy_",),
    }
    return {
        "variables": flags,
        "reputation": {k: v for k, v in flags.items() if k.startswith(prefixes["reputation"])},
        "resources": {"gold": progress.gold, "inventory": deepcopy(progress.inventory),
                      "supplies": {k: v for k, v in flags.items()
                                   if k.startswith(prefixes["supplies"])}},
        "companions": {k: {"job": h.job, "morale": h.morale,
                            "wounds": list(h.wounds)}
                       for k, h in sorted(progress.heroes.items())},
        "fortifications": {k: v for k, v in flags.items()
                           if k.startswith(prefixes["fortifications"])},
        "allies": {k: v for k, v in flags.items() if k.startswith(prefixes["allies"])},
        "enemies": {k: v for k, v in flags.items() if k.startswith(prefixes["enemies"])},
        "missions": {"unlocked": list(progress.unlocked),
                     "available": available_missions(progress, flow),
                     "completed": list(progress.completed),
                     "blocked": [mid for mid in progress.unlocked
                                 if mid not in progress.completed
                                 and mid not in available_missions(progress, flow)]},
        "endings": [eid for eid, condition in flow.get("endings", {}).items()
                    if matches(condition, progress)],
        "consequences": list(progress.flow_ledger),
    }


def audit_campaign(content, project, campaign_id):
    """Deterministic structural gate, not a claim of exhaustive choice coverage.

    Choice outcomes and story flags may change during dialogue. Those pathways
    need the runtime save/replay tests; this audit reports them as limitations.
    """
    from .campaign_graph import inspect_graph
    project.validate(content)
    campaign = project.campaign(campaign_id)
    require(campaign is not None, "Unknown campaign")
    graph = inspect_graph(content, [campaign["start_mission"]])
    flow = project.campaign_flow
    reachable = set(graph["reachable"])
    gated = sorted(set(flow.get("gates", {})) & reachable)
    impossible = sorted(mid for mid in gated
                        if (flow["gates"][mid].get("completed_mission") == mid))
    missing = sorted(set(flow.get("gates", {})) - reachable)
    endings = sorted(flow.get("endings", {}))
    warnings = ([f"Graph-unreachable gated mission: {mid}" for mid in missing]
                + ["Conditional dialogue effects require runtime scenario certification"]
                if gated else [])
    errors = [f"Mission requires its own completion: {mid}" for mid in impossible]
    if endings and not reachable:
        errors.append("No reachable mission for authored campaign endings")
    return {
        "campaign": campaign_id, "start": campaign["start_mission"],
        "reachable": sorted(reachable), "unreachable": graph["unreachable"],
        "terminal": [mid for mid in graph["terminal"] if mid in reachable],
        "cycles": graph["cycles"], "gated": gated, "endings": endings,
        "errors": errors, "warnings": warnings,
        "scope": "Structural reachability only; interactive paths need GameSession replay",
    }

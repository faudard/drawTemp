"""R53.B1: author party defaults and cooperative skills via one R1 transaction.

The Studio edits only GameProject. R41 Party and Campaign stay authoritative
for runtime roster, hero progression, HP, inventory and rewards.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.party_authoring import inspect_party
from sporebound.classic_party import EXTENSION
from sporebound.model import require
from sporebound.party_orchestration import PAUSE_POLICY, SLOTS


@dataclass(frozen=True)
class OrchestrationDraft:
    plan: object
    campaign: str
    before: dict | None
    after: dict
    revision: int


def _pair(snapshot):
    return snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot


def inspect_orchestration(snapshot, campaign_id):
    pair = _pair(snapshot)
    roster = inspect_party(pair, campaign_id)
    require(roster["enabled"], "Configure an R41 party before using R53")
    spec = pair["project"]["extensions"][EXTENSION]["data"].get("orchestration")
    active = list(roster["selection"]["active"])
    defaults = (spec or {}).get("defaults", {}).get(campaign_id, {})
    return {
        "campaign": campaign_id, "revision": pair.get("revision", 0),
        "enabled": spec is not None, "active": active,
        "recruitable": list(roster["selection"]["recruitable"]),
        "leader": defaults.get("leader", active[0]),
        "formation": list(defaults.get("formation", SLOTS[:len(active)])),
        "slots": list(SLOTS), "pause_policy": PAUSE_POLICY,
        "combos": deepcopy(spec.get("combos", []) if spec else []),
    }


def native_damage_choices(snapshot, hero_id):
    """Native enemy-damage skills for the first canonical player template."""
    pair = _pair(snapshot)
    player = None
    for mission in pair["content"]["missions"]:
        for unit in mission["units"]:
            if unit["team"] == "player" and unit["id"] == hero_id:
                player = unit
                break
        if player is not None:
            break
    if player is None:
        return ()
    skills = {skill["id"]: skill for skill in pair["content"]["skills"]}
    choices = []
    for skill_id in player["skills"]:
        skill = skills.get(skill_id)
        if skill is not None and skill.get("target", "enemy") == "enemy" and (
                skill.get("effects") and
                all(effect["kind"] == "damage" for effect in skill["effects"])):
            choices.append((skill_id, skill.get("name", skill_id)))
    return tuple(choices)


def combo_impact_preview(snapshot, combos):
    """Show native skill MP/effect stats, never fabricated live damage."""
    pair = _pair(snapshot)
    skills = {skill["id"]: skill for skill in pair["content"]["skills"]}
    heroes = {}
    for mission in pair["content"]["missions"]:
        for unit in mission["units"]:
            if unit["team"] == "player":
                heroes.setdefault(unit["id"], unit)
    result = []
    for combo in combos:
        details = {
            "id": combo["id"], "members": list(combo["members"]),
            "modes": list(combo["modes"]), "executable_rpg": "skills" in combo,
            "native_skills": [],
        }
        if "skills" in combo:
            for hero_id in combo["members"]:
                skill_id = combo["skills"][hero_id]
                skill = skills[skill_id]
                unit = heroes[hero_id]
                details["native_skills"].append({
                    "hero": hero_id, "skill": skill_id,
                    "mp_cost": skill.get("cost", 0),
                    "attack": unit.get("attack", 0),
                    "weapon_power": unit.get("weapon_power", 0),
                    "effects": [{"kind": e["kind"], "power": e.get("power", 0)}
                                for e in skill["effects"]],
                })
        result.append(details)
    return result


def preview_orchestration_edit(session: AuthoringSession, campaign_id, *,
                               leader, formation, combos, expected_revision=None):
    snapshot = session.snapshot()
    before = inspect_orchestration(snapshot, campaign_id)
    if expected_revision is not None:
        require(type(expected_revision) is int
                and expected_revision == snapshot.revision,
                "Stale Party Composer preview; refresh required")
    require(type(leader) is str and leader in before["active"],
            "R53 leader must belong to the authored active roster")
    require(type(formation) is list and len(formation) == len(before["active"])
            and all(type(slot) is str and slot in SLOTS for slot in formation)
            and len(set(formation)) == len(formation),
            "R53 formation must have one distinct slot per active hero")
    require(type(combos) is list and len(combos) <= 64,
            "R53 combo catalogue is bounded")
    defaults = {"leader": leader, "formation": list(formation)}

    def update(project):
        data = project["extensions"][EXTENSION]["data"]
        spec = deepcopy(data.get("orchestration", {
            "version": 1, "pause_policy": PAUSE_POLICY, "combos": [],
        }))
        spec["combos"] = deepcopy(combos)
        spec.setdefault("defaults", {})[campaign_id] = deepcopy(defaults)
        data["orchestration"] = spec
        return project

    plan = session.preview_project(update, kind="r53.party.compose")
    after = {"leader": leader, "formation": list(formation),
             "combos": deepcopy(combos)}
    return OrchestrationDraft(
        plan, campaign_id, deepcopy(before) if before["enabled"] else None,
        after, snapshot.revision)


def apply_orchestration_edit(session: AuthoringSession, draft: OrchestrationDraft):
    require(isinstance(draft, OrchestrationDraft),
            "R53 Party Composer requires a validated preview")
    return session.apply(draft.plan)


__all__ = [
    "OrchestrationDraft", "inspect_orchestration", "combo_impact_preview",
    "native_damage_choices",
    "preview_orchestration_edit", "apply_orchestration_edit",
]

"""Deterministic, opt-in morale and command rules for compact tactical squads.

Every state is derived from an existing battle snapshot (HP, corpses, positions,
tags). No RNG, invisible turn mutation or parallel combat engine. Rally is an
ordinary Battle.execute command; its tag is part of replay checksums.
"""
from __future__ import annotations

from .model import distance, require

STATES = ("steady", "shaken", "wavering", "routing")
DAMAGE_PERCENT = (100, 90, 80, 65)


def morale_snapshot(battle, actor_id):
    """Pure, readable morale and its causes, including the next counterplay."""
    actor = battle.unit(actor_id) if isinstance(actor_id, str) else actor_id
    base = next((tag.split(":", 1)[1] for tag in actor.tags
                 if tag.startswith("morale:") and tag.split(":", 1)[1] in STATES), "steady")
    pressure = STATES.index(base)
    reasons = []
    if actor.hp * 4 <= actor.max_hp:
        pressure += 2
        reasons.append("critical_wound")
    elif actor.hp * 2 <= actor.max_hp:
        pressure += 1
        reasons.append("wounded")
    comrades = [u for u in battle.units if u.team == actor.team and u.id != actor.id]
    alive = [u for u in comrades if u.alive]
    fallen = [u for u in comrades if not u.alive and u.kind != "summon"]
    if fallen:
        pressure += 1  # one casualty event, independent of unit counts
        reasons.append("comrade_down")
    # A missing leader is not the same as one who was never on the roster.
    if "bandit" in actor.tags and any("leader" in u.tags and "bandit" in u.tags
                                       and not u.alive for u in comrades):
        pressure += 1
        reasons.append("captain_down")
    enemies = [u for u in battle.units if u.alive and u.team != actor.team]
    close_enemies = sum(distance(u.pos, actor.pos) <= 2 for u in enemies)
    close_allies = sum(distance(u.pos, actor.pos) <= 2 for u in alive)
    if close_enemies >= 2 and close_allies == 0:
        pressure += 1
        reasons.append("outnumbered")
    if "morale:rallied" in actor.tags:
        pressure -= 2
        reasons.append("rallied")
    index = min(3, max(0, pressure))
    return {"unit": actor.id, "team": actor.team, "state": STATES[index],
            "pressure": index, "reasons": reasons, "damage_percent": DAMAGE_PERCENT[index],
            "certainty": "current", "can_be_rallied": index > 0 and "morale:rallied" not in actor.tags}


def rally(battle, actor, command):
    """One visible command, one action: rally a threatened ally within two cells."""
    require(set(command) <= {"kind", "unit", "target"}, "Unexpected rally field")
    require("leader" in actor.tags and actor.alive, "Only a living leader can rally")
    require(not actor.acted and not battle.status_blocks(actor, "act"), "Rally unavailable")
    uid = command.get("target")
    require(isinstance(uid, str) and bool(uid), "Rally requires an ally id")
    ally = next((u for u in battle.units if u.id == uid), None)
    require(ally is not None and ally.alive and ally.team == actor.team
            and ally.id != actor.id and distance(ally.pos, actor.pos) <= 2,
            "Ally not within rally range")
    before = morale_snapshot(battle, ally)
    require(before["can_be_rallied"], "Ally has no rallyable morale pressure")
    ally.tags.append("morale:rallied")
    actor.acted = True
    after = morale_snapshot(battle, ally)
    battle.emit("morale_rally", unit=actor.id, target=ally.id,
                before=before["state"], after=after["state"])


def install_morale(rules):
    """Versioned rule contract: older 3.1 replays reject new formulas explicitly."""
    from .rules.registry import CommandRule, FormulaRule

    original_damage = rules.formulas.get("damage").calculate

    def damage(battle, caster, target, skill, effect):
        amount = original_damage(battle, caster, target, skill, effect)
        # Crossbows are tactically vulnerable while empty; both forecast and
        # actual melee impact use exactly this rule.
        if ("reload:empty" in target.tags and skill.id == "attack"
                and caster.weapon in {"melee", "spear", "unarmed"}
                and not skill.magical):
            amount = amount * 6 // 5
        # Never penalize legacy actors without an opted-in doctrine/morale.
        if not any(tag.startswith(("doctrine:", "morale:")) for tag in caster.tags):
            return amount
        percent = morale_snapshot(battle, caster)["damage_percent"]
        return amount * percent // 100

    commands = rules.commands.with_rule("rally", CommandRule(rally, version="3.1.7"))
    formulas = rules.formulas.with_rule(
        "damage", FormulaRule(damage, version="3.1.7-morale"), replace_existing=True)
    return rules.with_family("commands", commands).with_family("formulas", formulas)

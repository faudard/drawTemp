"""Opt-in formations: real combat modifiers and explicit tactical commands (2.7.2).

Formation state lives in Unit.tags and is therefore part of Battle.state(),
save/replay checksums and normal atomic command rollback. Legacy rules are unchanged.
"""
from __future__ import annotations

from .model import distance, require

MODES = ("none", "shield_wall", "phalanx", "escort")
PREFIX = "formation:"


def _formation_tag(unit):
    return next((t for t in unit.tags if t.startswith(PREFIX)), "")


def _same_level(battle, actor, other):
    """Formations use authored deck membership, not overlapping 2D coordinates."""
    return battle.unit_levels.get(actor.id, 0) == battle.unit_levels.get(other.id, 0)


def _allied(battle, actor, *, mode):
    return [u for u in battle.units if u.alive and u.id != actor.id
            and u.team == actor.team and _same_level(battle, actor, u)
            and distance(u.pos, actor.pos) == 1
            and _formation_tag(u) == PREFIX + mode]


def shield_wall(battle, target):
    return (_formation_tag(target) == PREFIX + "shield_wall"
            and bool(_allied(battle, target, mode="shield_wall")))


def phalanx(battle, attacker):
    return (attacker.weapon == "spear"
            and _formation_tag(attacker) == PREFIX + "phalanx"
            and any(u.weapon == "spear" for u in _allied(battle, attacker, mode="phalanx")))


def escorted(battle, target):
    return any(u.alive and u.team == target.team and u.id != target.id
               and _formation_tag(u) == PREFIX + "escort:" + target.id
               and _same_level(battle, u, target)
               and distance(u.pos, target.pos) == 1 for u in battle.units)


def formation_preview(battle, unit_id):
    """Pure explanation of active and broken stances, including floor ownership."""
    unit = next((u for u in battle.units if u.id == unit_id), None)
    require(unit is not None, "Unknown formation unit")
    level = battle.unit_levels.get(unit.id, 0)
    # The ground board has no authority over upper-deck cover/elevation.
    tile = battle.board.tile(unit.pos) if level == 0 else None
    mode = _formation_tag(unit)[len(PREFIX):] or "none"
    wall = bool(shield_wall(battle, unit))
    spear = bool(phalanx(battle, unit))
    protected = bool(escorted(battle, unit))
    target_id = mode.partition(":")[2] if mode.startswith("escort:") else ""
    providing = any(
        ally.id == target_id and ally.alive and ally.team == unit.team
        and _same_level(battle, unit, ally)
        and distance(ally.pos, unit.pos) == 1
        for ally in battle.units) if target_id else False
    partners = (sorted(ally.id for ally in _allied(battle, unit, mode=mode))
                if mode in {"shield_wall", "phalanx"} else
                ([target_id] if providing else []))
    active = wall or spear or providing
    reason = None
    if mode == "shield_wall" and not wall:
        reason = "adjacent_shield_partner_required_on_same_floor"
    elif mode == "phalanx" and not spear:
        reason = "adjacent_spear_partner_required_on_same_floor"
    elif mode.startswith("escort:") and not providing:
        reason = "escort_target_required_adjacent_on_same_floor"
    return {"unit": unit.id, "mode": mode,
            "level": level,
            "shield_wall": wall, "phalanx": spear, "escort": protected,
            "providing_escort": providing, "formation_active": bool(active),
            "partners": partners, "break_reason": reason,
            "terrain_cover": tile.cover if tile else 0,
            "elevation": tile.height if tile else 0,
            "fortified": bool(wall and tile and tile.cover >= 20)}


def set_formation(battle, actor, command):
    """Existing activation must spend its action; accepts one explicit mode."""
    require(set(command) <= {"kind", "unit", "mode", "target"}, "Unexpected formation field")
    require(not actor.acted and not battle.status_blocks(actor, "act"), "Action already spent")
    mode = command.get("mode")
    require(mode in MODES, "Unknown formation")
    target = command.get("target")
    if mode == "escort":
        require(isinstance(target, str), "Escort requires a target id")
        protected = next((u for u in battle.units if u.id == target), None)
        require(protected is not None and protected.alive
                and protected.team == actor.team and protected.id != actor.id,
                "Escort target must be a living ally")
        require(_same_level(battle, actor, protected),
                "Escort target is on a different floor")
        require(distance(actor.pos, protected.pos) <= 2, "Escort target out of range")
    else:
        require(target is None, "Target only valid for escort")
    current = [tag for tag in actor.tags if tag.startswith(PREFIX)]
    require(len(current) <= 1, "Conflicting formation tags")
    actor.tags = [tag for tag in actor.tags if not tag.startswith(PREFIX)]
    if mode != "none":
        actor.tags.append(PREFIX + mode + (":" + target if mode == "escort" else ""))
    actor.acted = True
    actor.cast = None
    battle.emit("formation", unit=actor.id, mode=mode,
                **({"target": target} if target is not None else {}))


def phalanx_hold_covers(battle, watcher, cell):
    """Shared preview/execution geometry for a prepared spear corridor."""
    return (phalanx(battle, watcher)
            and distance(watcher.pos, cell) <= min(
                battle.engagement_range(watcher), battle._basic(watcher).range)
            and battle.line_of_sight(
                watcher.pos, cell, level=battle.unit_levels.get(watcher.id, 0)))


def phalanx_hold_enters(battle, watcher, previous, cell):
    return (not phalanx_hold_covers(battle, watcher, previous)
            and phalanx_hold_covers(battle, watcher, cell))


def validate_phalanx_hold(battle, unit, target):
    require(target is None, "Phalanx hold does not target an ally")
    require(phalanx(battle, unit),
            "Phalanx hold needs adjacent spears already in formation")


def formation_control_map(battle, team):
    """Pure overlay of ready/prepared formation corridors for Studio and Player.

    A marked pair projects a threat only through the existing spear attack
    geometry; nearby tiles may be seen but not entered through blocked walls.
    """
    require(team in {"player", "enemy"}, "Unknown team")
    result = []
    for unit in sorted(battle.units, key=lambda u: u.id):
        if not unit.alive or unit.team != team or not phalanx(battle, unit):
            continue
        cells = [list(cell) for cell in battle.board.cells()
                 if cell != unit.pos and phalanx_hold_covers(battle, unit, cell)]
        prep = battle.prepared_reactions.get(unit.id, {})
        result.append({"unit": unit.id,
                       "level": battle.unit_levels.get(unit.id, 0),
                       "cells": cells,
                       "armed": prep.get("mode") == "phalanx_hold"
                       and prep.get("charges", 0) > 0
                       and battle._can_react(unit)})
    return result


def install_formations(rules):
    """Return a new RuleSet; no modification of the default global rules."""
    from .rules.registry import CommandRule, FormulaRule, PreparationRule

    base_mitigate = rules.formulas.get("mitigation").calculate
    base_hit = rules.formulas.get("hit_chance").calculate

    def mitigate(battle, caster, target, skill, effect, raw):
        damage = base_mitigate(battle, caster, target, skill, effect, raw)
        if skill.magical:
            return damage
        if phalanx(battle, caster) and skill.id == "attack":
            damage = damage * 5 // 4
            if (battle.unit_levels.get(caster.id, 0) == 0
                    and battle.unit_levels.get(target.id, 0) == 0
                    and battle.board.tile(caster.pos).height >
                    battle.board.tile(target.pos).height):
                damage = damage * 11 // 10
        if shield_wall(battle, target):
            damage = damage * 4 // 5
            if (battle.unit_levels.get(target.id, 0) == 0
                    and battle.board.tile(target.pos).cover >= 20):
                damage = damage * 9 // 10
        if escorted(battle, target):
            damage = damage * 17 // 20
        return damage

    def hit_chance(battle, caster, target, skill):
        chance = base_hit(battle, caster, target, skill)
        if not skill.magical and escorted(battle, target):
            return chance * 0.9
        return chance

    rules = rules.with_family("preparations", rules.preparations.with_rule(
        "phalanx_hold", PreparationRule(validate_phalanx_hold,
            covers=phalanx_hold_covers, enters=phalanx_hold_enters,
            version="2.7.2")))
    rules = rules.with_family("commands", rules.commands.with_rule(
        "formation", CommandRule(set_formation, version="2.7.2")))
    rules = rules.with_family("formulas", rules.formulas.with_rule(
        "mitigation", FormulaRule(mitigate, version="2.7.2.1"), replace_existing=True))
    return rules.with_family("formulas", rules.formulas.with_rule(
        "hit_chance", FormulaRule(hit_chance, version="2.7.2"), replace_existing=True))

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


def _allied(battle, actor, *, mode):
    return [u for u in battle.units if u.alive and u.id != actor.id
            and u.team == actor.team and distance(u.pos, actor.pos) == 1
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
               and distance(u.pos, target.pos) == 1 for u in battle.units)


def formation_preview(battle, unit_id):
    """Pure UI/AI forecast, with no hidden formation activation."""
    unit = next((u for u in battle.units if u.id == unit_id), None)
    require(unit is not None, "Unknown formation unit")
    return {"unit": unit.id, "mode": _formation_tag(unit)[len(PREFIX):] or "none",
            "shield_wall": bool(shield_wall(battle, unit)),
            "phalanx": bool(phalanx(battle, unit)),
            "escort": bool(escorted(battle, unit))}


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


def install_formations(rules):
    """Return a new RuleSet; no modification of the default global rules."""
    from .rules.registry import CommandRule, FormulaRule

    base_mitigate = rules.formulas.get("mitigation").calculate
    base_hit = rules.formulas.get("hit_chance").calculate

    def mitigate(battle, caster, target, skill, effect, raw):
        damage = base_mitigate(battle, caster, target, skill, effect, raw)
        if skill.magical:
            return damage
        if phalanx(battle, caster) and skill.id == "attack":
            damage = damage * 5 // 4
        if shield_wall(battle, target):
            damage = damage * 4 // 5
        if escorted(battle, target):
            damage = damage * 17 // 20
        return damage

    def hit_chance(battle, caster, target, skill):
        chance = base_hit(battle, caster, target, skill)
        if not skill.magical and escorted(battle, target):
            return chance * 0.9
        return chance

    rules = rules.with_family("commands", rules.commands.with_rule(
        "formation", CommandRule(set_formation, version="2.7.2")))
    rules = rules.with_family("formulas", rules.formulas.with_rule(
        "mitigation", FormulaRule(mitigate, version="2.7.2"), replace_existing=True))
    return rules.with_family("formulas", rules.formulas.with_rule(
        "hit_chance", FormulaRule(hit_chance, version="2.7.2"), replace_existing=True))

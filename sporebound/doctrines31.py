"""Opt-in, deterministic medieval encounter doctrines (3.1.2).

Doctrines select existing legal commands; new reload and surrender commands run
inside Battle.execute's rollback, event log and replay contract. No global state.
"""
from __future__ import annotations

from .model import distance, require, RuleError


DOCTRINES = {
    "wolf": "pack_hunt",
    "alpha_wolf": "pack_hunt",
    "bandit": "bandit_ambush",
    "bandit_archer": "bandit_ambush",
    "raider": "bandit_ambush",
    "bandit_captain": "bandit_ambush",
    "spearman": "spear_hold",
    "crossbowman": "crossbow_reload",
}


def doctrine(unit):
    return next((tag.split(":", 1)[1] for tag in unit.tags
                 if tag.startswith("doctrine:")), "")


def _foes(battle, actor):
    return sorted((u for u in battle.units if u.alive and u.team != actor.team),
                  key=lambda u: u.id)


def _strike(battle, actor, foe):
    if actor.acted or battle.status_blocks(actor, "act"):
        return None
    for sid in [*actor.skills, "attack"]:
        skill = battle._skill(actor, sid)
        if skill.cost > actor.mp:
            continue
        try:
            rows = battle.forecast(sid, foe.pos, actor)
        except RuleError:
            continue
        if any(row.get("unit") == foe.id and row.get("kind") in {"damage", "tactic"}
               and row.get("amount", 0) > 0 for row in rows):
            return {"kind": "act", "skill": sid, "cell": list(foe.pos)}
    return None


def _move(battle, actor, rank):
    """Rank reachable cells without mutating the actor or exposing illegal moves."""
    if actor.moved or battle.status_blocks(actor, "move") or "move" not in battle.rules.commands:
        return None
    options = []
    for cell, (cost, path) in battle.reachable(actor).items():
        if cell == actor.pos:
            continue
        risk = sum(r["amount"] * r["chance"] for r in battle.movement_threats(actor, path))
        risk += sum(battle.board.tile(p).hazard for p in path[1:])
        score = rank(cell) - risk - cost * .05
        options.append((-score, cost, cell))
    if not options:
        return None
    score, _cost, cell = min(options)
    if -score <= rank(actor.pos):
        return None
    return {"kind": "move", "cell": list(cell)}


def _pack(battle, actor):
    enemies = _foes(battle, actor)
    if not enemies:
        return None
    # A lone hero is the pack's objective; stable tie-break by actor id.
    def isolation(target):
        allies = [u for u in battle.units if u.alive and u.team == target.team
                  and u.id != target.id]
        return min((distance(target.pos, u.pos) for u in allies), default=9)
    target = min(enemies, key=lambda u: (-isolation(u), u.hp, u.id))
    strike = _strike(battle, actor, target)
    if strike:
        return strike

    def rank(cell):
        d = distance(cell, target.pos)
        # Prefer a rear / flank entry, and support from other nearby wolves.
        dx, dy = cell[0] - target.pos[0], cell[1] - target.pos[1]
        facing = target.facing
        rear = dx * facing[0] + dy * facing[1] < 0
        pack = sum(1 for u in battle.units if u.alive and u.team == actor.team
                   and u.id != actor.id and "wolf" in u.tags
                   and distance(u.pos, target.pos) <= 2)
        return -d * 3 + (5 if d == 1 and rear else 0) + (pack * 2 if d == 1 else 0)

    return _move(battle, actor, rank)


def _bandit(battle, actor):
    enemies = _foes(battle, actor)
    if not enemies:
        return None
    leaders = [u for u in battle.units if u.team == actor.team
               and "bandit" in u.tags and "leader" in u.tags]
    from .morale31 import morale_snapshot
    # Officers prefer an explicit support action when morale is failing.
    if "leader" in actor.tags and not actor.acted and not battle.status_blocks(actor, "act"):
        if "rally" in battle.rules.commands:
            allies = sorted((u for u in battle.units
                             if u.alive and u.team == actor.team and u.id != actor.id
                             and distance(actor.pos, u.pos) <= 2
                             and morale_snapshot(battle, u)["can_be_rallied"]),
                            key=lambda u: (-morale_snapshot(battle, u)["pressure"], u.id))
            if allies:
                return {"kind": "rally", "target": allies[0].id}

    state = morale_snapshot(battle, actor)["state"]
    broken = (any(not u.alive for u in leaders)
              or actor.hp * 3 <= actor.max_hp
              or state in {"wavering", "routing"})
    if broken and "leader" not in actor.tags:
        # A cornered routing bandit capitulates; wounded brigands preserve
        # their existing low-HP surrender behaviour.
        surrounded = min(distance(actor.pos, e.pos) for e in enemies) <= 2
        if ("surrender" in battle.rules.commands and not actor.acted
                and (actor.hp * 2 <= actor.max_hp
                     or state == "routing" and surrounded)):
            return {"kind": "surrender"}
        fleeing = _move(battle, actor, lambda cell: (
            min(distance(cell, t.pos) for t in enemies) * 4
            + battle.board.tile(cell).cover * .05))
        if fleeing:
            return fleeing
        if state == "routing" and "surrender" in battle.rules.commands and not actor.acted:
            return {"kind": "surrender"}
        return {"kind": "end"}
    # An ambusher prefers cover and waits for an exposed target rather than
    # abandoning it to chase across the open.
    targets = sorted(enemies, key=lambda t: (t.hp, t.id))
    for target in targets:
        strike = _strike(battle, actor, target)
        if strike:
            return strike
    target = targets[0]
    return _move(battle, actor, lambda cell: (
        -distance(cell, target.pos) * 2 + battle.board.tile(cell).cover * .1))


def _spear(battle, actor):
    enemies = _foes(battle, actor)
    if not enemies:
        return None
    for target in sorted(enemies, key=lambda u: (distance(actor.pos, u.pos), u.id)):
        strike = _strike(battle, actor, target)
        if strike:
            return strike
    closest = min(distance(actor.pos, foe.pos) for foe in enemies)
    if (not actor.acted and closest <= 4 and
            not battle.status_blocks(actor, "act") and
            "prepare" in battle.rules.commands):
        from .formations3 import phalanx
        if ("phalanx_hold" in battle.rules.preparations
                and phalanx(battle, actor)):
            return {"kind": "prepare", "mode": "phalanx_hold"}
        if "guard" in battle.rules.preparations:
            return {"kind": "prepare", "mode": "guard"}
    # Do not pursue beyond the defended choke point. A pair can spend
    # real actions establishing its phalanx before arming a hold reaction.
    if (not actor.acted and "formation" in battle.rules.commands
            and not any(tag.startswith("formation:") for tag in actor.tags)
            and any(u.alive and u.team == actor.team and u.id != actor.id
                    and u.weapon == "spear" and distance(actor.pos, u.pos) == 1
                    for u in battle.units)):
        return {"kind": "formation", "mode": "phalanx"}
    return {"kind": "end"}


def _crossbow(battle, actor):
    if "reload:empty" in actor.tags:
        enemies = _foes(battle, actor)
        if enemies:
            near = min(distance(actor.pos, enemy.pos) for enemy in enemies)
            if near <= 2:
                retreat = _move(battle, actor, lambda c: (
                    min(distance(c, enemy.pos) for enemy in enemies) * 5
                    + battle.board.tile(c).cover * .05))
                if retreat:
                    return retreat
        if not actor.acted:
            return {"kind": "reload"}
        return {"kind": "end"}
    enemies = _foes(battle, actor)
    for target in sorted(enemies, key=lambda u: (u.hp, u.id)):
        strike = _strike(battle, actor, target)
        if strike:
            return strike
    return None


def doctrine_command(battle):
    from .ai import _choose_tactical_command
    actor = battle.active
    if actor is None or actor.cast:
        return _choose_tactical_command(battle)
    policy = {"pack_hunt": _pack, "bandit_ambush": _bandit,
              "spear_hold": _spear, "crossbow_reload": _crossbow}.get(doctrine(actor))
    command = policy(battle, actor) if policy else None
    return command or _choose_tactical_command(battle)


def crossbow_act(battle, actor, command):
    """Every shot creates an empty weapon; the next shot requires reload."""
    skill = command["skill"]
    is_crossbow = doctrine(actor) == "crossbow_reload"
    is_shot = skill in {"attack", "med_aim"}
    require(not (is_crossbow and is_shot and "reload:empty" in actor.tags),
            "Arbalète vide : rechargez avant de tirer")
    from .rules.commands import cell
    battle._act(actor, skill, cell(command))
    if is_crossbow and is_shot:
        actor.tags.append("reload:empty")
        battle.emit("crossbow_empty", unit=actor.id)


def reload_crossbow(battle, actor, command):
    require(doctrine(actor) == "crossbow_reload" and "reload:empty" in actor.tags,
            "Aucune arbalète vide")
    require(not actor.acted and not battle.status_blocks(actor, "act"),
            "Rechargement indisponible")
    actor.tags.remove("reload:empty")
    actor.acted = True
    battle.emit("crossbow_reloaded", unit=actor.id)


def surrender(battle, actor, command):
    require("bandit" in actor.tags and "leader" not in actor.tags
            and actor.alive and not actor.acted, "Reddition indisponible")
    leaders = [u for u in battle.units if u.team == actor.team
               and "bandit" in u.tags and "leader" in u.tags]
    from .morale31 import morale_snapshot
    require(actor.hp * 3 <= actor.max_hp or any(not u.alive for u in leaders)
            or morale_snapshot(battle, actor)["state"] == "routing",
            "Le combattant n'est pas démoralisé")
    actor.hp = 0
    actor.acted = True
    battle.emit("surrender", unit=actor.id, captor="player" if actor.team == "enemy" else "enemy")
    battle._outcome()
    if not battle.result:
        battle._end(actor, actor.facing)


def install_doctrines(rules):
    from .rules.registry import CommandRule
    commands = rules.commands.with_rule("act", CommandRule(crossbow_act, version="3.1.2"),
                                         replace_existing=True)
    commands = commands.with_rule("reload", CommandRule(reload_crossbow, version="3.1.2"))
    commands = commands.with_rule("surrender", CommandRule(surrender, version="3.1.2"))
    return rules.with_family("commands", commands)

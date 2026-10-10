"""Opt-in coordinated AI for compact encounters (2.7.1).

This behavior only *chooses* an existing command. All validation, RNG, tactical
effects and atomic rollback remain owned by Battle.execute.
"""
from __future__ import annotations

from .model import distance


def _is_healer(unit):
    return "healer" in unit.tags or "medic" in unit.tags


def _protective_move(battle, actor):
    """Place a protector between the closest enemy and an exposed medic."""
    if actor.moved or battle.status_blocks(actor, "move") or "move" not in battle.rules.commands:
        return None
    medics = sorted((u for u in battle.units if u.alive and u.team == actor.team
                     and u.id != actor.id and _is_healer(u)), key=lambda u: u.id)
    foes = [u for u in battle.units if u.alive and u.team != actor.team]
    if not medics or not foes:
        return None
    targets = []
    for medic in medics:
        threat = min(foes, key=lambda u: (distance(u.pos, medic.pos), u.id))
        if distance(threat.pos, medic.pos) > 4:
            continue
        # Evaluate reachable candidates without mutating actor or combat state.
        for cell, (cost, path) in battle.reachable(actor).items():
            if cell == actor.pos or distance(cell, medic.pos) != 1:
                continue
            before = distance(actor.pos, medic.pos)
            enemy_distance = distance(cell, threat.pos)
            if enemy_distance >= distance(medic.pos, threat.pos):
                continue
            risk = sum(row["amount"] * row["chance"]
                       for row in battle.movement_threats(actor, path))
            hazard = sum(battle.board.tile(pos).hazard for pos in path[1:])
            value = (before - 1) * 2 - cost * 0.1 - risk - hazard
            targets.append((-value, cost, cell, medic.id))
    if not targets:
        return None
    best = min(targets)
    if best[0] > 0:
        return None
    return {"kind": "move", "cell": list(best[2])}


def _healing_command(battle, actor):
    """Use legal restorative forecasts; no direct writes or hidden shortcuts."""
    if actor.acted or battle.status_blocks(actor, "act") or "act" not in battle.rules.commands:
        return None
    allies = sorted((u for u in battle.units if u.alive and u.team == actor.team
                     and u.hp < u.max_hp), key=lambda u: (u.hp / u.max_hp, u.id))
    for target in allies:
        for skill_id in sorted(actor.skills):
            skill = battle._skill(actor, skill_id)
            if skill.cost > actor.mp or skill.target not in {"ally", "self", "unit"}:
                continue
            if skill.magical and battle.status_blocks(actor, "magic"):
                continue
            try:
                rows = battle.forecast(skill_id, target.pos, actor)
            except ValueError:
                continue
            if any(row.get("kind") == "heal" and row.get("unit") == target.id
                   and row.get("amount", 0) > 0 for row in rows):
                return {"kind": "act", "skill": skill_id, "cell": list(target.pos)}
    return None


def coordinated_command(battle):
    """Medic recovery > protector positioning > standard objective-aware AI.

    The fallback is the existing deterministic tactical policy, preserving
    siege equipment, deployment, reactions and objective handling.
    """
    from .ai import _choose_tactical_command
    actor = battle.active
    if actor is None or actor.cast:
        return _choose_tactical_command(battle)
    if _is_healer(actor):
        healing = _healing_command(battle, actor)
        if healing is not None:
            return healing
    if "protector" in actor.tags:
        move = _protective_move(battle, actor)
        if move is not None:
            return move
    return _choose_tactical_command(battle)

"""Opt-in coordinated AI for compact encounters (2.7.1).

This behavior only *chooses* an existing command. All validation, RNG, tactical
effects and atomic rollback remain owned by Battle.execute.
"""
from __future__ import annotations

from .model import RuleError, distance, require


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



def squad_focus_preview(battle, actor_id=None):
    """Pure sorted targets for a squad-focused normal attack.

    The estimate comes from Battle.forecast (including real synergy effects),
    not a parallel damage formula. A supporter must currently be able to reach
    the target with a basic attack and retain their Act. Squads without an
    immediate supporting attack fall back to the ordinary objective-aware AI.
    """
    actor = (battle.unit(actor_id) if actor_id is not None else battle.active)
    require(actor is not None, "No actor for squad preview")
    if actor.acted or battle.status_blocks(actor, "act"):
        return []
    rows = []
    for foe in sorted((u for u in battle.units
                       if u.alive and u.team != actor.team), key=lambda u: u.id):
        try:
            forecast = battle.forecast("attack", foe.pos, actor)
        except RuleError:
            continue
        damage = sum(row["amount"] * row["chance"] for row in forecast
                     if row["unit"] == foe.id
                     and row["kind"] in {"damage", "tactic"})
        if damage <= 0:
            continue
        supporters = []
        for ally in sorted(battle.units, key=lambda u: u.id):
            if (not ally.alive or ally.team != actor.team or ally.id == actor.id
                    or ally.acted or battle.status_blocks(ally, "act")):
                continue
            basic = battle._basic(ally)
            separation = min(distance(cell, foe.pos)
                             for cell in ally.occupied_cells())
            if (basic.min_range <= separation <= basic.range
                    and (not basic.los or battle.line_of_sight(ally.pos, foe.pos))):
                supporters.append(ally.id)
        lethal = damage >= foe.hp
        score = (damage + len(supporters) * 8
                 + (25 if lethal else 0)
                 + (6 if _is_healer(foe) else 0))
        rows.append({"target": foe.id, "cell": list(foe.pos),
                     "expected_damage": round(damage, 3),
                     "supporters": supporters, "lethal": lethal,
                     "score": round(score, 3)})
    return sorted(rows, key=lambda r: (-r["score"], r["target"]))


def _focus_command(battle, actor):
    for row in squad_focus_preview(battle, actor.id):
        if row["supporters"]:
            return {"kind": "act", "skill": "attack", "cell": row["cell"]}
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
    baseline = _choose_tactical_command(battle)
    # Do not override siege interactions, healing, special spells, or
    # pathfinding: squad focus only resolves a choice of normal basic attack.
    if baseline["kind"] == "act" and baseline.get("skill") == "attack":
        return _focus_command(battle, actor) or baseline
    return baseline

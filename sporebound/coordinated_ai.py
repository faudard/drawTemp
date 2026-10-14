"""Opt-in coordinated AI for compact encounters (2.7.1).

This behavior only *chooses* an existing command. All validation, RNG, tactical
effects and atomic rollback remain owned by Battle.execute.
"""
from __future__ import annotations

from .model import RuleError, distance, require


def _is_healer(unit):
    return "healer" in unit.tags or "medic" in unit.tags or "squad:medic" in unit.tags


def _same_floor(battle, left, right):
    """Squad actions share a deck; cross-floor shots use explicit level_attack."""
    return battle.unit_levels.get(left.id, 0) == battle.unit_levels.get(right.id, 0)


def _protective_move(battle, actor):
    """Place a frontline actor between an enemy and an exposed support unit."""
    if actor.moved or battle.status_blocks(actor, "move") or "move" not in battle.rules.commands:
        return None
    medics = sorted((u for u in battle.units if u.alive and u.team == actor.team
                     and u.id != actor.id and _same_floor(battle, actor, u) and
                     (_is_healer(u) or
                      (squad_role(actor) in {"vanguard", "pikeman"}
                       and squad_role(u) == "archer"))), key=lambda u: u.id)
    foes = [u for u in battle.units if u.alive and u.team != actor.team
            and _same_floor(battle, actor, u)]
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
                     and u.hp < u.max_hp and _same_floor(battle, actor, u)),
                    key=lambda u: (u.hp / u.max_hp, u.id))
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
                       if u.alive and u.team != actor.team
                       and _same_floor(battle, actor, u)), key=lambda u: u.id):
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
                    or ally.acted or battle.status_blocks(ally, "act")
                    or not _same_floor(battle, actor, ally)):
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


def squad_role(actor):
    """Data-driven role. Legacy tags retain their existing behavior."""
    for tag in actor.tags:
        if tag in {"squad:pikeman", "squad:vanguard", "squad:archer",
                   "squad:medic", "squad:officer"}:
            return tag.split(":", 1)[1]
    return ""


def squad_posture_command(battle, actor):
    """Spend a real action to assemble a legal defensive formation.

    Formation partners must be present; no synthetic squad bonuses or hidden
    movement are granted by the AI. Other actions keep their normal priority.
    """
    if (actor.acted or battle.status_blocks(actor, "act")
            or "formation" not in battle.rules.commands):
        return None
    role = squad_role(actor)
    has_formation = any(tag.startswith("formation:") for tag in actor.tags)
    neighbors = [u for u in battle.units if u.alive and u.team == actor.team
                 and u.id != actor.id and distance(u.pos, actor.pos) == 1]
    if role == "pikeman" and actor.weapon == "spear":
        from .formations3 import phalanx
        if phalanx(battle, actor) and "phalanx_hold" in battle.rules.preparations:
            # Prepare the real spear reaction only if an enemy can approach.
            foes = [u for u in battle.units if u.alive and u.team != actor.team]
            if foes and min(distance(actor.pos, foe.pos) for foe in foes) <= 4:
                return {"kind": "prepare", "mode": "phalanx_hold"}
        if (not has_formation and any(u.weapon == "spear" for u in neighbors)):
            return {"kind": "formation", "mode": "phalanx"}
    if role == "vanguard" and not has_formation:
        if any(squad_role(u) == "vanguard" or
               "formation:shield_wall" in u.tags for u in neighbors):
            return {"kind": "formation", "mode": "shield_wall"}
    if role == "officer" and not has_formation:
        medics = sorted((u for u in battle.units if u.alive and u.team == actor.team
                         and u.id != actor.id and
                         (squad_role(u) == "medic" or _is_healer(u))
                         and distance(actor.pos, u.pos) <= 2),
                        key=lambda u: (u.hp / max(1, u.max_hp), u.id))
        if medics:
            return {"kind": "formation", "mode": "escort", "target": medics[0].id}
    return None


def squad_medic_retreat(battle, actor):
    """Keep a threatened medic behind defenders without teleporting or cheating."""
    if (actor.moved or battle.status_blocks(actor, "move")
            or squad_role(actor) != "medic"):
        return None
    foes = [u for u in battle.units if u.alive and u.team != actor.team]
    if not foes:
        return None
    current = min(distance(actor.pos, foe.pos) for foe in foes)
    if current > 2:
        return None
    guards = [u for u in battle.units if u.alive and u.team == actor.team
              and u.id != actor.id and (squad_role(u) in {"vanguard", "pikeman"}
                                         or "protector" in u.tags)]
    options = []
    for cell, (cost, path) in battle.reachable(actor).items():
        separation = min(distance(cell, foe.pos) for foe in foes)
        if cell == actor.pos or separation <= current:
            continue
        cover = battle.board.tile(cell).cover
        guard_distance = min((distance(cell, u.pos) for u in guards), default=4)
        risk = sum(row["amount"] * row["chance"]
                   for row in battle.movement_threats(actor, path))
        hazard = sum(battle.board.tile(pos).hazard for pos in path[1:])
        score = separation * 10 + cover * .05 - guard_distance - risk - hazard - cost * .05
        options.append((-score, cost, cell))
    if not options:
        return None
    return {"kind": "move", "cell": list(min(options)[2])}


def squad_archer_cover_move(battle, actor):
    """Approach a shot from behind a melee screen, not through the frontline."""
    if (squad_role(actor) != "archer" or actor.weapon != "ranged"
            or actor.moved or battle.status_blocks(actor, "move")
            or battle.engaged_by(actor)):
        return None
    foes = [u for u in battle.units if u.alive and u.team != actor.team]
    guards = [u for u in battle.units if u.alive and u.team == actor.team
              and u.id != actor.id
              and squad_role(u) in {"pikeman", "vanguard"}]
    if not foes or not guards:
        return None
    basic = battle._basic(actor)
    if any(basic.min_range <= distance(actor.pos, foe.pos) <= basic.range
           and battle.line_of_sight(actor.pos, foe.pos) for foe in foes):
        return None
    options = []
    for cell, (cost, path) in battle.reachable(actor).items():
        if cell == actor.pos:
            continue
        if min(distance(cell, guard.pos) for guard in guards) > 2:
            continue
        reachable_foes = [foe for foe in foes
                          if basic.min_range <= distance(cell, foe.pos) <= basic.range
                          and battle.line_of_sight(cell, foe.pos)
                          and any(distance(cell, foe.pos) >=
                                  distance(guard.pos, foe.pos) for guard in guards)]
        if not reachable_foes:
            continue
        risk = sum(row["amount"] * row["chance"]
                   for row in battle.movement_threats(actor, path))
        risk += sum(battle.board.tile(pos).hazard for pos in path[1:])
        if risk:
            continue
        cover = battle.board.tile(cell).cover
        options.append((-cover, cost, cell))
    if not options:
        return None
    return {"kind": "move", "cell": list(min(options)[2])}


def squad_objective_guard_move(battle, actor):
    """Contest authored goal tiles rather than chasing kills on objective maps.

    Only opt-in enemy squads use this policy. It chooses a normal, reachable
    Move with no implicit teleport, damage, CT or state mutation. An available
    shot takes priority, and units already screening the goal hold their tile.
    """
    if (actor.team != "enemy" or actor.moved
            or battle.status_blocks(actor, "move")
            or "move" not in battle.rules.commands
            or battle.mission.objective not in {"extract", "hold", "crown",
                                               "capture", "escort", "retreat"}
            or not battle.mission.goal):
        return None
    goals = tuple(sorted(battle.mission.goal))
    current = min(distance(actor.pos, cell) for cell in goals)
    if current <= 1:
        return None
    if not actor.acted and not battle.status_blocks(actor, "act"):
        attack = battle._basic(actor)
        if any(opponent.alive and opponent.team != actor.team
               and attack.min_range <= distance(actor.pos, opponent.pos) <= attack.range
               and (not attack.los or battle.line_of_sight(actor.pos, opponent.pos))
               for opponent in battle.units):
            return None
    options = []
    for cell, (cost, path) in battle.reachable(actor).items():
        goal_distance = min(distance(cell, goal) for goal in goals)
        if cell == actor.pos or goal_distance >= current:
            continue
        risk = sum(row["amount"] * row["chance"]
                   for row in battle.movement_threats(actor, path))
        risk += sum(battle.board.tile(pos).hazard for pos in path[1:])
        if risk > actor.hp / 2:
            continue
        options.append((goal_distance, risk, cost, cell))
    if not options:
        return None
    return {"kind": "move", "cell": list(min(options)[3])}


def squad_terrain_vantage_move(battle, actor):
    """Acquire a legal ranged firing tile with demonstrable terrain advantage.

    Only moves when no current basic shot exists. Compare reachable tiles by
    real terrain, LOS, movement threats and hazard exposure; this planner
    cannot perform attacks, teleport, or reason across different floors.
    """
    if (squad_role(actor) != "archer" or actor.weapon != "ranged"
            or actor.moved or battle.status_blocks(actor, "move")
            or "move" not in battle.rules.commands
            or battle.unit_levels.get(actor.id, 0) != 0
            or battle.engaged_by(actor)):
        return None
    opponents = [u for u in battle.units if u.alive and u.team != actor.team
                 and battle.unit_levels.get(u.id, 0) == 0]
    if not opponents:
        return None
    basic = battle._basic(actor)

    def shot_from(cell):
        return any(basic.min_range <= distance(cell, enemy.pos) <= basic.range
                   and (not basic.los or battle.line_of_sight(cell, enemy.pos))
                   for enemy in opponents)

    if shot_from(actor.pos):
        return None
    current = battle.board.tile(actor.pos)
    options = []
    for cell, (cost, path) in battle.reachable(actor).items():
        if cell == actor.pos or not shot_from(cell):
            continue
        tile = battle.board.tile(cell)
        height_gain = tile.height - current.height
        cover_gain = tile.cover - current.cover
        if height_gain <= 0 and cover_gain < 20:
            continue
        risk = sum(row["amount"] * row["chance"]
                   for row in battle.movement_threats(actor, path))
        hazards = sum(battle.board.tile(position).hazard for position in path[1:])
        if risk + hazards >= max(1, actor.hp / 4):
            continue
        # Gain must be worth the path; ties are stable across runs/platforms.
        score = height_gain * 8 + cover_gain * .12 - cost * .15 - risk - hazards
        if score > 0:
            options.append((-score, cost, cell))
    if not options:
        return None
    return {"kind": "move", "cell": list(min(options)[2])}


def squad_plan_preview(battle, actor_id):
    """Read-only companion/role diagnostics for UI and tests."""
    actor = battle.unit(actor_id)
    comrades = sorted((u for u in battle.units if u.alive and u.team == actor.team
                        and u.id != actor.id), key=lambda u: u.id)
    return {"unit": actor.id, "role": squad_role(actor),
            "frontline": [u.id for u in comrades
                          if squad_role(u) in {"vanguard", "pikeman"}],
            "support": [u.id for u in comrades
                        if _is_healer(u) or squad_role(u) == "medic"],
            "officers": [u.id for u in comrades if squad_role(u) == "officer"]}


def coordinated_command(battle):
    """Medic recovery > protector positioning > standard objective-aware AI.

    The fallback is the existing deterministic tactical policy, preserving
    siege equipment, deployment, reactions and objective handling.
    """
    from .ai import _choose_tactical_command
    actor = battle.active
    if actor is None or actor.cast:
        return _choose_tactical_command(battle)
    # The existing layered planner owns stairs and upper-floor actions.
    # Ground-only formation, escort and healing policies cannot issue
    # ordinary Move/Act commands on an authored upper deck.
    if battle.mission.level_links and battle.unit_levels.get(actor.id, 0) != 0:
        return _choose_tactical_command(battle)
    if _is_healer(actor):
        healing = _healing_command(battle, actor)
        if healing is not None:
            return healing
    if squad_role(actor) or "protector" in actor.tags:
        objective_move = squad_objective_guard_move(battle, actor)
        if objective_move is not None:
            return objective_move
    if "protector" in actor.tags or squad_role(actor) in {"vanguard", "pikeman"}:
        move = _protective_move(battle, actor)
        if move is not None:
            return move
    if squad_role(actor) == "medic":
        retreat = squad_medic_retreat(battle, actor)
        if retreat is not None:
            return retreat
    if squad_role(actor) == "archer":
        approach = squad_archer_cover_move(battle, actor)
        if approach is not None:
            return approach
        vantage = squad_terrain_vantage_move(battle, actor)
        if vantage is not None:
            return vantage
    posture = squad_posture_command(battle, actor)
    if posture is not None:
        return posture
    baseline = _choose_tactical_command(battle)
    # Do not override siege interactions, healing, special spells, or
    # pathfinding: squad focus only resolves a choice of normal basic attack.
    if baseline["kind"] == "act" and baseline.get("skill") == "attack":
        return _focus_command(battle, actor) or baseline
    return baseline

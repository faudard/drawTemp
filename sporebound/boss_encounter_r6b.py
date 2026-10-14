"""R6.6B encounter intelligence, using the canonical combat runtime only.

All functions are pure queries of the current Battle. Casts are real authored
Skill.cast_ticks actions resolved by Battle._advance, and arriving allies come
from the normal actor_spawned journal. No extra delayed-command queue.
"""
from __future__ import annotations

from .model import RuleError, distance


def arrived_reinforcements(battle, boss):
    """Already spawned teammates, never queued or hypothetical wave actors."""
    ids = {event["unit"] for event in battle.events
           if event["kind"] == "actor_spawned"}
    return sorted(
        (unit for unit in battle.units
         if unit.id in ids and unit.alive and unit.team == boss.team
         and unit.id != boss.id
         and battle.unit_levels.get(unit.id, 0) ==
             battle.unit_levels.get(boss.id, 0)),
        key=lambda unit: unit.id)


def reinforcement_pressure(battle, boss, destination, target, allies=None):
    """Observed supporting firing positions for a particular reachable anchor.

    Only real, arrived teammates count; being alive/nearby doesn't promise
    that the AI will take a future action.
    """
    allies = arrived_reinforcements(battle, boss) if allies is None else allies
    if not allies:
        return 0
    footprint = boss.occupied_cells(destination)
    if min(distance(c, p) for c in footprint
           for p in target.occupied_cells()) > 3:
        return 0
    count = 0
    for ally in allies:
        if (ally.acted or battle.status_blocks(ally, "act")
                or not ally.alive or ally.team != boss.team):
            continue
        weapon = battle._basic(ally)
        gap = min(distance(a, t) for a in ally.occupied_cells()
                  for t in target.occupied_cells())
        if (weapon.min_range <= gap <= weapon.range
                and (not weapon.los or
                     battle.line_of_sight(ally.pos, target.pos))):
            count += 1
    return min(2, count)


def telegraphed_cast_command(battle, boss):
    """One actual multi-tick area skill; no speculative CT or new damage model.

    A candidate must have authored cast_ticks and a non-zero AoE radius.
    The engine's forecast scores direct enemy/friendly collateral. The hero
    can move away during the real cast, especially when lock='cell'.
    """
    if (boss.cast or boss.acted or battle.status_blocks(boss, "act")
            or "act" not in battle.rules.commands):
        return None
    if battle.unit_levels.get(boss.id, 0) != 0:
        return None
    opponents = sorted(
        (other for other in battle.units if other.alive
         and other.team != boss.team
         and battle.unit_levels.get(other.id, 0) == 0),
        key=lambda unit: unit.id)
    candidates = []
    for sid in sorted(boss.skills):
        skill = battle._skill(boss, sid)
        if (skill.cast_ticks < 2 or skill.radius < 1
                or skill.cost > boss.mp
                or skill.target not in {"ground", "enemy"}
                or (skill.magical and battle.status_blocks(boss, "magic"))):
            continue
        for target in opponents:
            if not battle.board.contains(target.pos):
                continue
            try:
                rows = battle.forecast(sid, target.pos, boss)
            except RuleError:
                continue
            value = 0.0
            touched = set()
            for row in rows:
                if row["kind"] not in {"damage", "tactic"}:
                    continue
                victim = battle.unit(row["unit"])
                expected = min(victim.hp, row["amount"]) * row["chance"]
                value += expected if victim.team != boss.team else -2.0 * expected
                if victim.team != boss.team and expected > 0:
                    touched.add(victim.id)
            # Penalize long windups and MP; prefer affecting two enemies.
            value = value / (1 + skill.cast_ticks / 20) + max(0, len(touched)-1)*4
            value -= skill.cost * .2
            if value > 0:
                candidates.append((-value, sid, list(target.pos)))
    if not candidates:
        return None
    _, sid, cell = min(candidates)
    return {"kind": "act", "skill": sid, "cell": cell}

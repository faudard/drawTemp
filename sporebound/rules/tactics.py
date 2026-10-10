"""Tactics policies; Battle owns state and transactions."""
from __future__ import annotations

from copy import deepcopy
from itertools import combinations
from .registry import Registry, TacticRule
from ..model import Cell, Unit, distance, require

def relay_options(battle, unit: Unit | None = None) -> list[dict]:
    """Pure pair-tactic query: spend Act + partner CT for a bounded legal reposition."""
    u = unit or battle.active
    if (u is None or not u.alive or u.acted or battle.status_blocks(u, "act")
            or "relay" not in u.tactics):
        return []
    result = []
    for partner in battle.units:
        if (partner.id == u.id or not partner.alive or partner.team != u.team
                or "relay" not in partner.tactics or not battle._can_react(partner)
                or partner.ct < 20 or battle.status_blocks(partner, "move")
                or battle.carrier == partner.id
                or distance(u.pos, partner.pos) != 1
                or not battle.line_of_sight(u.pos, partner.pos)):
            continue
        ghost = deepcopy(partner)
        ghost.moved = False
        ghost.disengaging = False
        for cell, (cost, path) in battle.reachable(ghost).items():
            if cell == partner.pos or cost > 2:
                continue
            result.append({"id": "relay", "partner": partner.id, "cell": cell,
                           "move_cost": cost, "ct_cost": 20,
                           "threats": battle.movement_threats(ghost, path)})
    return sorted(result, key=lambda row: (row["partner"], row["move_cost"], row["cell"]))


def pincer(battle, caster, target):
    result = []
    if "pincer" in caster.tactics and battle.engagement_range(caster) > 0:
        if distance(caster.pos, target.pos) <= battle.engagement_range(caster):
            cx, cy = caster.pos[0] - target.pos[0], caster.pos[1] - target.pos[1]
            for ally in battle.units:
                if (ally.id == caster.id or not ally.alive or ally.team != caster.team
                        or "pincer" not in ally.tactics or not battle._can_react(ally)
                        or ally.ct < 20 or battle.engagement_range(ally) <= 0):
                    continue
                if distance(ally.pos, target.pos) > battle.engagement_range(ally):
                    continue
                if not battle.line_of_sight(ally.pos, target.pos):
                    continue
                ax, ay = ally.pos[0] - target.pos[0], ally.pos[1] - target.pos[1]
                opposite = ((cx == 0 and ax == 0 and cy * ay < 0)
                            or (cy == 0 and ay == 0 and cx * ax < 0))
                if opposite:
                    result.append({"id": "pincer", "partner": ally.id,
                                   "target": target.id, "ct_cost": 20})

    return result

def crossfire(battle, caster, target):
    result = []
    if ("crossfire" in caster.tactics and caster.weapon == "ranged"
            and not battle.engaged_by(caster)):
        cx, cy = caster.pos[0] - target.pos[0], caster.pos[1] - target.pos[1]
        for ally in battle.units:
            if (ally.id == caster.id or not ally.alive or ally.team != caster.team
                    or "crossfire" not in ally.tactics or ally.weapon != "ranged"
                    or not battle._can_react(ally) or ally.ct < 20 or battle.engaged_by(ally)):
                continue
            skill = battle._basic(ally)
            d = distance(ally.pos, target.pos)
            if not (skill.min_range <= d <= skill.range and battle.line_of_sight(ally.pos, target.pos)):
                continue
            ax, ay = ally.pos[0] - target.pos[0], ally.pos[1] - target.pos[1]
            cross = cx * ay - cy * ax
            dot = cx * ax + cy * ay
            if cross != 0 or dot < 0:
                result.append({"id": "crossfire", "partner": ally.id,
                               "target": target.id, "ct_cost": 20})

    return result

def encirclement(battle, caster, target):
    result = []
    if ("encirclement" in caster.tactics and battle.engagement_range(caster) > 0
            and distance(caster.pos, target.pos) <= battle.engagement_range(caster)):
        def cardinal_axis(unit):
            dx, dy = unit.pos[0] - target.pos[0], unit.pos[1] - target.pos[1]
            if dx == 0 and dy:
                return 0, 1 if dy > 0 else -1
            if dy == 0 and dx:
                return 1 if dx > 0 else -1, 0
            return None

        caster_axis = cardinal_axis(caster)
        candidates = []
        if caster_axis is not None:
            for ally in battle.units:
                if (ally.id == caster.id or not ally.alive or ally.team != caster.team
                        or "encirclement" not in ally.tactics or not battle._can_react(ally)
                        or ally.ct < 20 or battle.engagement_range(ally) <= 0
                        or distance(ally.pos, target.pos) > battle.engagement_range(ally)
                        or not battle.line_of_sight(ally.pos, target.pos)):
                    continue
                ally_axis = cardinal_axis(ally)
                if ally_axis is not None and ally_axis != caster_axis:
                    candidates.append((ally.id, ally_axis))
            for left, right in combinations(sorted(candidates), 2):
                if left[1] != right[1]:
                    result.append({"id": "encirclement",
                                   "partners": [left[0], right[0]],
                                   "target": target.id, "ct_cost": 20})
                    break

    return result

def available_team_tactics(battle, caster, target):
    if not target.alive or target.team == caster.team:
        return []
    result = []
    for key in sorted(set(caster.tactics)):
        result.extend(battle.rules.tactics.get(key).options(battle, caster, target))
    return sorted(result, key=lambda row: (
        row['id'], tuple(row['partners'] if 'partners' in row else [row['partner']])))


def _resolve_team_tactic(battle, caster: Unit, target: Unit):
    options = battle.available_team_tactics(caster, target)
    if not options or not target.alive:
        return
    tactic = options[0]
    partner_ids = tactic["partners"] if "partners" in tactic else [tactic["partner"]]
    divisor = battle.rules.tactics.get(tactic["id"]).divisor
    partners = [battle.unit(uid) for uid in partner_ids]
    for partner in partners:
        partner.ct = max(0, partner.ct - tactic["ct_cost"])
    battle.emit("tactic", tactic=tactic["id"], units=[caster.id, *partner_ids],
              target=target.id, ct_cost=tactic["ct_cost"] * len(partners))
    for partner in partners:
        if not target.alive:
            break
        skill = battle._basic(partner)
        if battle.rng.random() < battle.hit_chance(partner, target, skill):
            amount = max(1, battle.damage(partner, target, skill, skill.effects[0]) // divisor)
            battle._hurt(target, amount, partner, reactions=False)
        else:
            battle.emit("miss", unit=partner.id, target=target.id)


def _relay(battle, u: Unit, partner_id: str, cell: Cell):
    require(isinstance(partner_id, str) and bool(partner_id), "Relay needs a partner")
    option = next((row for row in battle.relay_options(u)
                   if row["partner"] == partner_id and tuple(row["cell"]) == cell), None)
    require(option is not None, "Relay destination or partner unavailable")
    partner = battle.unit(partner_id)
    u.acted = True
    u.cast = None
    partner.ct = max(0, partner.ct - option["ct_cost"])
    battle.emit("tactic", tactic="relay", units=[u.id, partner.id],
              target=partner.id, cell=cell, ct_cost=option["ct_cost"])
    partner.moved = False
    battle._move(partner, cell)




def default_tactics():
    return Registry((('pincer', TacticRule(pincer)), ('crossfire', TacticRule(crossfire)),
                     ('encirclement', TacticRule(encirclement, arity=3, divisor=3)),
                     ('relay', TacticRule(lambda b, c, t: [], reposition=relay_options, execute=_relay))))

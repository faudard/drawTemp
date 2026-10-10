"""Proximity-based dual/trio tactics; existing bond unlock/codex owns discovery.

Opt-in rules work with the standard `Battle.available_team_tactics`, forecasts,
CT expenditure, battle replay and Campaign.prepare machinery.
"""
from __future__ import annotations

from itertools import combinations

from .model import distance


def _partner(battle, caster, target, other, tactic, ct_cost):
    return (other.id != caster.id and other.alive and other.team == caster.team
            and tactic in other.tactics and other.ct >= ct_cost
            and battle._can_react(other) and other.pos != caster.pos
            and distance(caster.pos, other.pos) <= 2
            and battle.engagement_range(other) > 0
            and distance(other.pos, target.pos) <= battle.engagement_range(other)
            and battle.line_of_sight(other.pos, target.pos))


def chain_strike(battle, caster, target):
    """Adjacent/nearby comrades pressure one enemy without needing a flank."""
    if ("chain_strike" not in caster.tactics or
            distance(caster.pos, target.pos) > battle.engagement_range(caster)):
        return []
    return [{"id": "chain_strike", "partner": ally.id, "target": target.id,
             "ct_cost": 25}
            for ally in sorted(battle.units, key=lambda u: u.id)
            if _partner(battle, caster, target, ally, "chain_strike", 25)]


def trio_burst(battle, caster, target):
    """A bounded 3-person move; two distinct partners pay CT to follow up."""
    if ("trio_burst" not in caster.tactics or
            distance(caster.pos, target.pos) > battle.engagement_range(caster)):
        return []
    allies = [u for u in sorted(battle.units, key=lambda u: u.id)
              if _partner(battle, caster, target, u, "trio_burst", 30)]
    return [{"id": "trio_burst", "partners": [a.id, b.id],
             "target": target.id, "ct_cost": 30}
            for a, b in combinations(allies, 2)][:1]


def synergy_readiness(battle, caster_id, target_id):
    """Pure UI view of ready combos and committed companion CT."""
    caster = next(u for u in battle.units if u.id == caster_id)
    target = next(u for u in battle.units if u.id == target_id)
    return [{"tactic": row["id"], "members": [caster.id, *row.get(
                "partners", [row["partner"]] if "partner" in row else [])],
             "target": target.id, "ct_cost": row["ct_cost"]}
            for row in battle.available_team_tactics(caster, target)]


def install_synergies(rules):
    from .rules.registry import TacticRule
    rules = rules.with_family("tactics", rules.tactics.with_rule(
        "chain_strike", TacticRule(chain_strike, arity=2, divisor=2, version="2.7.4")))
    return rules.with_family("tactics", rules.tactics.with_rule(
        "trio_burst", TacticRule(trio_burst, arity=3, divisor=3, version="2.7.4")))

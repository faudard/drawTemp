"""Opt-in positional melee pressure for Tactical RPG 3.1.

All calculations are pure. Legacy default_rules() and replay manifests stay
unchanged; the real damage and Battle.forecast share this formula.
"""
from __future__ import annotations


def facing_sector(attacker, defender):
    """Return front / flank / rear for the nearest occupied footprint cells.

    Each candidate pair is ordered deterministically. Facing is measured from
    defender to attacker; this works for 1x1 as well as large actors.
    """
    pairs = sorted(
        ((abs(a[0] - d[0]) + abs(a[1] - d[1]), d, a)
         for d in defender.occupied_cells()
         for a in attacker.occupied_cells()),
        key=lambda row: (row[0], row[1], row[2]),
    )
    if not pairs:
        return "front"
    _, d, a = pairs[0]
    offset = (a[0] - d[0], a[1] - d[1])
    dot = offset[0] * defender.facing[0] + offset[1] * defender.facing[1]
    return "rear" if dot < 0 else "front" if dot > 0 else "flank"


def positional_preview(battle, attacker_id, defender_id):
    """Read-only positioning feedback for player and AI."""
    attacker = battle.unit(attacker_id)
    defender = battle.unit(defender_id)
    sector = facing_sector(attacker, defender)
    melee = attacker.weapon in {"melee", "spear", "unarmed"}
    return {"attacker": attacker_id, "defender": defender_id,
            "sector": sector, "melee": melee,
            "damage_percent": (140 if sector == "rear" else
                               120 if sector == "flank" else 100) if melee else 100}


def install_positioning(rules):
    """Wrap the already-installed formation mitigation formula once."""
    from .rules.registry import FormulaRule

    base = rules.formulas.get("mitigation").calculate

    def mitigation(battle, caster, target, skill, effect, raw):
        amount = base(battle, caster, target, skill, effect, raw)
        if (skill.id != "attack" or skill.magical or
                caster.weapon not in {"melee", "spear", "unarmed"}):
            return amount
        sector = facing_sector(caster, target)
        if sector == "rear":
            return amount * 7 // 5
        if sector == "flank":
            return amount * 6 // 5
        return amount

    return rules.with_family(
        "formulas",
        rules.formulas.with_rule(
            "mitigation", FormulaRule(mitigation, version="3.1-positional"),
            replace_existing=True,
        ),
    )

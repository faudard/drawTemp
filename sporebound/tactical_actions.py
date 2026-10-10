"""Shared legal action descriptors for the standalone and castle players.

Only commands known to Battle are returned. The target tile is still chosen by
the player; Battle.execute remains the sole validator and state mutator.
"""
from __future__ import annotations

from .model import RuleError, distance


def tactical_action_options(battle):
    actor = battle.active
    if actor is None or actor.team != "player" or battle.result or battle.deploying:
        return []
    options = []
    if "charge" in battle.rules.commands and battle.charge_options(actor):
        options.append("charge")
    if ("disengage" in battle.rules.commands and not actor.acted
            and not battle.status_blocks(actor, "act") and battle.engaged_by(actor)):
        options.append("disengage")
    if not actor.acted and not battle.status_blocks(actor, "act"):
        if "formation" in battle.rules.commands:
            options += ["formation:none", "formation:shield_wall"]
            if actor.weapon == "spear":
                options.append("formation:phalanx")
            options += ["formation:escort:" + unit.id
                        for unit in sorted(battle.units, key=lambda u: u.id)
                        if unit.alive and unit.team == actor.team and unit.id != actor.id
                        and distance(unit.pos, actor.pos) <= 2]
        if "prepare" in battle.rules.commands:
            for mode in sorted(battle.rules.preparations.manifest()):
                rule = battle.rules.preparations.get(mode)
                if rule.targeted:
                    targets = [u.id for u in sorted(battle.units, key=lambda u: u.id)
                               if u.alive and u.team == actor.team and u.id != actor.id]
                else:
                    targets = [None]
                for target in targets:
                    try:
                        rule.validate(battle, actor, target)
                    except RuleError:
                        continue
                    options.append("prepare:" + mode + (":" + target if target else ""))
        if "relay" in battle.rules.tactics:
            options += ["relay:" + uid for uid in sorted({
                row["partner"] for row in battle.relay_options(actor)})]
    return options


def tactical_command(option, cell):
    """Convert one explicit widget selection into a normal Battle command."""
    if option == "charge":
        return {"kind": "charge", "cell": list(cell)}
    if option == "disengage":
        return {"kind": "disengage"}
    if option.startswith("formation:"):
        rest = option[len("formation:"):]
        if rest.startswith("escort:"):
            return {"kind": "formation", "mode": "escort", "target": rest[len("escort:"):]}
        return {"kind": "formation", "mode": rest}
    if option.startswith("prepare:"):
        rest = option[len("prepare:"):]
        mode, _, target = rest.partition(":")
        return {"kind": "prepare", "mode": mode, **({"target": target} if target else {})}
    if option.startswith("relay:"):
        return {"kind": "relay", "partner": option[len("relay:"):], "cell": list(cell)}
    raise RuleError("Unknown tactical action selection")

"""Pure, bounded combat telegraphs shared by Studio and both Tk players.

There is no hidden future AI simulation: casts and armed reactions are known,
charge corridors are POSSIBILITIES, and CT times assume unchanged speeds.
"""
from __future__ import annotations

from .model import distance
from .rules import statuses


def activation_timeline(battle, limit=8):
    if battle.result or battle.deploying:
        return []
    rows = []
    for order, actor in enumerate(battle.units):
        if not actor.alive:
            continue
        blocked = battle.status_blocks(actor, "activation")
        speed = statuses.speed(battle, actor)
        if actor.id == battle.active_id:
            eta = 0
        elif blocked or speed <= 0:
            eta = None
        else:
            eta = max(0, (100 - actor.ct + speed - 1) // speed)
        rows.append({"unit": actor.id, "team": actor.team,
                     "eta_ticks": eta, "active": actor.id == battle.active_id,
                     "uncertain": actor.id != battle.active_id,
                     "blocked": blocked})
    rows.sort(key=lambda item: (
        item["eta_ticks"] is None,
        item["eta_ticks"] if item["eta_ticks"] is not None else 999999,
        not item["active"],
        next(i for i, u in enumerate(battle.units) if u.id == item["unit"]),
    ))
    return rows[:limit]


def tactical_intents(battle, *, max_cells=1024):
    """Snapshot observable and conditional threats; never modifies Battle/RNG.

    max_cells bounds prepared-reaction overlays for huge authoring maps.
    """
    result = {"timeline": activation_timeline(battle),
              "casts": [], "charges": [], "prepared": [],
              "danger": [], "truncated": False}
    if battle.result or battle.deploying:
        return result

    danger = {}
    for cell, tile in sorted(battle.board.tiles.items()):
        if tile.hazard:
            danger[("hazard", cell)] = {
                "kind": "hazard", "cell": list(cell),
                "amount": tile.hazard, "certainty": "certain"}

    for actor in sorted(battle.units, key=lambda u: u.id):
        if not actor.alive:
            continue
        if actor.cast:
            cast = actor.cast
            skill = battle.content.skills[cast["skill"]]
            recipient = next((u for u in battle.units
                              if u.id == cast.get("unit")), None)
            cell = recipient.pos if recipient is not None else tuple(cast["cell"])
            cells = sorted(battle._area(cell, skill))
            result["casts"].append({
                "unit": actor.id, "team": actor.team,
                "skill": skill.id, "remaining_ticks": cast["remaining"],
                "cell": list(cell), "cells": [list(c) for c in cells],
                "certainty": "scheduled"})
            if actor.team == "enemy":
                for pos in cells:
                    danger[("cast", pos)] = {"kind": "cast", "cell": list(pos),
                                            "unit": actor.id, "certainty": "scheduled"}
        # Only telegraph a possible lane, not a promised future boss command.
        if (actor.team == "enemy" and actor.behavior == "phase_boss"
                and "charge" in battle.rules.commands):
            for option in battle.charge_options(actor)[:4]:
                result["charges"].append({
                    "unit": actor.id, "target": option["target"],
                    "landing": list(option["landing"]),
                    "certainty": "possible"})
                for cell in (option["landing"], option["cell"]):
                    danger[("charge", tuple(cell))] = {
                        "kind": "charge", "cell": list(cell),
                        "unit": actor.id, "certainty": "possible"}

    armed = sorted((uid, prep) for uid, prep in battle.prepared_reactions.items()
                   if battle.unit(uid).alive and battle.unit(uid).team == "enemy"
                   and battle._can_react(battle.unit(uid))
                   and prep.get("charges", 0) > 0)
    if armed:
        tiles = list(battle.board.cells())
        result["truncated"] = len(tiles) > max_cells
        for cell in tiles[:max_cells]:
            for uid, prep in armed:
                watcher = battle.unit(uid)
                if battle.rules.preparations.get(prep["mode"]).covers(
                        battle, watcher, cell):
                    danger[("prepared", cell)] = {
                        "kind": "prepared", "cell": list(cell), "unit": uid,
                        "certainty": "armed"}
        result["prepared"] = [{"unit": uid, "mode": prep["mode"],
                               "charges": prep["charges"]}
                              for uid, prep in armed]

    order = {"hazard": 0, "prepared": 1, "cast": 2, "charge": 3}
    result["danger"] = sorted(danger.values(),
                              key=lambda row: (order[row["kind"]], row["cell"], row.get("unit", "")))
    return result

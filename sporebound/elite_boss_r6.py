"""R6.6 opt-in elite boss decisions and honest telegraphs.

Reuses existing Battle.reachable/charge_options/forecast and event triggers:
no new actor state, random rolls, pathfinder, wave scheduler or save schema.
"""
from __future__ import annotations

from copy import deepcopy

from .model import distance


def _phase(actor):
    return int(next((t.partition(":")[2] for t in actor.tags
                     if t.startswith("boss_phase:")), "1"))


def _separation(cells, opponent):
    return min(distance(a, b) for a in cells for b in opponent.occupied_cells())


def _path_exposure(battle, actor, path, destination):
    """Compare paths by the same encounter threats and actual footprint hazards."""
    threats = battle.movement_threats(actor, path)
    risk = sum(row.get("amount", 0) * row.get("chance", 0) for row in threats)
    # Applying the full hazard along the whole footprint is intentionally
    # conservative; the resolver remains the authority for actual damage.
    hazards = sum(max(battle.board.tile(cell).hazard
                      for cell in actor.occupied_cells(node))
                  for node in path[1:])
    landing_hazard = max(battle.board.tile(c).hazard
                         for c in actor.occupied_cells(destination))
    return risk + hazards + landing_hazard


def adaptive_boss_command(battle):
    """Choose only canonical commands, with deterministic footprint-aware terrain.

    Phase one retains the existing guard; later phases favor safe charges.
    If there is already a legal attack/interact, do not override it merely
    for terrain advantage. Movement goes through the real reachable map.
    """
    from .bosses3 import phase_boss_command
    from .coordinated_ai import coordinated_command

    actor = battle.active
    if actor is None or actor.cast:
        return phase_boss_command(battle)
    if battle.unit_levels.get(actor.id, 0):
        # Layered navigation and vertical attacks belong to the base AI.
        return coordinated_command(battle)
    phase = _phase(actor)
    if phase <= 1:
        return phase_boss_command(battle)
    baseline = coordinated_command(battle)
    if baseline["kind"] in {"act", "level_attack", "interact", "siege_attack",
                            "repair_siege", "item", "formation", "prepare"}:
        return baseline
    opponents = sorted((u for u in battle.units if u.alive
                        and u.team != actor.team
                        and battle.unit_levels.get(u.id, 0) == 0),
                       key=lambda u: u.id)
    if not opponents:
        return baseline

    if ("charge" in battle.rules.commands and not actor.moved
            and not actor.acted and not battle.status_blocks(actor, "charge")):
        charges = []
        for option in battle.charge_options(actor):
            target = battle.unit(option["target"])
            row = battle.reachable(actor).get(tuple(option["landing"]))
            if row is None:
                continue
            exposure = _path_exposure(battle, actor, row[1],
                                      tuple(option["landing"]))
            if exposure >= max(1, actor.hp / 3):
                continue
            # Prefer pressure on weak targets without assuming a hit. Charge's
            # actual hit/damage/RNG remain exclusively in Battle._charge.
            priority = min(target.hp, actor.attack + actor.weapon_power)
            score = priority * 2 + option["distance"] * 2 - exposure
            charges.append((-score, exposure, target.id, list(option["cell"])))
        if charges:
            return {"kind": "charge", "cell": min(charges)[3]}

    if (actor.moved or "move" not in battle.rules.commands
            or battle.status_blocks(actor, "move")):
        return baseline
    current = actor.occupied_cells()
    initial = min(_separation(current, foe) for foe in opponents)
    current_tile = battle.board.tile(actor.pos)
    options = []
    reachable = battle.reachable(actor)
    for anchor, (cost, path) in sorted(reachable.items()):
        if anchor == actor.pos:
            continue
        footprint = actor.occupied_cells(anchor)
        remaining = min(_separation(footprint, foe) for foe in opponents)
        progress = initial - remaining
        if progress <= 0:
            continue
        exposure = _path_exposure(battle, actor, path, anchor)
        if exposure >= max(1, actor.hp / 3):
            continue
        cover = min(battle.board.tile(cell).cover for cell in footprint)
        height = min(battle.board.tile(cell).height for cell in footprint)
        # Route cost and cover are tie-breakers, not replacements for
        # geometric pressure or risk. Both are evaluated on real tiles.
        score = (progress * 10 + (cover - current_tile.cover) * .1
                 + (height - current_tile.height) * 2
                 - exposure - cost * .3)
        if score > 0:
            options.append((-score, exposure, cost, anchor))
    if options:
        return {"kind": "move", "cell": list(min(options)[3])}
    # Refuse highly exposed default Move instead of blindly entering a
    # lethal hazard. Guard/end are already legal standard command paths.
    if baseline["kind"] == "move":
        node = reachable.get(tuple(baseline["cell"]))
        if node is not None and _path_exposure(
                battle, actor, node[1], tuple(baseline["cell"])) >= max(1, actor.hp / 3):
            return {"kind": "end"}
    return baseline


def boss_r6_telegraph(battle, boss_id):
    """Observed footprint + pending scripted waves + conditional current intent.

    Off-turn AI choices remain unknown. Authored wave triggers describe a
    *possible* reinforcement, while already queued waves are known facts.
    """
    from .bosses3 import boss_intent_preview
    actor = battle.unit(boss_id)
    view = boss_intent_preview(battle, boss_id)
    result = {
        **view, "behavior": actor.behavior,
        "occupied_cells": [list(cell) for cell in sorted(actor.occupied_cells())],
        "certainty": "conditional" if view["ready"] else "unknown",
        "threat_cells": [], "destination_cells": [], "path": [],
        "reinforcements": [], "queued_waves": [],
    }
    for wave in battle.encounter.pending:
        result["queued_waves"].append({
            "id": wave["id"], "count": len(wave["actors"]), "certainty": "queued"})
    for trigger in sorted(battle.mission.triggers, key=lambda item: item["id"]):
        if (trigger["id"] in battle.fired
                or trigger.get("condition") != "hp_below"
                or trigger.get("unit") != boss_id):
            continue
        waves = [action for action in trigger.get("actions", [])
                 if action.get("kind") in {"queue_wave", "wave", "spawn"}]
        for action in waves:
            result["reinforcements"].append({
                "trigger": trigger["id"], "percent": trigger["percent"],
                "kind": action["kind"],
                "count": (1 if action["kind"] == "spawn"
                          else len(action.get("actors", []))),
                "certainty": "possible"})
    if actor.cast:
        skill = battle.content.skills.get(actor.cast.get("skill"))
        if skill:
            target = next((u for u in battle.units
                           if u.id == actor.cast.get("unit")), None)
            cell = target.pos if target else tuple(actor.cast["cell"])
            result["cast"] = {
                "skill": skill.id, "remaining_ticks": actor.cast["remaining"],
                "cells": [list(c) for c in sorted(battle._area(cell, skill))],
                "certainty": "scheduled"}
    command = view["command"]
    if command is None:
        return result
    if command["kind"] == "charge":
        option = next((row for row in battle.charge_options(actor)
                       if list(row["cell"]) == command["cell"]), None)
        if option:
            path = battle.reachable(actor).get(tuple(option["landing"]))
            if path:
                result["path"] = [list(node) for node in path[1]]
                result["destination_cells"] = [
                    list(c) for c in sorted(actor.occupied_cells(option["landing"]))]
            result["threat_cells"] = [list(c) for c in
                                      sorted(battle.unit(option["target"]).occupied_cells())]
    elif command["kind"] == "move":
        path = battle.reachable(actor).get(tuple(command["cell"]))
        if path:
            result["path"] = [list(node) for node in path[1]]
            result["destination_cells"] = [
                list(c) for c in sorted(actor.occupied_cells(command["cell"]))]
    elif command["kind"] == "act":
        skill = battle._skill(actor, command["skill"])
        result["threat_cells"] = [
            list(c) for c in sorted(battle._area(tuple(command["cell"]), skill))]
    return result

"""R6 tactical integration: optional objective rules and pure Player/Studio diagnostics.

All tactical choices remain in the existing AI and Battle.execute. This module
adds no persisted fields, alternate clock, damage calculation or random rolls.
"""
from __future__ import annotations

from copy import deepcopy

from .model import RuleError, distance, require
from .rules.registry import ObjectiveRule


ADVANCED_OBJECTIVES = frozenset({"capture", "escort", "defend", "sabotage", "retreat"})


def _occupies(battle, team, cell):
    return any(unit.alive and unit.team == team
               and battle.unit_levels.get(unit.id, 0) == 0
               and cell in unit.occupied_cells()
               for unit in battle.units)


def _goal_owned(battle, cell):
    return _occupies(battle, "player", cell) and not _occupies(battle, "enemy", cell)


def _capture(battle):
    return bool(battle.mission.goal) and all(
        _goal_owned(battle, tuple(cell)) for cell in battle.mission.goal)


def _escort(battle):
    protected = battle.mission.protected_id
    return bool(protected) and any(
        unit.id == protected and unit.alive and unit.team == "player"
        and battle.unit_levels.get(unit.id, 0) == 0
        and any(tuple(cell) in unit.occupied_cells() for cell in battle.mission.goal)
        for unit in battle.units)


def _defend(battle):
    protected = battle.mission.protected_id
    return bool(protected and battle.unit(protected).alive
                and battle.tick >= battle.mission.target_ticks)


def _sabotage(battle):
    defenses = [obj for obj in battle.mission.objects
                if obj["kind"] == "defense" and obj.get("team") == "enemy"]
    return bool(defenses) and all(obj.get("disabled", False) for obj in defenses)


def _retreat(battle):
    survivors = [unit for unit in battle.units if unit.alive and unit.team == "player"]
    return bool(survivors and battle.mission.goal) and all(
        battle.unit_levels.get(unit.id, 0) == 0
        and any(tuple(cell) in unit.occupied_cells() for cell in battle.mission.goal)
        for unit in survivors)


def install_objectives(rules):
    """Install explicit versioned policies; vanilla rules and old replays stay unchanged."""
    policies = (
        ("capture", _capture, True),
        ("escort", _escort, True),
        ("defend", _defend, False),
        ("sabotage", _sabotage, False),
        ("retreat", _retreat, True),
    )
    registry = rules.objectives
    for name, predicate, needs_goal in policies:
        registry = registry.with_rule(
            name, ObjectiveRule(predicate, needs_goal=needs_goal, version="6.4"))
    return rules.with_family("objectives", registry)


def tactical_r6_rules(base=None):
    """Explicit opt-in that preserves previous Tactical RPG 3.0 manifests."""
    from .tactical_rpg3 import tactical_rpg_rules
    from .rules.registry import BehaviorRule
    from .elite_boss_r6 import adaptive_boss_command
    rules = install_objectives(tactical_rpg_rules(base))
    return rules.with_family("behaviors", rules.behaviors.with_rule(
        "adaptive_boss", BehaviorRule(adaptive_boss_command, version="6.6")))


def objective_progress(battle):
    """Actual objective facts, never a prediction of success or AI behavior."""
    mission = battle.mission
    cells = [{"cell": list(cell),
              "player": _occupies(battle, "player", tuple(cell)),
              "enemy": _occupies(battle, "enemy", tuple(cell)),
              "controlled": _goal_owned(battle, tuple(cell))}
             for cell in sorted(mission.goal)]
    defenses = [{"id": obj["id"], "disabled": bool(obj.get("disabled", False))}
                for obj in sorted(mission.objects, key=lambda o: o["id"])
                if obj["kind"] == "defense" and obj.get("team") == "enemy"]
    return {"kind": mission.objective, "goal_cells": cells,
            "protected": mission.protected_id or None,
            "elapsed_ticks": battle.tick,
            "target_ticks": mission.target_ticks
            if mission.objective in {"survive", "hold", "defend"} else None,
            "hold_ticks": battle.hold_ticks if mission.objective == "hold" else None,
            "defenses": defenses if mission.objective == "sabotage" else [],
            "achieved": battle.rules.objectives.get(mission.objective).achieved(battle),
            "certainty": "observed"}


def squad_coordination(battle):
    """Comparable squad metrics for Battle Lab, Studio and Player.

    Reports real adjacency/cover/formation and current goals; does not invent
    future ally turns or compute a second AI policy.
    """
    from .coordinated_ai import squad_role
    from .formations3 import formation_preview

    result = []
    for team in ("player", "enemy"):
        group = sorted((u for u in battle.units if u.team == team and u.alive),
                       key=lambda u: u.id)
        medics = [u for u in group if squad_role(u) == "medic"
                  or "medic" in u.tags or "healer" in u.tags]
        frontline = [u for u in group if squad_role(u) in {"vanguard", "pikeman"}
                     or "protector" in u.tags]
        protected = sum(any(distance(guard.pos, medic.pos) == 1
                            for guard in frontline if guard.id != medic.id)
                        for medic in medics)
        formations = []
        for unit in group:
            if not any(tag.startswith("formation:") for tag in unit.tags):
                continue
            view = formation_preview(battle, unit.id)
            if any(view[key] for key in ("shield_wall", "phalanx", "escort")):
                formations.append(unit.id)
        contested = sum(_occupies(battle, team, tuple(cell))
                        for cell in battle.mission.goal)
        result.append({"team": team, "units": len(group),
                       "medics": len(medics), "protected_medics": protected,
                       "active_formations": sorted(formations),
                       "occupied_goal_cells": contested,
                       "certainty": "observed"})
    return result


def active_enemy_plan(battle):
    """Conditional preview of only the active enemy's *current* legal choice.

    Off-turn planning is deliberately excluded: CT, targets, terrain and
    interrupts can change before a future activation.
    """
    actor = battle.active
    if battle.result or battle.deploying or actor is None or actor.team != "enemy":
        return None
    from .ai import choose_command

    command = deepcopy(choose_command(battle))
    view = {"unit": actor.id, "command": command,
            "certainty": "conditional", "horizon": "current_activation",
            "floor": battle.unit_levels.get(actor.id, 0),
            "area": [], "risk": [], "terrain": None}
    kind = command["kind"]
    if kind == "act":
        try:
            view["area"] = deepcopy(battle.forecast(
                command["skill"], tuple(command["cell"]), actor))
        except RuleError:
            pass
    elif kind == "charge":
        view["area"] = deepcopy(next(
            (option["threats"] for option in battle.charge_options(actor)
             if list(option["cell"]) == command["cell"]), []))
    elif kind == "move":
        target = tuple(command["cell"])
        path = battle.reachable(actor).get(target)
        if path is not None:
            view["risk"] = deepcopy(battle.movement_threats(actor, path[1]))
    elif kind == "level_move":
        from .level_navigation import available_level_moves
        target = (command["level"], *command["cell"])
        path = available_level_moves(battle, actor).get(target)
        if path is not None:
            view["path_levels"] = [list(node) for node in path[1]]
    if kind in {"move", "act", "charge"} and "cell" in command:
        cell = tuple(command["cell"])
        if battle.board.contains(cell):
            tile = battle.board.tile(cell)
            view["terrain"] = {"cell": list(cell), "height": tile.height,
                               "cover": tile.cover, "hazard": tile.hazard,
                               "blocked": tile.blocked}
    return view


def party_build_preview(content, campaign, mission_id, *, ruleset=None):
    """Prepare through the real campaign pipeline on a copy; do not spend JP.

    Effective stats include job, equipment, talents, profile and campaign
    growth, unlike a second hand-maintained build formula.
    """
    from .builds3 import talent_catalog
    from .campaign import HeroProgress
    from .tactical_rpg3 import authored_rules_for_document

    selected_rules = ruleset or authored_rules_for_document(content.to_dict())
    prepared = deepcopy(campaign).prepare(content, mission_id, seed=1,
                                          ruleset=selected_rules)
    roster = []
    for unit in sorted(prepared.units, key=lambda item: item.id):
        if unit.team != "player":
            continue
        hero = deepcopy(campaign.heroes.get(unit.id, HeroProgress()))
        talents = (talent_catalog(content, hero, hero.job)
                   if hero.job in content.jobs else
                   {"job": hero.job, "available_jp": 0, "talents": []})
        roster.append({
            "unit": unit.id, "job": hero.job,
            "secondary_job": hero.secondary_job, "level": hero.level,
            "equipment": dict(sorted(hero.equipment.items())),
            "skills": sorted(unit.skills), "tactics": sorted(unit.tactics),
            "tags": sorted(unit.tags), "talents": talents,
            "stats": {key: getattr(unit, key)
                      for key in ("max_hp", "max_mp", "attack", "magic",
                                  "defense", "magic_defense", "speed",
                                  "move", "weapon_power")},
        })
    return {"mission": mission_id, "party_size": len(roster), "heroes": roster,
            "certainty": "prepared_build_no_resources_spent"}

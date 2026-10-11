"""Role-based encounter budgets and deterministic three-mission validation (3.1.6)."""
from copy import deepcopy
from dataclasses import asdict
import json

from .ai import simulate
from .campaign import Campaign
from .engine import Battle
from .model import require
from .tactical_rpg3 import tactical_rpg_rules


def role(unit):
    for tag in unit.tags:
        if tag.startswith("doctrine:"):
            return tag.split(":", 1)[1]
    if unit.weapon == "spear":
        return "guardian"
    if unit.weapon == "ranged":
        return "artillery"
    if "healer" in unit.tags:
        return "support"
    return "frontline"


def budget(unit):
    """Heuristic for composition, never an alternate damage formula."""
    return max(1, unit.max_hp // 8 + unit.attack * 2
               + unit.weapon_power + unit.defense + unit.speed // 3)


def analyze_encounter(content, mission_id, *, max_active=14):
    require(mission_id in content.missions, "Unknown encounter")
    mission = content.missions[mission_id]
    sides = {team: [unit for unit in mission.units if unit.team == team]
             for team in ("player", "enemy")}
    scores = {team: sum(budget(unit) for unit in units)
              for team, units in sides.items()}
    ratio = round(scores["enemy"] / max(1, scores["player"]), 3)
    enemy_roles = sorted({role(unit) for unit in sides["enemy"]})
    warnings = []
    if len(mission.units) > max_active:
        warnings.append("Too many active combatants")
    if not sides["enemy"] or not sides["player"]:
        warnings.append("Both sides must have units")
    if ratio < .7:
        warnings.append("Encounter may be too easy")
    elif ratio > 1.3:
        warnings.append("Encounter may be too hard")
    if len(sides["enemy"]) >= 3 and len(enemy_roles) < 2:
        warnings.append("Enemy composition lacks distinct tactical roles")
    return {"mission": mission_id, "player_budget": scores["player"],
            "enemy_budget": scores["enemy"], "ratio": ratio,
            "enemy_roles": enemy_roles, "warnings": warnings,
            "balanced": not warnings}


def analyze_three(content, mission_ids):
    require(len(mission_ids) == 3 and len(set(mission_ids)) == 3,
            "Select three distinct encounters")
    reports = [analyze_encounter(content, key) for key in mission_ids]
    return {"encounters": reports,
            "balanced": all(row["balanced"] for row in reports),
            "distinct_roles": sorted({r for row in reports for r in row["enemy_roles"]})}


def replay_three(content, campaign, mission_ids, *, max_commands=800, seeds=(1, 2, 3)):
    """Real battles, replay digests and JSON round-trip after each encounter.

    No slot is overwritten: the supplied campaign is deep-copied. The caller
    can save the returned snapshot only after inspecting the report.
    """
    require(len(mission_ids) == len(seeds) == 3, "Three encounters and seeds required")
    current = deepcopy(campaign)
    rules = tactical_rpg_rules()
    records = []
    for mission_id, seed in zip(mission_ids, seeds):
        battle = current.prepare(content, mission_id, seed, ruleset=rules)
        simulation = simulate(battle, max_commands=max_commands)
        replay = Battle.replay(battle.recording(), rules=rules)
        require(replay.digest() == battle.digest(), "Replay diverged")
        committed = current.finish(battle)
        snapshot = json.loads(json.dumps({"version": 1, **asdict(current)}))
        current = Campaign.from_dict(snapshot, ruleset=rules)
        records.append({"mission": mission_id, "result": simulation["result"],
                        "commands": simulation["commands"],
                        "replay_digest": replay.digest(), "committed": committed,
                        "resume_checked": True})
    return {"encounters": records, "campaign": current,
            "all_victories": all(row["result"] == "victory" for row in records)}

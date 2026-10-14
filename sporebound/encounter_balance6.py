"""R6 balance evidence built on the existing Battle Lab, Matrix and Campaign.

Analytics are observations and review signals, not alternate game rules or
proofs of human balance. All simulations use canonical Battle/AI/replay.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
from .ai import simulate
from .balance_matrix import compare_matrices
from .battle_diagnostics import trace_seed
from .campaign import Campaign
from .encounter_balance31 import budget
from .engine import Battle
from .model import Content, require
from .playtest_telemetry import analyze_playtests, validate_report


SCHEMA = 1
CONFUSION_TAGS = {"objective", "positioning", "controls", "resources",
                  "tutorial", "other"}
EXIT_REASONS = {"difficulty", "unclear_objective", "technical",
                "voluntary", "unknown"}


def encounter_profile(content, mission_id):
    """Inventory an authored encounter; never pad small rosters artificially."""
    require(isinstance(content, Content) and mission_id in content.missions,
            "Unknown encounter profile")
    mission = content.missions[mission_id]
    sides = {team: [u for u in mission.units if u.team == team]
             for team in ("player", "enemy")}
    heroes, enemies = len(sides["player"]), len(sides["enemy"])
    return {
        "kind": "encounter_profile", "schema": SCHEMA,
        "mission": mission_id, "objective": mission.objective,
        "map": {"width": mission.board.width, "height": mission.board.height},
        "player_count": heroes, "enemy_count": enemies,
        "target": {"players": [4, 6], "enemies": [5, 10],
                   "human_minutes": [15, 30]},
        "target_roster_met": 4 <= heroes <= 6 and 5 <= enemies <= 10,
        "units": [{"id": u.id, "team": u.team, "weapon": u.weapon,
                   "behavior": u.behavior, "pos": list(u.pos),
                   "level": mission.unit_levels.get(u.id, 0)}
                  for u in mission.units],
        "note": "Roster and duration are design targets, not engine gates",
    }


def ai_decision_analytics(trace):
    """Extract explanations from a verified canonical decision trace.

    No-op moves, A→B→A cycles and repeated waiting are warning heuristics;
    they do not establish that a move was strategically unnecessary.
    """
    require(type(trace) is dict and trace.get("kind") == "battle_diagnostics"
            and trace.get("replay_verified") is True
            and type(trace.get("steps")) is list,
            "AI analytics require a replay-verified diagnostic trace")
    actions = Counter()
    by_team = Counter()
    actor_teams = {u["id"]: u["team"] for u in trace["initial"]["units"]}
    positions = {u["id"]: [tuple(u["pos"])] for u in trace["initial"]["units"]}
    findings = Counter()
    findings_by_team = Counter()
    evidence = []
    controlled = 0
    protections = 0
    reactions_total = 0
    for step in trace["steps"]:
        actor = step["actor"]
        team = step["team"]
        kind = step["command"]["kind"]
        actions[kind] += 1
        by_team[team + ":" + kind] += 1
        frame = {u["id"]: u for u in step["after"]["units"]}
        events = step["events"]
        protections += sum(e.get("kind") == "intercept" for e in events)
        reactions_total += sum(e.get("kind") in (
            "intercept", "prepared_triggered", "counter", "opportunity")
            for e in events)
        goal = trace["board"]["goals"]
        if team == "player" and any(
                u["alive"] and u["team"] == "player" and u["pos"] in goal
                for u in frame.values()):
            controlled += 1
        code = None
        if kind == "move" and actor in frame and actor in positions:
            previous = positions[actor]
            new_pos = tuple(frame[actor]["pos"])
            if new_pos == previous[-1]:
                code = "move_without_displacement"
            elif len(previous) >= 2 and new_pos == previous[-2]:
                code = "backtrack"
            if new_pos != previous[-1]:
                previous.append(new_pos)
        if code is not None:
            findings[code] += 1
            findings_by_team[team + ":" + code] += 1
            evidence.append({"step": step["index"], "actor": actor,
                             "team": team, "signal": code})
    findings.update(trace["diagnostics"]["counts"])
    return {
        "kind": "ai_decision_analytics", "schema": SCHEMA,
        "mission": trace["mission"], "seed": trace["seed"],
        "digest": trace["digest"], "replay_verified": True,
        "actions": dict(sorted(actions.items())),
        "team_decisions": dict(sorted(by_team.items())),
        "team_findings": dict(sorted(findings_by_team.items())),
        "signals": dict(sorted(findings.items())),
        "protective_reactions": protections,
        "all_reactions_observed": reactions_total,
        "player_goal_occupied_commands": controlled,
        "objective_hold_ticks_end": (
            trace["steps"][-1]["after"]["hold_ticks"]
            if trace["steps"] else trace["initial"]["hold_ticks"]),
        "evidence": evidence[:100],
        "limitations": "Heuristics only; trace does not expose discarded AI candidates",
    }


def trace_encounter_ai(content, mission_id, *, seed=1, max_commands=500,
                       rules=None, initial_state=None):
    """Run real AI and preserve trace for drilldown; caller chooses export."""
    trace = trace_seed(content, mission_id, seed=seed,
                       max_commands=max_commands, rules=rules,
                       initial_state=initial_state)
    return {"analytics": ai_decision_analytics(trace), "trace": trace}


def strict_regression_gate(before, after, **thresholds):
    """Compare fixed encounter profiles and initial rule manifests, paired by seed.

    If scenario definitions or rules change, request a fresh reference instead
    of presenting the incomparable run as a pass.
    """
    comparison = compare_matrices(before, after, **thresholds)
    old = {row["id"]: row for row in before["cases"]}
    current = {row["id"]: row for row in after["cases"]}
    incompatible = []
    for key in sorted(old):
        a, b = old[key], current[key]
        if a["spec"] != b["spec"]:
            incompatible.append(key + ": scenario changed")
        if a["report"]["rules_manifest"] != b["report"]["rules_manifest"]:
            incompatible.append(key + ": initial rules changed")
        if not all(s.get("replay_verified") is True
                   for s in a["report"]["samples"] + b["report"]["samples"]):
            incompatible.append(key + ": unverified replay")
    passed = comparison["passed"] and not incompatible
    return {"kind": "r6_regression_gate", "schema": SCHEMA,
            "status": "pass" if passed else "fail", "passed": passed,
            "incompatible_inputs": incompatible,
            "regressions": comparison["failures"], "matrix_gate": comparison}


def human_variant_breakdown(report, annotations=(), *, min_complete=5):
    """Per-mission and per-variant human minutes, failures and confusion tags.

    Annotations are separate opt-in review data indexed by exported session
    position, with categorical tags only (no free-text/person identifiers).
    """
    validate_report(report)
    require(type(min_complete) is int and min_complete >= 1,
            "Invalid human-playtest minimum")
    require(type(annotations) in (list, tuple), "Invalid playtest annotations")
    labels = {}
    for item in annotations:
        require(type(item) is dict
                and set(item) <= {"index", "variant", "confusion", "exit_reason"}
                and type(item.get("index")) is int
                and 0 <= item["index"] < len(report["sessions"])
                and item["index"] not in labels
                and type(item.get("variant", "authored")) is str
                and 1 <= len(item.get("variant", "authored")) <= 64
                and type(item.get("confusion", [])) is list
                and len(set(item.get("confusion", []))) == len(item.get("confusion", []))
                and set(item.get("confusion", [])) <= CONFUSION_TAGS
                and item.get("exit_reason", "unknown") in EXIT_REASONS,
                "Invalid categorical playtest annotation")
        labels[item["index"]] = item
    groups = defaultdict(list)
    confusion = defaultdict(Counter)
    reasons = defaultdict(Counter)
    for index, row in enumerate(report["sessions"]):
        tag = labels.get(index, {})
        key = (row["mission"], tag.get("variant", "authored"))
        groups[key].append(row)
        confusion[key].update(tag.get("confusion", []))
        if row["outcome"] == "abandoned":
            reasons[key][tag.get("exit_reason", "unknown")] += 1
    outputs = []
    for key in sorted(groups):
        subset = {**report, "sessions": groups[key]}
        summary = analyze_playtests(subset, mission=key[0])
        completed = summary["complete_observations"]
        p50 = summary["human_duration_minutes_p50"]
        outputs.append({
            "mission": key[0], "variant": key[1], "summary": summary,
            "failures": summary["outcomes"].get("defeat", 0),
            "confusion": dict(sorted(confusion[key].items())),
            "exit_reasons": dict(sorted(reasons[key].items())),
            "goal_occupancy": sum(bool(s.get("goal_occupied"))
                                  for s in groups[key]),
            "objective_hold_ticks_max": max(
                (s.get("objective_hold_ticks", 0) for s in groups[key]),
                default=0),
            "duration_target_15_30_minutes": (
                15 <= p50 <= 30 if completed >= min_complete and p50 is not None
                else None),
            "sample_sufficient": completed >= min_complete,
        })
    return {"kind": "r6_human_variants", "schema": SCHEMA,
            "target": "15-30 real human minutes; unverified below min_complete",
            "groups": outputs}


def campaign_balance_curve(content, campaign, missions, *, seeds,
                           max_commands=500, rules=None):
    """Play real consecutive Campaign encounters, never author fictitious XP.

    On a loss or locked mission the curve records the obstruction, then stops.
    The caller's Campaign and Content are not changed.
    """
    require(isinstance(content, Content) and isinstance(campaign, Campaign),
            "Expected authored Content and Campaign")
    require(type(missions) in (tuple, list) and bool(missions)
            and len(missions) <= 24 and len(missions) == len(set(missions))
            and all(type(x) is str and x in content.missions for x in missions),
            "Expected unique authored campaign missions")
    require(type(seeds) in (list, tuple) and len(seeds) == len(missions)
            and all(type(s) is int and 0 <= s < 2**32 for s in seeds),
            "Expected a seed for each mission")
    require(type(max_commands) is int and 1 <= max_commands <= 10000,
            "Invalid campaign command cap")
    progress = deepcopy(campaign)
    authored = content.to_dict()
    rows = []
    for mid, seed in zip(missions, seeds):
        if mid not in progress.unlocked:
            rows.append({"mission": mid, "seed": seed, "status": "locked"})
            break
        before_gold = progress.gold
        before_xp = {uid: hero.xp for uid, hero in progress.heroes.items()}
        before_inventory = deepcopy(progress.inventory)
        battle = progress.prepare(content, mid, seed=seed, ruleset=rules)
        sides = {team: [u for u in battle.units if u.team == team]
                 for team in ("player", "enemy")}
        budget_player = sum(budget(u) for u in sides["player"])
        budget_enemy = sum(budget(u) for u in sides["enemy"])
        outcome = simulate(battle, max_commands=max_commands)
        replay = Battle.replay(battle.recording(), rules=battle.rules)
        require(outcome["digest"] == replay.digest(),
                "Campaign curve replay divergence")
        committed = progress.finish(battle)
        rows.append({
            "mission": mid, "seed": seed, "status": outcome["result"],
            "commands": outcome["commands"], "ticks_ct": outcome["ticks"],
            "digest": outcome["digest"], "replay_verified": True,
            "player_units": len(sides["player"]), "enemy_units": len(sides["enemy"]),
            "enemy_to_player_budget": round(budget_enemy / max(1, budget_player), 4),
            "rewards_committed": committed,
            "xp_delta": {uid: hero.xp - before_xp.get(uid, 0)
                         for uid, hero in sorted(progress.heroes.items())
                         if hero.xp != before_xp.get(uid, 0)},
            "gold_delta": progress.gold - before_gold,
            "inventory_before": before_inventory,
            "inventory_after": deepcopy(progress.inventory),
            "equipment": {uid: dict(sorted(hero.equipment.items()))
                          for uid, hero in sorted(progress.heroes.items())},
            "wounds": {uid: list(hero.wounds)
                       for uid, hero in sorted(progress.heroes.items())},
            "completed": list(progress.completed),
            "unlocked": list(progress.unlocked),
            "story_flags": deepcopy(progress.story_flags),
        })
        if outcome["result"] != "victory":
            break
    require(content.to_dict() == authored, "Campaign curve modified Content")
    return {"kind": "r6_campaign_balance", "schema": SCHEMA,
            "missions": list(missions), "seeds": list(seeds),
            "rows": rows, "finished_all": len(rows) == len(missions)
            and all(r["status"] == "victory" for r in rows),
            "starting_campaign": asdict(campaign),
            "ending_campaign": asdict(progress),
            "note": "Budget ratio is a design proxy, not a measured difficulty",
            "human_minutes": None}


def campaign_curve_review(report, *, max_budget_jump=.5):
    """Flag pacing discontinuities for designer review, not fake human gates."""
    require(type(report) is dict and report.get("kind") == "r6_campaign_balance"
            and report.get("schema") == SCHEMA, "Invalid campaign balance curve")
    require(type(max_budget_jump) in (int, float) and 0 <= max_budget_jump <= 10,
            "Invalid jump threshold")
    warnings = []
    last = None
    for row in report["rows"]:
        if row["status"] not in ("victory", "defeat", "draw", "limit"):
            warnings.append(row["mission"] + ": mission unavailable")
            break
        ratio = row["enemy_to_player_budget"]
        if last is not None and ratio - last > max_budget_jump:
            warnings.append(row["mission"] + ": enemy budget spike")
        if row["status"] != "victory":
            warnings.append(row["mission"] + ": campaign blocked by " + row["status"])
        last = ratio
    return {"review_required": bool(warnings), "warnings": warnings,
            "replay_verified": all(row.get("replay_verified", False)
                                   for row in report["rows"] if row["status"] != "locked")}

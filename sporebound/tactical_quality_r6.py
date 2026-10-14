"""R6.15 Tactical Quality: one-command counterfactual evidence, not AI scoring.

All alternatives execute against cloned canonical Battle states. These probes
are limited to IMMEDIATE observable effects: a guard posture is preparation,
not prevented damage; one command cannot prove a winning strategy.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from .ai import simulate
from .battle_lab import _fingerprint
from .encounter_balance6 import human_variant_breakdown
from .engine import Battle
from .model import Content, distance, require
from .tactical_choice_lab_r6 import available_tactical_choices

SCHEMA = 1
MAX_QUALITY_SAMPLES = 16
MAX_QUALITY_COMMANDS = 5000
# Direction: positive means better (at this instant). Do not sum across metrics
# or rank commands by a fabricated universal "tactical quality" score.
BENEFITS = (
    "enemy_hp_removed", "ally_hp_restored", "cover_gain",
    "hazard_reduction", "goal_distance_reduction", "prepared_added",
    "objective_hold_gain")
COSTS = ("ally_hp_lost", "mp_spent", "consumables_spent")
METRICS = (*BENEFITS, *COSTS)
SIGNOFF_FIELDS = ("positioning", "protection", "resources",
                  "objectives", "player_comprehension")


def _snapshot(battle, actor_id, team):
    """Comparable battlefield features; never infer future AI reactions."""
    actor = battle.unit(actor_id)
    friend = {u.id: (u.hp, u.mp) for u in battle.units if u.team == team}
    hostile = {u.id: u.hp for u in battle.units if u.team != team}
    goals = battle.mission.goal
    pos = actor.pos
    return {
        "friend": friend, "hostile": hostile,
        "inventory": deepcopy(battle.inventory[team]),
        "cover": battle.board.tile(pos).cover,
        "hazard": battle.board.tile(pos).hazard,
        "goal_distance": (min(distance(pos, goal) for goal in goals)
                          if goals else None),
        "prepared": len(battle.prepared_reactions),
        "hold_ticks": battle.hold_ticks,
    }


def _delta(before, after):
    damage = sum(max(0, hp - after["hostile"].get(uid, 0))
                 for uid, hp in before["hostile"].items())
    healing = sum(max(0, after["friend"].get(uid, (0, 0))[0] - hp)
                  for uid, (hp, _) in before["friend"].items())
    loss = sum(max(0, hp - after["friend"].get(uid, (0, 0))[0])
               for uid, (hp, _) in before["friend"].items())
    mp = sum(max(0, old_mp - after["friend"].get(uid, (0, 0))[1])
             for uid, (_, old_mp) in before["friend"].items())
    items = sum(max(0, count - after["inventory"].get(item, 0))
                for item, count in before["inventory"].items())
    goal_delta = (
        before["goal_distance"] - after["goal_distance"]
        if before["goal_distance"] is not None and
        after["goal_distance"] is not None else 0)
    return {
        "enemy_hp_removed": damage,
        "ally_hp_restored": healing,
        "ally_hp_lost": loss,
        "mp_spent": mp,
        "consumables_spent": items,
        "cover_gain": after["cover"] - before["cover"],
        "hazard_reduction": before["hazard"] - after["hazard"],
        "goal_distance_reduction": goal_delta,
        "prepared_added": max(0, after["prepared"] - before["prepared"]),
        "objective_hold_gain": after["hold_ticks"] - before["hold_ticks"],
    }


def immediate_effect(battle, command, *, actor_id=None):
    """Execute a single legitimate command against an independent Battle.

    The output is a local observation, not a turn-normalized or risk-adjusted
    benefit. Random effects are reproducible within a fixed starting RNG state.
    """
    require(not battle.deploying and battle.active is not None
            and not battle.result, "A tactical activation is required")
    actor = battle.active
    if actor_id is not None:
        require(actor.id == actor_id, "Tactical actor mismatch")
    initial = _snapshot(battle, actor.id, actor.team)
    sandbox = deepcopy(battle)
    events_before = len(sandbox.events)
    sandbox.execute(deepcopy(command))
    final = _snapshot(sandbox, actor.id, actor.team)
    return {
        "metrics": _delta(initial, final),
        "event_kinds": dict(sorted(Counter(
            row["kind"] for row in sandbox.events[events_before:]).items())),
        "result_after_one_command": sandbox.result,
    }


def _oriented(metrics):
    return tuple(metrics[key] for key in BENEFITS) + tuple(
        -metrics[key] for key in COSTS)


def _tradeoff(left, right):
    """Neither option is universally superior among observed dimensions."""
    diff = [a - b for a, b in zip(_oriented(left), _oriented(right))]
    return any(v > 0 for v in diff) and any(v < 0 for v in diff)


def measure_decision(battle, chosen):
    """Side-by-side chosen command and at most five legal alternatives."""
    options = available_tactical_choices(battle)
    require(options["sampled"] and options["team"] == "player",
            "Quality measurement requires a player activation")
    before_digest = battle.digest()
    original_commands = len(battle.commands)
    candidate_rows = []
    seen_commands = set()
    for option in options["options"]:
        # Duplicate chosen commands still appear once, with their category.
        command = option["command"]
        key = _fingerprint(command)
        if key in seen_commands:
            continue
        seen_commands.add(key)
        candidate_rows.append({
            "category": option["category"], "reason": option["reason"],
            "command": deepcopy(command),
            "immediate": immediate_effect(battle, command,
                                         actor_id=options["actor"])})
    chosen_effect = immediate_effect(battle, chosen,
                                     actor_id=options["actor"])
    impacts = [row["immediate"]["metrics"] for row in candidate_rows]
    signatures = {tuple(impact[key] for key in METRICS) for impact in impacts}
    contrasting = len(signatures) > 1
    tradeoffs = []
    for i, left in enumerate(candidate_rows):
        for right in candidate_rows[i + 1:]:
            if _tradeoff(left["immediate"]["metrics"],
                         right["immediate"]["metrics"]):
                tradeoffs.append({
                    "categories": sorted((left["category"], right["category"])),
                    "commands": [left["command"], right["command"]]})
    require(battle.digest() == before_digest
            and len(battle.commands) == original_commands,
            "Quality instrumentation changed Battle")
    return {
        "actor": options["actor"], "team": "player",
        "chosen": deepcopy(chosen), "chosen_immediate": chosen_effect,
        "alternatives": candidate_rows,
        "category_count": len({row["category"] for row in candidate_rows}),
        "distinct_immediate_footprints": len(signatures),
        "has_differentiation": contrasting,
        "tradeoffs": tradeoffs,
        "note": "One-command effects; selected AI action may not be among sampled options",
    }


def evaluate_quality_gate(report, *, min_decisions=1,
                          min_differentiated=1, min_tradeoffs=0):
    """Coverage policy only. Human approval is a separate mandatory gate."""
    require(type(report) is dict and report.get("kind") == "tactical_quality_r6"
            and report.get("schema") == SCHEMA
            and report.get("replay_verified") is True
            and type(report.get("decisions")) is list,
            "Expected replay-verified R6.15 quality evidence")
    require(all(type(value) is int and value >= 0 for value in (
            min_decisions, min_differentiated, min_tradeoffs))
            and min_decisions >= 1,
            "Invalid quality gate policy")
    decisions = report["decisions"]
    distinct = sum(bool(row["has_differentiation"]) for row in decisions)
    tradeoffs = sum(bool(row["tradeoffs"]) for row in decisions)
    issues = []
    if len(decisions) < min_decisions:
        issues.append("Insufficient sampled player decisions")
    if distinct < min_differentiated:
        issues.append("Insufficient observable immediate differences")
    if tradeoffs < min_tradeoffs:
        issues.append("Insufficient observable tradeoff states")
    return {
        "kind": "tactical_quality_gate_r6", "passed": not issues,
        "status": "pass" if not issues else "fail",
        "issues": issues, "sampled_player_decisions": len(decisions),
        "differentiated_states": distinct, "tradeoff_states": tradeoffs,
        "limits": "Local immediate outcomes do not establish strategy or fun",
    }


def run_quality_lab(content, mission_id, *, seed=1, max_commands=120,
                    max_samples=8, sample_stride=3, rules=None,
                    initial_state=None):
    """Run the real AI once; only selected player states are probed."""
    require(isinstance(content, Content) and mission_id in content.missions,
            "Unknown tactical quality mission")
    require(type(seed) is int and 0 <= seed < 2**32
            and type(max_commands) is int
            and 1 <= max_commands <= MAX_QUALITY_COMMANDS
            and type(max_samples) is int and 1 <= max_samples <= MAX_QUALITY_SAMPLES
            and type(sample_stride) is int and 1 <= sample_stride <= 64,
            "Invalid R6.15 sampling bounds")
    require(initial_state is None or type(initial_state) is dict,
            "Invalid initial tactical state")
    content_hash = _fingerprint(content.to_dict())
    battle = Battle(content, mission_id, seed=seed, rules=rules,
                    initial_state=initial_state)
    decisions = []
    count = 0

    def observe(state, command):
        nonlocal count
        if state.deploying or state.active is None or state.active.team != "player":
            return
        count += 1
        if len(decisions) >= max_samples or (count - 1) % sample_stride:
            return
        evidence = measure_decision(state, command)
        decisions.append({**evidence, "command_index": len(state.commands),
                          "ct_tick": state.tick})

    simulation = simulate(battle, max_commands=max_commands, observer=observe)
    replay = Battle.replay(battle.recording(), rules=battle.rules)
    require(replay.digest() == simulation["digest"]
            and _fingerprint(content.to_dict()) == content_hash,
            "Quality probe changed replay or authored content")
    report = {
        "kind": "tactical_quality_r6", "schema": SCHEMA,
        "mission": mission_id, "seed": seed, "max_commands": max_commands,
        "max_samples": max_samples, "sample_stride": sample_stride,
        "content_sha256": content_hash,
        "context_sha256": _fingerprint(initial_state),
        "rules_manifest": battle.rules.manifest(),
        "replay_verified": True, "digest": simulation["digest"],
        "commands": simulation["commands"], "ticks_ct": simulation["ticks"],
        "result": simulation["result"], "observed_player_commands": count,
        "decisions": decisions,
    }
    report["automated_gate"] = evaluate_quality_gate(report)
    return report


def release_quality_review(report, human_report=None, *, annotations=(),
                           variant="authored", min_complete=5,
                           human_signoff=None, min_tradeoffs=1):
    """Fail closed: automated probes alone never certify the human design gate.

    An explicit, anonymous design-review signoff plus at least min_complete
    full human observations for the matching mission and variant are required.
    """
    automated = evaluate_quality_gate(
        report, min_decisions=1, min_differentiated=1,
        min_tradeoffs=min_tradeoffs)
    require(type(variant) is str and variant and len(variant) <= 64
            and type(min_complete) is int and min_complete >= 1,
            "Invalid human review scope")
    if human_signoff is not None:
        require(type(human_signoff) is dict
                and set(human_signoff) == set(SIGNOFF_FIELDS)
                and all(type(v) is bool for v in human_signoff.values()),
                "Human signoff requires five explicit design checkboxes")
    matched = None
    issues = list(automated["issues"])
    human_hash_matches = None
    if human_report is None:
        issues.append("Missing opt-in human playtest report")
    else:
        report_content = human_report.get("content_sha256")
        human_hash_matches = (
            report_content == report.get("content_sha256")
            if report_content is not None else None)
        if human_hash_matches is not True:
            issues.append("Missing or mismatched authored content fingerprint")
        analysis = human_variant_breakdown(
            human_report, annotations, min_complete=min_complete)
        matched = next((row for row in analysis["groups"]
                        if row["mission"] == report["mission"]
                        and row["variant"] == variant), None)
        if matched is None or not matched["sample_sufficient"]:
            issues.append("Insufficient full human playtest observations")
        elif matched["duration_target_15_30_minutes"] is not True:
            issues.append("Human median duration outside 15-30 minute target")
        if matched is not None and matched["confusion"]:
            issues.append("Human confusion signals require review")
    if human_signoff is None or not all(human_signoff.values()):
        issues.append("Explicit human tactical design signoff incomplete")
    return {
        "kind": "r6_15_release_review", "status": "pass" if not issues else "pending",
        "passed": not issues, "issues": sorted(set(issues)),
        "automated": automated, "mission": report["mission"],
        "variant": variant, "human_fingerprint_matches": human_hash_matches,
        "human": matched,
        "signoff": deepcopy(human_signoff),
        "note": "Human judgment and evidence are required; not an automatic balance claim",
    }

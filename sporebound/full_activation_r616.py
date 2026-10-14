"""R6.16 — bounded counterfactual *complete activations* via canonical Battle.

Contrasts what can actually be combined in one CT activation: Move -> Act ->
End, Act -> Move -> End, defense, consumables and objective interactions.
No alternate gameplay engine, no forecast-only legality or new save format.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from .ai import choose_command, simulate
from .battle_lab import _fingerprint
from .engine import Battle
from .model import Content, RuleError, distance, require
from .tactical_choice_lab_r6 import available_tactical_choices
from .tactical_quality_r6 import _snapshot, _delta, _oriented

SCHEMA = 1
MAX_PLANS = 12
MAX_ACTIVATION_COMMANDS = 5
MAX_SAMPLES = 6


def _end(battle, uid):
    return {"kind": "end", "facing": list(battle.unit(uid).facing)}


def execute_activation(battle, commands, *, ai_continuation=False):
    """One activation from a common pre-state, with a fixed RNG clone.

    Explicit plans always end with 'end', unless the canonical battle reaches
    a terminal outcome before that point. The reference AI continuation uses
    its real dynamic decisions until that very same activation boundary.
    Invalid/incomplete plans raise RuleError and cannot count as options.
    """
    require(not battle.deploying and battle.active is not None
            and not battle.result and battle.active.team == "player",
            "R6.16 requires an active player unit")
    require(type(commands) is list and len(commands) <= MAX_ACTIVATION_COMMANDS
            and (ai_continuation or bool(commands)),
            "R6.16 plan is missing or exceeds the activation budget")
    require(not ai_continuation or not commands,
            "Reference AI path must choose its own commands")
    actor = battle.active
    initial = _snapshot(battle, actor.id, actor.team)
    replica = deepcopy(battle)
    start_events = len(replica.events)
    steps = []
    for index in range(MAX_ACTIVATION_COMMANDS):
        if replica.result:
            break
        require(replica.active_id == actor.id,
                "The activation changed before the plan finished")
        if ai_continuation:
            command = choose_command(replica)
        else:
            require(index < len(commands), "Activation did not reach End")
            command = commands[index]
        require(isinstance(command, dict), "Invalid activation command")
        before = len(replica.commands)
        replica.execute(deepcopy(command))
        require(len(replica.commands) == before + 1, "Uncommitted activation command")
        steps.append(deepcopy(command))
        if replica.result or replica.active_id != actor.id:
            break
    require(replica.result or replica.active_id != actor.id,
            "Incomplete tactical activation")
    require(ai_continuation or replica.result or
            (steps and steps[-1].get("kind") == "end"),
            "Explicit activation did not finish with End")
    events = replica.events[start_events:]
    end_events = [row for row in events if row["kind"] == "end_turn"
                  and row["unit"] == actor.id]
    cost = end_events[-1]["cost"] if end_events else None
    after = _snapshot(replica, actor.id, actor.team)
    return {
        "commands": steps,
        "metrics": _delta(initial, after),
        "ct_end_cost": cost,  # null if terminal victory/defeat skipped End
        "actor_position": list(replica.unit(actor.id).pos),
        "actor_alive": replica.unit(actor.id).alive,
        "result": replica.result,
        "event_kinds": dict(sorted(Counter(
            row["kind"] for row in events).items())),
        "end_committed": bool(end_events),
        "commands_committed": len(steps),
    }


def _first_actions(battle):
    options = available_tactical_choices(battle)
    return [row for row in options["options"]
            if row["category"] != "positioning"
            and row["command"].get("kind") not in {"move", "end"}]


def _move_candidates(battle):
    """Select a bounded representative cover, objective and approach move."""
    if "move" not in battle.rules.commands or battle.active.moved:
        return []
    actor = battle.active
    reachable = battle.reachable(actor)
    cells = [cell for cell in reachable if cell != actor.pos]
    enemies = [u.pos for u in battle.units
               if u.alive and u.team != actor.team]
    goals = list(battle.mission.goal)
    candidates = []
    for sort_key in (
        lambda cell: (-battle.board.tile(cell).cover,
                      battle.board.tile(cell).hazard, cell),
        lambda cell: (min((distance(cell, g) for g in goals), default=0),
                      battle.board.tile(cell).hazard, cell),
        lambda cell: (min((distance(cell, pos) for pos in enemies), default=0),
                      battle.board.tile(cell).hazard, cell),
    ):
        if not cells:
            break
        selected = min(cells, key=sort_key)
        if selected not in candidates:
            candidates.append(selected)
    return [{"kind": "move", "cell": list(cell)} for cell in candidates]


def sample_activation_plans(battle):
    """Generated bounded plans are executed, never accepted via prediction."""
    require(not battle.deploying and battle.active is not None
            and battle.active.team == "player" and not battle.result,
            "R6.16 needs a tactical player activation")
    actor_id = battle.active.id
    cases, seen = [], set()

    def attempt(label, commands, *, reference=False):
        if len(cases) >= MAX_PLANS:
            return
        key = _fingerprint(commands) if not reference else "reference"
        if key in seen:
            return
        seen.add(key)
        try:
            evidence = execute_activation(battle, commands,
                                          ai_continuation=reference)
        except RuleError:
            return
        cases.append({"label": label, "reference": reference, **evidence})

    attempt("AI reference activation", [], reference=True)
    attempt("End without acting", [_end(battle, actor_id)])
    move_starts = _move_candidates(battle)
    actions = _first_actions(battle)
    for row in actions:
        if len(cases) >= MAX_PLANS:
            break
        action = row["command"]
        attempt(row["category"] + " then End",
                [action, _end(battle, actor_id)])
    for movement in move_starts:
        if len(cases) >= MAX_PLANS:
            break
        attempt("Move then End", [movement, _end(battle, actor_id)])
        # After moving, the canonical actor can expose new attacks, heals or
        # interactions. Probe the changed state rather than reuse stale ranges.
        try:
            mid = deepcopy(battle)
            mid.execute(deepcopy(movement))
            if mid.result or mid.active_id != actor_id:
                continue
            later = _first_actions(mid)
            for row in later[:3]:
                if len(cases) >= MAX_PLANS:
                    break
                attempt("Move then " + row["category"] + " then End",
                        [movement, row["command"], _end(mid, actor_id)])
        except RuleError:
            continue
    # Attack -> Move can be legal and tactically different from Move -> Attack.
    # Sample one such order if the activation budget still permits.
    for row in actions[:2]:
        if len(cases) >= MAX_PLANS:
            break
        try:
            mid = deepcopy(battle)
            mid.execute(deepcopy(row["command"]))
            if mid.result or mid.active_id != actor_id:
                continue
            for movement in _move_candidates(mid)[:1]:
                attempt(row["category"] + " then Move then End",
                        [row["command"], movement, _end(mid, actor_id)])
        except RuleError:
            continue
    require(bool(cases) and cases[0]["reference"], "No valid activation evidence")
    return cases


def _dominance(left, right):
    """Pareto direction, including *actual end-turn* CT cost."""
    if left["ct_end_cost"] is None or right["ct_end_cost"] is None:
        return False
    l = (*_oriented(left["metrics"]), -left["ct_end_cost"])
    r = (*_oriented(right["metrics"]), -right["ct_end_cost"])
    return all(a >= b for a, b in zip(l, r)) and any(
        a > b for a, b in zip(l, r))


def evaluate_activation_state(battle):
    """Compare entire feasible activations at one pre-state; no battle edits."""
    original = battle.digest()
    before_record = deepcopy(battle.recording())
    plans = sample_activation_plans(battle)
    signatures = {
        (tuple(plan["metrics"][metric] for metric in sorted(plan["metrics"])),
         plan["ct_end_cost"], plan["result"], tuple(plan["actor_position"]))
        for plan in plans
    }
    # Terminal results cannot be fairly collapsed into a damage/CT score.
    comparable = [p for p in plans if p["result"] is None
                  and p["ct_end_cost"] is not None]
    frontier = [
        p["label"] for p in comparable
        if not any(other is not p and _dominance(other, p)
                   for other in comparable)
    ]
    pairs = sum(
        1 for i, first in enumerate(comparable)
        for second in comparable[i + 1:]
        if not _dominance(first, second)
        and not _dominance(second, first)
        and (first["metrics"] != second["metrics"] or
             first["ct_end_cost"] != second["ct_end_cost"]))
    require(battle.digest() == original and battle.recording() == before_record,
            "R6.16 observer modified canonical Battle")
    return {
        "actor": battle.active_id, "team": "player",
        "plans": plans, "plan_count": len(plans),
        "distinct_full_activation_footprints": len(signatures),
        "has_distinct_full_activations": len(signatures) >= 2,
        "pareto_frontier_labels": frontier,
        "non_dominated_pairs": pairs,
        "terminal_plan_count": sum(p["result"] is not None for p in plans),
        "warnings": [
            "No future enemy actions simulated; only the next full activation",
            "Non-dominated local outcomes are not a human strategy ranking",
        ],
    }


def evaluate_activation_gate(report, *, min_samples=1,
                             min_distinct=1, min_non_dominated=0):
    require(type(report) is dict and report.get("kind") == "full_activation_r6"
            and report.get("schema") == SCHEMA
            and report.get("replay_verified") is True
            and type(report.get("decisions")) is list,
            "R6.16 gate requires replay-verified evidence")
    require(all(type(v) is int and v >= 0 for v in (
                min_samples, min_distinct, min_non_dominated))
            and min_samples >= 1, "Invalid R6.16 thresholds")
    count = sum(bool(row["has_distinct_full_activations"])
                for row in report["decisions"])
    tradeoffs = sum(row["non_dominated_pairs"] > 0
                    for row in report["decisions"])
    issues = []
    if len(report["decisions"]) < min_samples:
        issues.append("Insufficient fully observed player activations")
    if count < min_distinct:
        issues.append("Too few distinct complete activation outcomes")
    if tradeoffs < min_non_dominated:
        issues.append("No required non-dominated full-turn choices")
    return {"kind": "r6_16_full_activation_gate",
            "passed": not issues,
            "status": "pass" if not issues else "fail",
            "sampled_activations": len(report["decisions"]),
            "states_with_distinct_turns": count,
            "states_with_non_dominated_pairs": tradeoffs,
            "issues": issues,
            "limits": "Bounded single-activation comparisons; not human-tested strategy"}


def run_activation_lab(content, mission_id, *, seed=1, max_commands=120,
                       max_samples=3, sample_stride=2, rules=None,
                       initial_state=None):
    require(isinstance(content, Content) and mission_id in content.missions,
            "Unknown R6.16 mission")
    require(type(seed) is int and 0 <= seed < 2**32
            and type(max_commands) is int and 1 <= max_commands <= 5000
            and type(max_samples) is int and 1 <= max_samples <= MAX_SAMPLES
            and type(sample_stride) is int and 1 <= sample_stride <= 64,
            "Invalid full-activation lab budgets")
    require(initial_state is None or type(initial_state) is dict,
            "Invalid initial full-activation state")
    content_sha = _fingerprint(content.to_dict())
    battle = Battle(content, mission_id, seed=seed, rules=rules,
                    initial_state=initial_state)
    decisions, observed, visited = [], 0, set()

    def observe(state, command):
        nonlocal observed
        actor = state.active
        if (state.deploying or actor is None or
                actor.team != "player"):
            return
        # First observed command of each activation only: a unit can move and
        # attack in one turn; counting each prefix would bias the sample.
        activation = sum(event["kind"] == "activation" for event in state.events)
        key = (activation, actor.id)
        if key in visited:
            return
        visited.add(key)
        observed += 1
        if len(decisions) >= max_samples or (observed - 1) % sample_stride:
            return
        evidence = evaluate_activation_state(state)
        decisions.append({**evidence, "ct_tick": state.tick,
                          "command_index": len(state.commands),
                          "chosen_first_command": deepcopy(command)})

    outcome = simulate(battle, max_commands=max_commands, observer=observe)
    replay = Battle.replay(battle.recording(), rules=battle.rules)
    require(replay.digest() == outcome["digest"]
            and content_sha == _fingerprint(content.to_dict()),
            "Full-activation instrumentation changed replay or content")
    report = {
        "kind": "full_activation_r6", "schema": SCHEMA,
        "mission": mission_id, "seed": seed,
        "max_commands": max_commands, "max_samples": max_samples,
        "sample_stride": sample_stride,
        "context_sha256": _fingerprint(initial_state),
        "content_sha256": content_sha, "rules_manifest": battle.rules.manifest(),
        "replay_verified": True, "result": outcome["result"],
        "commands": outcome["commands"], "ticks_ct": outcome["ticks"],
        "digest": outcome["digest"],
        "observed_player_activations": observed,
        "decisions": decisions,
    }
    report["gate"] = evaluate_activation_gate(report)
    return report

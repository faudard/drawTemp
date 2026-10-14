"""R6.14 — representative, executable tactical alternatives in real Battle states.

This is bounded sampling, not a solver or proof of optimal play. The canonical
Battle is NEVER mutated by the probes: each candidate uses an isolated copy
and the same Battle.execute legality rules used by Player and AI.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from .ai import simulate
from .battle_lab import _fingerprint
from .engine import Battle
from .model import Content, RuleError, distance, require

SCHEMA = 1
CATEGORIES = ("positioning", "damage", "protection", "resources", "objective")
MAX_SAMPLES = 24
MAX_CANDIDATES = 30


def _legal(battle, command):
    """No hypothetical command is recorded as available without execution."""
    try:
        replica = deepcopy(battle)
        replica.execute(deepcopy(command))
        return True
    except RuleError:
        return False


def available_tactical_choices(battle):
    """Find representative meaningful categories, not enumerate the full tree.

    'Positioning' needs an actual position change and a different tactical
    property (cover, hazard, enemy/goal distance). 'Damage' requires a
    positive-chance engine forecast. 'Protection' and 'resources' must pass
    Battle.execute. UI/deployment states never count as tactical decisions.
    """
    actor = battle.active
    if battle.result or battle.deploying or actor is None:
        return {"actor": None, "team": None, "options": [],
                "categories": [], "sampled": False}
    options, tested = [], 0
    enemies = sorted(
        (u for u in battle.units if u.alive and u.team != actor.team),
        key=lambda u: (distance(actor.pos, u.pos), u.id))
    allies = sorted((u for u in battle.units if u.team == actor.team),
                    key=lambda u: u.id)
    goals = list(battle.mission.goal)

    def add(category, command, why):
        nonlocal tested
        if tested >= MAX_CANDIDATES:
            return False
        tested += 1
        if _legal(battle, command):
            options.append({"category": category, "command": command,
                            "reason": why})
            return True
        return False

    if "move" in battle.rules.commands and not actor.moved:
        reachable = battle.reachable(actor)
        start = actor.pos
        nearest = lambda cell: min((distance(cell, other.pos)
                                    for other in enemies), default=0)
        goal_distance = lambda cell: min((distance(cell, goal)
                                         for goal in goals), default=0)
        baseline = (battle.board.tile(start).cover,
                    battle.board.tile(start).hazard,
                    nearest(start), goal_distance(start))
        moves = sorted(
            (cell for cell in reachable if cell != start),
            key=lambda cell: (
                -battle.board.tile(cell).cover,
                battle.board.tile(cell).hazard,
                goal_distance(cell), nearest(cell), cell))
        movement_reasons = set()
        for cell in moves:
            if tested >= 12 or len(movement_reasons) >= 3:
                break
            now = (battle.board.tile(cell).cover,
                   battle.board.tile(cell).hazard,
                   nearest(cell), goal_distance(cell))
            changed = [name for i, name in enumerate(
                ("cover", "hazard", "enemy_distance", "goal_distance"))
                if baseline[i] != now[i]]
            if not changed:
                continue
            kind = changed[0]
            if kind in movement_reasons:
                continue
            if add("positioning", {"kind": "move", "cell": list(cell)},
                   "changed " + kind):
                movement_reasons.add(kind)

    if ("act" in battle.rules.commands and not actor.acted
            and not battle.status_blocks(actor, "act")):
        for target in enemies[:4]:
            if tested >= MAX_CANDIDATES:
                break
            # Forecasts are observations; only executable commands count.
            try:
                forecast = battle.forecast("attack", target.pos, actor)
            except RuleError:
                continue
            if any(row.get("kind") == "damage" and row.get("amount", 0) > 0
                   and row.get("chance", 0) > 0 for row in forecast):
                if add("damage", {"kind": "act", "skill": "attack",
                                  "cell": list(target.pos)},
                       "positive-chance attack forecast"):
                    break
        for skill_id in actor.skills[:8]:
            if tested >= MAX_CANDIDATES:
                break
            try:
                skill = battle._skill(actor, skill_id)
            except RuleError:
                continue
            healing = any(e.kind in ("heal", "revive", "cleanse")
                          for e in skill.effects)
            expensive = skill.cost > 0
            if not healing and not expensive:
                continue
            for target in (allies if healing else enemies)[:4]:
                try:
                    forecast = battle.forecast(skill_id, target.pos, actor)
                except RuleError:
                    continue
                if not forecast:
                    continue
                if healing and not any(
                        (row.get("kind") == "heal"
                         and target.hp < target.max_hp) or
                        (row.get("kind") == "revive" and not target.alive) or
                        (row.get("kind") == "cleanse"
                         and bool(target.statuses)) for row in forecast):
                    continue
                category = "resources" if expensive else "protection"
                if add(category, {"kind": "act", "skill": skill_id,
                                  "cell": list(target.pos)},
                       "support skill" if healing else "MP-consuming attack"):
                    break

    if ("prepare" in battle.rules.commands and not actor.acted
            and not battle.status_blocks(actor, "act")):
        for mode in ("guard", "overwatch"):
            relevant = bool(enemies) and (
                mode == "overwatch" or
                any(distance(actor.pos, other.pos) <=
                    battle.movement_budget(actor) + battle.engagement_range(actor)
                    for other in enemies))
            if relevant and mode in battle.rules.preparations:
                if add("protection", {"kind": "prepare", "mode": mode},
                       "real guard/overwatch preparation with an enemy"):
                    break

    if ("item" in battle.rules.commands and not actor.acted
            and not battle.status_blocks(actor, "act")):
        inventory = battle.inventory[actor.team]
        for target in allies:
            if distance(actor.pos, target.pos) > 1:
                continue
            choices = (
                ("potion", target.alive and target.hp < target.max_hp),
                ("ether", target.alive and target.mp < target.max_mp),
                ("phoenix", not target.alive))
            for item, relevant in choices:
                if relevant and inventory.get(item, 0) > 0 and add(
                        "resources",
                        {"kind": "item", "item": item, "cell": list(target.pos)},
                        "meaningful consumable use"):
                    break
            if any(row["category"] == "resources" for row in options):
                break

    if ("interact" in battle.rules.commands and not actor.acted
            and not battle.status_blocks(actor, "act")):
        for obj in battle.mission.objects[:16]:
            if tested >= MAX_CANDIDATES:
                break
            if distance(actor.pos, tuple(obj.get("pos", (999, 999)))) <= 1:
                if add("objective", {"kind": "interact", "object": obj["id"]},
                       "available object interaction"):
                    break

    # Keep one representative option per category in the public report.
    seen, selected = set(), []
    for option in options:
        if option["category"] not in seen:
            seen.add(option["category"])
            selected.append(option)
    return {"actor": actor.id, "team": actor.team, "sampled": True,
            "categories": sorted(seen), "options": selected,
            "probes_executed": tested}


def evaluate_choice_gate(report, *, min_decisions=1, min_multi=1,
                         required_pairs=()):
    """Explicit quality gate: zero samples or missing choices cannot pass.

    This gate proves observable legal alternatives only. Human judgment still
    decides whether choices are understandable and strategically balanced.
    """
    require(type(report) is dict and report.get("kind") == "tactical_choices_r6"
            and report.get("schema") == SCHEMA
            and report.get("replay_verified") is True
            and type(report.get("decisions")) is list,
            "Choice gate requires verified R6 choice evidence")
    require(type(min_decisions) is int and min_decisions >= 1
            and type(min_multi) is int and min_multi >= 0,
            "Invalid tactical coverage threshold")
    require(type(required_pairs) in (tuple, list) and
            len(set(required_pairs)) == len(required_pairs)
            and set(required_pairs) <= {
                "positioning+damage", "positioning+protection",
                "positioning+resources", "positioning+objective"},
            "Invalid required tactical opportunity pairs")
    pairs = Counter()
    multi = 0
    all_categories = Counter()
    for row in report["decisions"]:
        cats = set(row["categories"])
        require(cats <= set(CATEGORIES) and row["team"] == "player"
                and row["sampled"] is True, "Untrusted choice evidence")
        all_categories.update(cats)
        multi += len(cats) >= 2
        for category in ("damage", "protection", "resources", "objective"):
            if "positioning" in cats and category in cats:
                pairs["positioning+" + category] += 1
    issues = []
    if len(report["decisions"]) < min_decisions:
        issues.append("Too few sampled player decisions")
    if multi < min_multi:
        issues.append("Too few multi-category player decisions")
    for pair in required_pairs:
        if not pairs[pair]:
            issues.append("No executable alternative pair: " + pair)
    return {"kind": "r6_tactical_choice_gate", "passed": not issues,
            "status": "pass" if not issues else "fail", "issues": issues,
            "sampled_player_decisions": len(report["decisions"]),
            "multi_category_decisions": multi,
            "choice_categories": dict(sorted(all_categories.items())),
            "pair_occurrences": dict(sorted(pairs.items())),
            "limits": "Sampled legal alternatives, not exhaustive or human-tested strategy"}


def run_choice_lab(content, mission_id, *, seed=1, max_commands=120,
                   max_samples=12, sample_stride=2, rules=None,
                   initial_state=None):
    """Observe optional bounded actor choices, then replay the unmodified run."""
    require(isinstance(content, Content) and mission_id in content.missions,
            "Unknown tactical choice mission")
    require(type(seed) is int and 0 <= seed < 2**32
            and type(max_commands) is int and 1 <= max_commands <= 5000
            and type(max_samples) is int and 1 <= max_samples <= MAX_SAMPLES
            and type(sample_stride) is int and 1 <= sample_stride <= 64,
            "Invalid tactical choice run budget")
    require(initial_state is None or type(initial_state) is dict,
            "Invalid tactical choice initial state")
    fingerprint = _fingerprint(content.to_dict())
    battle = Battle(content, mission_id, seed=seed, rules=rules,
                    initial_state=initial_state)
    choices = []
    observed_player = 0

    def observe(state, command):
        nonlocal observed_player
        if state.deploying or state.active is None or state.active.team != "player":
            return
        observed_player += 1
        if len(choices) >= max_samples or (observed_player - 1) % sample_stride:
            return
        entry = available_tactical_choices(state)
        if entry["sampled"]:
            choices.append({**entry, "command_index": len(state.commands),
                            "chosen": deepcopy(command)})

    simulated = simulate(battle, max_commands=max_commands, observer=observe)
    verified = Battle.replay(battle.recording(), rules=battle.rules)
    require(verified.digest() == simulated["digest"],
            "Tactical choice instrumentation changed replay")
    require(_fingerprint(content.to_dict()) == fingerprint,
            "Tactical choice probe changed authored Content")
    report = {
        "kind": "tactical_choices_r6", "schema": SCHEMA,
        "mission": mission_id, "seed": seed, "max_commands": max_commands,
        "sample_stride": sample_stride, "max_samples": max_samples,
        "content_sha256": fingerprint, "rules_manifest": battle.rules.manifest(),
        "context_sha256": _fingerprint(initial_state),
        "result": simulated["result"], "commands": simulated["commands"],
        "ticks_ct": simulated["ticks"], "digest": simulated["digest"],
        "replay_verified": True, "observed_player_commands": observed_player,
        "decisions": choices,
    }
    report["gate"] = evaluate_choice_gate(report)
    return report


def compare_choice_reports(before, after, *, max_multi_rate_drop=.25):
    """Paired-seed, mission and sampling-policy regression of tactical options.

    Different authored Content is allowed and signalled. The comparison is
    descriptive; it does not pretend that snapshots from changed encounters
    denote equivalent tactical positions.
    """
    require(type(max_multi_rate_drop) in (float, int)
            and not isinstance(max_multi_rate_drop, bool)
            and 0 <= max_multi_rate_drop <= 1,
            "Invalid tactical coverage tolerance")
    old = evaluate_choice_gate(before, min_multi=0)
    new = evaluate_choice_gate(after, min_multi=0)
    require(all(before.get(key) == after.get(key) for key in (
                "mission", "seed", "max_commands", "sample_stride",
                "max_samples")), "Choice regression requires matching seed and scope")
    old_rate = (old["multi_category_decisions"] /
                max(1, old["sampled_player_decisions"]))
    new_rate = (new["multi_category_decisions"] /
                max(1, new["sampled_player_decisions"]))
    issues = []
    if old_rate - new_rate > max_multi_rate_drop:
        issues.append("Multi-category opportunities fell beyond tolerance")
    pairs_disappeared = sorted(
        key for key, count in old["pair_occurrences"].items()
        if count > 0 and not new["pair_occurrences"].get(key, 0))
    if pairs_disappeared:
        issues.append("Previously available tactical pair disappeared")
    changed = (before.get("content_sha256") != after.get("content_sha256") or
               before.get("rules_manifest") != after.get("rules_manifest") or
               before.get("context_sha256") != after.get("context_sha256"))
    if not changed and before.get("digest") != after.get("digest"):
        issues.append("Tactical choice replay determinism changed on identical inputs")
    return {
        "kind": "r6_choice_comparison", "status": "fail" if issues else "pass",
        "passed": not issues, "issues": issues,
        "authored_inputs_changed": changed,
        "multi_category_rate_before": round(old_rate, 4),
        "multi_category_rate_after": round(new_rate, 4),
        "pairs_disappeared": pairs_disappeared,
        "sampled_before": old["sampled_player_decisions"],
        "sampled_after": new["sampled_player_decisions"],
        "note": "Matched simulation seeds, not necessarily identical decision states",
    }

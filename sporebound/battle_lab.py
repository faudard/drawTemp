"""Battle Lab 3.8: reproducible, read-only telemetry around canonical Battle/AI.

Simulation, rules, objectives and replays remain owned by Battle and ai.simulate.
Ticks/commands are pacing proxies, never minutes of human play.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math

from .ai import simulate
from .balance3 import percentile
from .engine import Battle
from .model import require


SCHEMA = 1
DESIGN_TARGETS = {"player_units": [4, 6], "active_enemies": [5, 10],
                  "standard_minutes": [15, 30], "measured_in_playtests": False}


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _class(unit):
    for tag in unit.tags:
        if tag.startswith(("class:", "job:")):
            return tag.split(":", 1)[1]
    return unit.archetype or "weapon:" + unit.weapon


def _progress(battle):
    """Coarse signal of tactical progress, not a proof of a soft-lock."""
    return (tuple((u.id, u.hp, u.pos) for u in battle.units),
            tuple((o["id"], o.get("open"), o.get("hp"))
                  for o in battle.mission.objects),
            battle.hold_ticks, battle.carrier, battle.relic_pos,
            tuple(battle.fired))


def _totals(samples, key):
    total = Counter()
    for sample in samples:
        total.update(sample[key])
    return dict(sorted(total.items()))


def run_lab(content, mission_id, *, seeds=(1, 7, 42, 99),
            max_commands=500, rules=None, stall_window=30,
            progress=None, initial_state=None):
    """Measure fresh battles using the *existing* AI and execution pipeline.

    Input Content and rules are never modified. Replay checks detect divergence;
    the recorded digest is the final canonical Battle.state() digest.
    """
    require(mission_id in content.missions, "Unknown Battle Lab mission")
    require(isinstance(seeds, (tuple, list)) and 1 <= len(seeds) <= 1000
            and len(seeds) == len(set(seeds))
            and all(type(s) is int and 0 <= s < 2**32 for s in seeds),
            "Seeds must be unique unsigned 32-bit integers (1..1000)")
    require(type(max_commands) is int and 1 <= max_commands <= 100000,
            "Invalid Battle Lab command limit")
    require(type(stall_window) is int and 2 <= stall_window <= 100000,
            "Invalid inactivity window")
    # Campaign-dependent runs use exactly Campaign.prepare (hero levels,
    # jobs, equipment, recruits, morale, talents) and standard Battle setup.
    # Fresh deepcopy per seed is required: prepare may materialize hero data.
    if progress is not None:
        from .campaign import Campaign
        require(isinstance(progress, Campaign), "Battle Lab needs a campaign snapshot")
        require(mission_id in progress.unlocked,
                "Battle Lab campaign mission is locked")
    require(initial_state is None or isinstance(initial_state, dict),
            "Invalid Battle Lab initial state")
    context_hash = (_fingerprint({
        "progress": asdict(progress) if progress is not None else None,
        "initial_state": initial_state,
    }) if progress is not None or initial_state is not None else None)
    samples = []
    class_totals = defaultdict(lambda: {"alive": 0, "total": 0})
    for seed in seeds:
        battle = (deepcopy(progress).prepare(content, mission_id, seed=seed,
                                           ruleset=rules, initial_state=initial_state)
                  if progress is not None else
                  Battle(content, mission_id, seed=seed, rules=rules,
                         initial_state=initial_state))
        decisions = Counter()
        class_decisions = Counter()
        max_inactive = 0
        inactive = 0
        previous = None

        def observe(state, command):
            nonlocal previous, inactive, max_inactive
            actor = state.active
            kind = command["kind"]
            team = actor.team if actor else "deployment"
            label = _class(actor) if actor else "deployment"
            decisions[team + ":" + kind] += 1
            class_decisions[team + "/" + label + ":" + kind] += 1
            progress = _progress(state)
            inactive = inactive + 1 if progress == previous else 0
            max_inactive = max(max_inactive, inactive)
            previous = progress

        result = simulate(battle, max_commands=max_commands, observer=observe)
        replay = Battle.replay(battle.recording(), rules=rules)
        require(replay.digest() == result["digest"], "Battle Lab replay divergence")
        events = Counter(e["kind"] for e in battle.events)
        unit_info = {u.id: (u.team, _class(u)) for u in battle.units}
        damage = Counter()
        healing = Counter()
        reactions = Counter()
        for event in battle.events:
            kind = event["kind"]
            if kind == "damage":
                target = unit_info.get(event.get("unit"))
                source = unit_info.get(event.get("source"))
                if target:
                    damage["received:" + target[0]] += event["amount"]
                if source:
                    damage["dealt:" + source[0]] += event["amount"]
            elif kind == "heal":
                target = unit_info.get(event.get("unit"))
                if target:
                    healing[target[0]] += event["amount"]
            elif kind in {"prepared_triggered", "intercept", "counter",
                          "opportunity", "pursuit", "tactic"}:
                reactions[kind] += 1
        for unit in battle.units:
            key = unit.team + "/" + _class(unit)
            class_totals[key]["total"] += 1
            class_totals[key]["alive"] += int(unit.alive)
        sample = {
            "seed": seed, "result": result["result"], "ticks": result["ticks"],
            "initial_inventory": deepcopy(battle.initial_state.get("inventory",
                                               {"potion": 3, "ether": 2,
                                                "phoenix": 1})),
            "commands": result["commands"], "digest": result["digest"],
            "replay_verified": True,
            "activations_ct": events["activation"],
            "events": dict(sorted(events.items())),
            "decisions": dict(sorted(decisions.items())),
            "class_decisions": dict(sorted(class_decisions.items())),
            "damage": dict(sorted(damage.items())),
            "healing_received": dict(sorted(healing.items())),
            "reactions": dict(sorted(reactions.items())),
            "survival": {
                unit.team + "/" + _class(unit) + "/" + unit.id: bool(unit.alive)
                for unit in battle.units
            },
            "objective": {"kind": battle.mission.objective,
                          "hold_ticks": battle.hold_ticks,
                          "target_ticks": battle.mission.target_ticks,
                          "goal_occupied": any(u.alive and u.team == "player"
                                              and u.pos in battle.mission.goal
                                              for u in battle.units),
                          "achieved": result["result"] == "victory"},
            "longest_no_progress_commands": max_inactive,
            "possible_stall": result["result"] == "limit"
                              and max_inactive >= stall_window,
        }
        samples.append(sample)
    counts = Counter(s["result"] for s in samples)
    class_survival = {
        key: {**counts_for_class,
              "rate": round(counts_for_class["alive"] / counts_for_class["total"], 4)}
        for key, counts_for_class in sorted(class_totals.items())
    }
    return {
        "schema": SCHEMA, "kind": "battle_lab", "mission": mission_id,
        "content_sha256": _fingerprint(content.to_dict()),
        "rules_manifest": battle.rules.manifest(),
        **({"setup_sha256": context_hash,
            "contextual": True,
            "initial_inventory": deepcopy(samples[0]["initial_inventory"])}
           if context_hash is not None else {}),
        "seeds": list(seeds), "max_commands": max_commands,
        "design_targets": DESIGN_TARGETS.copy(),
        "runs": len(samples),
        "outcomes": {key: counts[key] for key in ("victory", "defeat", "draw", "limit")},
        "victory_rate": round(counts["victory"] / len(samples), 4),
        "ticks_p50": percentile([s["ticks"] for s in samples], 50),
        "ticks_p95": percentile([s["ticks"] for s in samples], 95),
        "ticks_p99": percentile([s["ticks"] for s in samples], 99),
        "commands_p50": percentile([s["commands"] for s in samples], 50),
        "commands_p95": percentile([s["commands"] for s in samples], 95),
        "commands_p99": percentile([s["commands"] for s in samples], 99),
        "activations_ct": sum(s["activations_ct"] for s in samples),
        "damage": _totals(samples, "damage"),
        "healing_received": _totals(samples, "healing_received"),
        "reactions": _totals(samples, "reactions"),
        "decisions": _totals(samples, "decisions"),
        "class_decisions": _totals(samples, "class_decisions"),
        "events": _totals(samples, "events"),
        "class_survival": class_survival,
        "possible_stalls": sum(s["possible_stall"] for s in samples),
        "samples": samples,
    }


def compare_reports(before, after, *, max_victory_drop=0.25,
                    max_p95_growth=0.30, max_new_limits=0):
    """Paired-seed gate. Comparison of differing content/rules is intentional."""
    for report in (before, after):
        require(isinstance(report, dict) and report.get("schema") == SCHEMA
                and report.get("kind") == "battle_lab"
                and isinstance(report.get("samples"), list)
                and len(report["samples"]) == len(report.get("seeds", []))
                and report.get("runs") == len(report["samples"])
                and report["runs"] > 0, "Invalid Battle Lab report")
    require(before["mission"] == after["mission"]
            and before["seeds"] == after["seeds"]
            and before["max_commands"] == after["max_commands"],
            "Comparison requires the same mission, ordered seeds and command cap")
    require(type(max_victory_drop) in (int, float)
            and math.isfinite(max_victory_drop) and 0 <= max_victory_drop <= 1,
            "Invalid victory rate tolerance")
    require(type(max_p95_growth) in (int, float)
            and math.isfinite(max_p95_growth) and max_p95_growth >= 0,
            "Invalid duration tolerance")
    require(type(max_new_limits) is int and max_new_limits >= 0,
            "Invalid unresolved encounter tolerance")
    issues = []
    win_delta = round(after["victory_rate"] - before["victory_rate"], 4)
    if win_delta < -max_victory_drop:
        issues.append("Victory rate dropped beyond tolerance")
    deltas = {"victory_rate": win_delta}
    for key in ("commands_p95", "ticks_p95"):
        old, new = before[key], after[key]
        growth = (new - old) / max(old, 1)
        deltas[key] = new - old
        deltas[key + "_growth"] = round(growth, 4)
        if growth > max_p95_growth:
            issues.append(key + " grew beyond tolerance")
    new_limits = after["outcomes"]["limit"] - before["outcomes"]["limit"]
    deltas["new_limits"] = new_limits
    if new_limits > max_new_limits:
        issues.append("New unresolved encounters beyond tolerance")
    changed = (before["content_sha256"] != after["content_sha256"]
               or before["rules_manifest"] != after["rules_manifest"]
               or before.get("setup_sha256") != after.get("setup_sha256"))
    paired = []
    for old, new in zip(before["samples"], after["samples"]):
        require(old["seed"] == new["seed"], "Paired seed mismatch")
        if not new.get("replay_verified"):
            issues.append("Replay not verified for seed " + str(new["seed"]))
        if not changed and old["digest"] != new["digest"]:
            issues.append("Determinism drift on identical inputs, seed "
                          + str(new["seed"]))
        paired.append({"seed": new["seed"], "before": old["result"],
                       "after": new["result"], "tick_delta": new["ticks"] - old["ticks"],
                       "command_delta": new["commands"] - old["commands"],
                       "digest_equal": old["digest"] == new["digest"]})
    return {"status": "fail" if issues else "pass",
            "passed": not issues, "issues": sorted(set(issues)),
            "mission": after["mission"], "paired_seeds": len(paired),
            "authored_inputs_changed": changed, "deltas": deltas, "pairs": paired}


def save_report(path, report):
    """Human-diffable JSON; no model, savegame or studio document mutation."""
    from pathlib import Path
    target = Path(path)
    target.write_text(json.dumps(report, sort_keys=True, indent=2,
                                 ensure_ascii=False) + "\n", encoding="utf-8")
    return target

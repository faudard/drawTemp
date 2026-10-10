"""Deterministic seed sweeps and bounded difficulty metrics (2.7.6)."""
from __future__ import annotations

from collections import Counter
import math

from .ai import simulate
from .engine import Battle
from .model import require


def percentile(values, percent):
    """Nearest-rank percentile; deterministic for every Python/OS combination."""
    require(bool(values) and 0 < percent <= 100, "Invalid percentile")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percent / 100) - 1)]


def evaluate(content, mission_id, *, seeds=(1, 7, 42, 99),
             max_commands=500, rules=None):
    """Execute independent battles: no RNG or progression shared across seeds."""
    require(mission_id in content.missions, "Unknown mission")
    require(isinstance(seeds, (tuple, list)) and bool(seeds)
            and len(seeds) <= 1000
            and all(type(s) is int and 0 <= s < 2**32 for s in seeds)
            and len(seeds) == len(set(seeds)), "Seeds must be unique 32-bit integers")
    require(type(max_commands) is int and 1 <= max_commands <= 100000,
            "Invalid command budget")
    samples = []
    total_events = Counter()
    total_tactics = Counter()
    for seed in seeds:
        battle = Battle(content, mission_id, seed=seed, rules=rules)
        result = simulate(battle, max_commands)
        player_units = [u for u in battle.units if u.team == "player"]
        unit_team = {u.id: u.team for u in battle.units}
        events = Counter(e["kind"] for e in battle.events)
        tactics = Counter(e["tactic"] for e in battle.events
                          if e["kind"] == "tactic")
        total_events.update(events)
        total_tactics.update(tactics)
        incoming = sum(e.get("amount", 0) for e in battle.events
                       if e["kind"] == "damage"
                       and unit_team.get(e["unit"]) == "player")
        samples.append({"seed": seed, "result": result["result"],
                        "ticks": result["ticks"], "commands": result["commands"],
                        "digest": result["digest"],
                        "allied_downed": sum(not u.alive for u in player_units),
                        "allied_count": len(player_units),
                        "damage_taken": incoming,
                        "events": dict(sorted(events.items())),
                        "tactics": dict(sorted(tactics.items()))})
    counts = Counter(s["result"] for s in samples)
    total = len(samples)
    commands = [s["commands"] for s in samples]
    ticks = [s["ticks"] for s in samples]
    return {"mission": mission_id, "seeds": list(seeds), "runs": total,
            "outcomes": {key: counts[key] for key in ("victory", "defeat", "draw", "limit")},
            "victory_rate": round(counts["victory"] / total, 4),
            "downed_mean": round(sum(s["allied_downed"] for s in samples) / total, 3),
            "damage_taken_mean": round(sum(s["damage_taken"] for s in samples) / total, 3),
            "telemetry": {"events": dict(sorted(total_events.items())),
                          "tactics": dict(sorted(total_tactics.items()))},
            "commands_p50": percentile(commands, 50),
            "commands_p95": percentile(commands, 95),
            "commands_p99": percentile(commands, 99),
            "ticks_p50": percentile(ticks, 50),
            "ticks_p95": percentile(ticks, 95),
            "ticks_p99": percentile(ticks, 99),
            "samples": samples}



def compare_compositions(variants, mission_id, *, baseline=None,
                         seeds=(1, 7, 42, 99), max_commands=500, rules=None):
    """Fair deterministic A/B runs: the same seeds and command cap for each roster.

    Variants are fully authored Content objects with the same mission identifier.
    Each Battle owns a deep copy; neither the supplied content nor RNG state is
    shared across variants. Deltas are descriptive, not causal confidence bounds.
    """
    from .model import Content
    require(isinstance(variants, dict) and 2 <= len(variants) <= 16
            and all(isinstance(name, str) and name.strip() and len(name) <= 64
                    and isinstance(content, Content)
                    and mission_id in content.missions
                    for name, content in variants.items()),
            "Need 2..16 named compositions containing the same mission")
    labels = sorted(variants)
    reference = baseline if baseline is not None else labels[0]
    require(reference in variants, "Unknown comparison baseline")
    reports = {name: evaluate(variants[name], mission_id, seeds=seeds,
                              max_commands=max_commands, rules=rules)
               for name in labels}
    first = reports[reference]
    result = []
    for name in labels:
        report = reports[name]
        result.append({
            "name": name, "baseline": name == reference,
            "victory_rate": report["victory_rate"],
            "victory_rate_delta": round(report["victory_rate"] -
                                        first["victory_rate"], 4),
            "downed_mean": report["downed_mean"],
            "downed_delta": round(report["downed_mean"] -
                                  first["downed_mean"], 3),
            "damage_taken_mean": report["damage_taken_mean"],
            "damage_taken_delta": round(report["damage_taken_mean"] -
                                         first["damage_taken_mean"], 3),
            "commands_p95": report["commands_p95"],
            "commands_p95_delta": report["commands_p95"] - first["commands_p95"],
            "report": report,
        })
    return {"mission": mission_id, "baseline": reference,
            "seeds": list(seeds), "max_commands": max_commands,
            "compositions": result}


def verify_budgets(report, *, max_p95_commands=None, max_difficulty=None,
                   max_mean_damage_taken=None, allow_limits=False):
    """Explicit CI gate; no reliance on performance of a particular computer."""
    require(isinstance(report, dict) and report.get("runs", 0) > 0,
            "Missing balance report")
    if max_p95_commands is not None:
        require(type(max_p95_commands) is int and max_p95_commands > 0,
                "Invalid command budget")
        require(report["commands_p95"] <= max_p95_commands,
                "P95 command budget exceeded")
    if max_difficulty is not None:
        require(type(max_difficulty) in (int, float) and 0 <= max_difficulty <= 1,
                "Invalid difficulty budget")
        require(1 - report["victory_rate"] <= max_difficulty,
                "Difficulty budget exceeded")
    if max_mean_damage_taken is not None:
        require(type(max_mean_damage_taken) in (int, float)
                and not isinstance(max_mean_damage_taken, bool)
                and math.isfinite(max_mean_damage_taken)
                and max_mean_damage_taken >= 0, "Invalid damage budget")
        require(report.get("damage_taken_mean", float("inf")) <= max_mean_damage_taken,
                "Mean allied damage budget exceeded")
    if not allow_limits:
        require(report["outcomes"]["limit"] == 0, "Unresolved seeded encounter")
    return True

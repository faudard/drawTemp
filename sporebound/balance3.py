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
    for seed in seeds:
        battle = Battle(content, mission_id, seed=seed, rules=rules)
        result = simulate(battle, max_commands)
        player_units = [u for u in battle.units if u.team == "player"]
        samples.append({"seed": seed, "result": result["result"],
                        "ticks": result["ticks"], "commands": result["commands"],
                        "allied_downed": sum(not u.alive for u in player_units),
                        "allied_count": len(player_units)})
    counts = Counter(s["result"] for s in samples)
    total = len(samples)
    commands = [s["commands"] for s in samples]
    ticks = [s["ticks"] for s in samples]
    return {"mission": mission_id, "seeds": list(seeds), "runs": total,
            "outcomes": {key: counts[key] for key in ("victory", "defeat", "draw", "limit")},
            "victory_rate": round(counts["victory"] / total, 4),
            "downed_mean": round(sum(s["allied_downed"] for s in samples) / total, 3),
            "commands_p50": percentile(commands, 50),
            "commands_p95": percentile(commands, 95),
            "commands_p99": percentile(commands, 99),
            "ticks_p50": percentile(ticks, 50),
            "ticks_p95": percentile(ticks, 95),
            "ticks_p99": percentile(ticks, 99),
            "samples": samples}


def verify_budgets(report, *, max_p95_commands=None, max_difficulty=None,
                   allow_limits=False):
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
    if not allow_limits:
        require(report["outcomes"]["limit"] == 0, "Unresolved seeded encounter")
    return True

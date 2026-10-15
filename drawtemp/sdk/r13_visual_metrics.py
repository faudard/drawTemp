"""R13.8 Visual Battle Lab: display-ready metrics from verified canonical runs.

No timing inference, resampling or AI predictions: all numbers are measured
Battle Lab output. Comparisons are strict paired-seed observations.
"""
from __future__ import annotations

from copy import deepcopy
from math import isfinite

from sporebound.model import require

from .r13_combat_lab import compare_encounters

SCHEMA = 1
AGGREGATE_METRICS = (
    ("victory_percent", "Victoires", "%"),
    ("ticks_p95", "Ticks CT p95", "ticks"),
    ("commands_p95", "Commandes p95", "commandes"),
    ("activations_per_run", "Activations CT / combat", "activations"),
)
SEED_METRICS = (
    ("ticks", "Ticks CT", "ticks"),
    ("commands", "Commandes", "commandes"),
    ("activations_ct", "Activations CT", "activations"),
)
OUTCOMES = ("victory", "defeat", "draw", "limit")


def _number(value):
    return type(value) in (int, float) and isfinite(value) and value >= 0


def _validate(report):
    require(type(report) is dict and report.get("kind") == "battle_lab"
            and type(report.get("mission")) is str
            and type(report.get("seeds")) in (list, tuple)
            and type(report.get("samples")) is list
            and type(report.get("runs")) is int
            and 1 <= report["runs"] <= 1000
            and len(report["samples"]) == report["runs"]
            and len(report["seeds"]) == report["runs"]
            and len(set(report["seeds"])) == report["runs"]
            and all(type(seed) is int and 0 <= seed < 2**32
                    for seed in report["seeds"])
            and _number(report.get("victory_rate"))
            and report["victory_rate"] <= 1
            and all(_number(report.get(key))
                    for key in ("ticks_p95", "commands_p95", "activations_ct"))
            and type(report.get("outcomes")) is dict
            and all(type(report["outcomes"].get(key)) is int
                    and report["outcomes"][key] >= 0 for key in OUTCOMES)
            and sum(report["outcomes"][key] for key in OUTCOMES) == report["runs"],
            "Invalid canonical Battle Lab metrics")
    for seed, sample in zip(report["seeds"], report["samples"]):
        require(type(sample) is dict and sample.get("seed") == seed
                and sample.get("result") in OUTCOMES
                and sample.get("replay_verified") is True
                and all(_number(sample.get(key))
                        for key in ("ticks", "commands", "activations_ct"))
                and type(sample.get("digest")) is str,
                "Invalid or unverified seeded Battle Lab sample")
    require(sum(s["result"] == "victory" for s in report["samples"])
            == report["outcomes"]["victory"]
            and sum(s["result"] == "limit" for s in report["samples"])
            == report["outcomes"]["limit"],
            "Battle Lab outcomes do not match seeded samples")


def _series(report, name, identifier):
    runs = report["runs"]
    aggregate = {
        "victory_percent": round(report["victory_rate"] * 100, 2),
        "ticks_p95": report["ticks_p95"],
        "commands_p95": report["commands_p95"],
        "activations_per_run": round(report["activations_ct"] / runs, 2),
    }
    return {
        "id": identifier,
        "label": name,
        "aggregate": aggregate,
        "outcomes": {key: report["outcomes"][key] for key in OUTCOMES},
        "samples": [
            {"seed": s["seed"], "result": s["result"],
             "ticks": s["ticks"], "commands": s["commands"],
             "activations_ct": s["activations_ct"]}
            for s in report["samples"]
        ],
    }


def build_visual_comparison(baseline, candidate=None, *,
                            objective_changed=False):
    """Prepare chart groups from exact battle output.

    Single-run mode is valid. For paired comparison the existing regression
    gate verifies mission, seed order, command cap and deterministic replays.
    Changed objectives may still be visualized, but are *never* labelled as
    a comparable passing balance gate.
    """
    require(type(objective_changed) is bool, "Invalid objective change flag")
    _validate(baseline)
    if candidate is not None:
        _validate(candidate)
        comparison = compare_encounters(baseline, candidate)
        issues = list(comparison["issues"])
        if objective_changed:
            issues.append("Conditions de victoire modifiées : nouvelle référence et revue humaine requises")
        compare_status = {
            "passed": comparison["passed"] and not objective_changed,
            "issues": sorted(set(issues)),
            "authored_inputs_changed": comparison["authored_inputs_changed"],
            "human_signoff_required": (
                comparison["human_signoff_required"] or objective_changed),
            "objective_changed": objective_changed,
        }
        series = [
            _series(baseline, "Avant / référence", "before"),
            _series(candidate, "Après / candidat", "after"),
        ]
        deltas = {key: round(series[1]["aggregate"][key] -
                             series[0]["aggregate"][key], 2)
                  for key, _, _ in AGGREGATE_METRICS}
    else:
        compare_status = None
        series = [_series(baseline, "Simulation", "current")]
        deltas = None
    return {
        "kind": "r13_visual_metrics", "schema": SCHEMA,
        "mission": baseline["mission"], "mode": (
            "comparison" if candidate is not None else "single"),
        "seed_order": deepcopy(baseline["seeds"]),
        "runs": baseline["runs"], "max_commands": baseline["max_commands"],
        "metrics": [{"id": key, "label": label, "unit": unit}
                    for key, label, unit in AGGREGATE_METRICS],
        "seed_metrics": [{"id": key, "label": label, "unit": unit}
                         for key, label, unit in SEED_METRICS],
        "series": series, "deltas": deltas, "comparison": compare_status,
        "units_note": ("Ticks CT, commandes et activations sont des mesures "
                       "simulées, pas une durée humaine en minutes."),
    }

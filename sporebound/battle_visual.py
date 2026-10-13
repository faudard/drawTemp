"""3.8.3 Visual Battle Lab view models — deterministic, headless, read-only.

Separate telemetry-derived chart data from Tk rendering. All figures use the
already exported Battle Lab and Combat Diagnostics JSON, never reimplement
Battle mechanics or infer human elapsed minutes from CT.
"""
from __future__ import annotations

from collections import Counter
from .battle_lab import SCHEMA as LAB_SCHEMA
from .model import require


OUTCOME_ORDER = ("victory", "defeat", "draw", "limit")
METRICS = ("damage", "healing_received", "decisions", "reactions",
           "class_survival")


def _check_report(report):
    require(isinstance(report, dict) and report.get("kind") == "battle_lab"
            and report.get("schema") == LAB_SCHEMA
            and type(report.get("samples")) is list
            and report.get("runs") == len(report["samples"])
            and report["runs"] > 0
            and type(report.get("seeds")) is list
            and report["seeds"] == [s.get("seed") for s in report["samples"]]
            and all(isinstance(s.get("commands"), int)
                    and isinstance(s.get("ticks"), int)
                    and s.get("result") in OUTCOME_ORDER
                    for s in report["samples"]),
            "Invalid Battle Lab visualization report")


def chart_model(report, *, reference=None):
    """Chart-safe model with ordered paired seeds and zero fabricated values."""
    _check_report(report)
    if reference is not None:
        _check_report(reference)
        require((reference["mission"], reference["seeds"],
                 reference["max_commands"]) ==
                (report["mission"], report["seeds"],
                 report["max_commands"]),
                "Visual comparison needs identical mission, seeds and limit")
    original = {s["seed"]: s for s in reference["samples"]} if reference else {}
    rows = []
    for sample in report["samples"]:
        old = original.get(sample["seed"])
        rows.append({
            "seed": sample["seed"], "outcome": sample["result"],
            "ct": sample["ticks"], "commands": sample["commands"],
            "replay_verified": bool(sample.get("replay_verified", False)),
            "possible_stall": bool(sample.get("possible_stall", False)),
            "previous_outcome": old["result"] if old else None,
            "ct_delta": sample["ticks"] - old["ticks"] if old else None,
            "commands_delta": sample["commands"] - old["commands"] if old else None,
            "outcome_changed": old["result"] != sample["result"] if old else False,
        })
    meters = {}
    for metric in METRICS:
        if metric == "class_survival":
            def read(row):
                return {k: v["rate"] for k, v in
                        row.get("class_survival", {}).items()}
        else:
            def read(row, field=metric):
                return row.get(field, {})
        current = read(report)
        previous = read(reference) if reference is not None else {}
        names = sorted(set(current) | set(previous))
        meters[metric] = [
            {"name": name, "value": current.get(name, 0),
             "reference": previous.get(name, 0) if reference else None,
             "delta": current.get(name, 0) - previous.get(name, 0)
             if reference else None}
            for name in names
        ]
    totals = [
        {"name": result, "count": sum(s["result"] == result
                                    for s in report["samples"]),
         "reference_count": sum(s["result"] == result
                                for s in reference["samples"])
         if reference else None}
        for result in OUTCOME_ORDER
    ]
    return {
        "mission": report["mission"],
        "runs": report["runs"],
        "seeds": list(report["seeds"]),
        "max_commands": report["max_commands"],
        "win_rate": report["victory_rate"],
        "reference_win_rate": reference["victory_rate"] if reference else None,
        "ct_p95": report["ticks_p95"],
        "commands_p95": report["commands_p95"],
        "outcomes": totals,
        "samples": rows,
        "metrics": meters,
        "paired": reference is not None,
        "units": {"ct": "ticks CT", "commands": "commandes IA"},
    }


def notable_seeds(report, *, reference=None):
    """Order seeds needing examination using reproducible, explicit signals."""
    model = chart_model(report, reference=reference)
    ranked = []
    for row in model["samples"]:
        issues = []
        if row["outcome"] == "limit":
            issues.append("unresolved")
        if row["possible_stall"]:
            issues.append("possible_stall")
        if row["outcome"] == "defeat":
            issues.append("defeat")
        if row["outcome_changed"]:
            issues.append("outcome_changed")
        if row["commands_delta"] is not None and row["commands_delta"] > 0:
            issues.append("command_growth")
        if issues:
            ranked.append({"seed": row["seed"], "issues": issues,
                           "outcome": row["outcome"], "ct": row["ct"],
                           "commands": row["commands"]})
    priority = {"unresolved": 0, "possible_stall": 1, "outcome_changed": 2,
                "defeat": 3, "command_growth": 4}
    return sorted(ranked, key=lambda row:
                  (min(priority[item] for item in row["issues"]),
                   -row["commands"], row["seed"]))


def timeline_model(trace, *, max_points=240):
    """Downsample only the drawing vertices; all real command steps stay indexed.

    Viewer selections can open the full pre-existing replay inspector at any
    exact step. No simulation, interpolation or pseudo-CT is introduced here.
    """
    require(type(trace) is dict and trace.get("kind") == "battle_diagnostics"
            and trace.get("schema") == 1 and trace.get("replay_verified") is True
            and type(trace.get("steps")) is list
            and trace.get("commands") == len(trace["steps"]),
            "Expected verified 3.8.1 diagnostic trace")
    require(type(max_points) is int and 2 <= max_points <= 5000,
            "Invalid timeline display budget")
    steps = trace["steps"]
    stride = max(1, (len(steps) + max_points - 2) // (max_points - 1))
    indices = list(range(0, len(steps), stride))
    if steps and indices[-1] != len(steps) - 1:
        indices.append(len(steps) - 1)
    points = [
        {"step": steps[i]["index"], "tick": steps[i]["tick_after"],
         "actor": steps[i]["actor"], "action": steps[i]["command"]["kind"],
         "damage": sum(e.get("amount", 0) for e in steps[i]["events"]
                       if e["kind"] == "damage"),
         "healing": sum(e.get("amount", 0) for e in steps[i]["events"]
                        if e["kind"] == "heal"),
         "events": [e["kind"] for e in steps[i]["events"]]}
        for i in indices
    ]
    reasons = Counter(row["code"] for row in trace["diagnostics"]["findings"])
    return {
        "mission": trace["mission"], "seed": trace["seed"],
        "result": trace["result"], "commands": len(steps),
        "final_tick": trace["ticks"], "stride": stride,
        "points": points,
        "findings": [
            {"step": row["step"], "code": row["code"],
             "severity": row["severity"], "actor": row.get("actor"),
             "message": row["message"]}
            for row in trace["diagnostics"]["findings"]],
        "finding_counts": dict(sorted(reasons.items())),
        "verified": True,
    }

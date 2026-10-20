"""R77.B read-only Exploration Lab: verified heatmaps, witnesses and review.

A view is built only from R77.A reports independently reproduced against the
exact source scene. Comparisons/triage remain exploratory, never certification.
No writes to Content, GameProject, AuthoringSession or external services.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json

from drawtemp.quality.r77_exploratory import explore_action_scene
from sporebound.action_runtime import ActionRuntime, validate_scene

MAX_REDUCTIONS = 64
REVIEW_CHOICES = ("suspected_false_positive", "needs_investigation",
                  "reproduced_manually", "accepted_risk")


def _sha(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _cell(runtime):
    return [v // 1000 for v in runtime.hero["pos"]]


def build_lab_view(scene, report):
    """Reject altered/unproven claims by regenerating ALL R77.A evidence.

    This is intentionally bounded by R77.A's seed/tick/static state limits.
    For a large scene, run it explicitly from a Studio button, never a timer.
    """
    source = validate_scene(scene)
    if type(report) is not dict or report.get("schema") != 1 or (
            report.get("kind") != "r77a-action-exploration") or (
            report.get("release_certified") is not False):
        raise ValueError("Expected an un-certified R77.A report")
    config = report.get("config")
    if type(config) is not dict or set(config) != {
            "seeds", "goals", "ticks_per_seed", "state_budget"}:
        raise ValueError("R77.A report lacks replay provenance")
    expected = explore_action_scene(
        source, deepcopy(config["goals"]), seeds=deepcopy(config["seeds"]),
        ticks_per_seed=config["ticks_per_seed"],
        state_budget=config["state_budget"],
    )
    if report != expected:
        raise ValueError("R77.A report fails deterministic source/replay verification")

    occupancy = defaultdict(int)
    seeds_at = defaultdict(set)
    runs = []
    for run in report["runs"]:
        runtime = ActionRuntime(source)
        timeline = [{"tick": 0, "cell": _cell(runtime), "command": None, "events": []}]
        for command in run["trace"]:
            events = runtime.step(deepcopy(command))
            timeline.append({
                "tick": runtime.tick, "cell": _cell(runtime),
                "command": deepcopy(command),
                "events": [event["kind"] for event in events],
            })
        if runtime.digest() != run["final_state_sha256"]:
            raise ValueError("Replay state changed while preparing R77.B")
        for row in timeline:
            key = tuple(row["cell"])
            occupancy[key] += 1
            seeds_at[key].add(run["seed"])
        runs.append({"seed": run["seed"], "outcome": run["outcome"],
                     "ticks": run["ticks"], "timeline": timeline,
                     "trace_sha256": run["trace_sha256"],
                     "failures": deepcopy(run["failures"])})
    static = report["static_preflight"]
    findings = []
    if static["status"] == "softlock_risk":
        for i, case in enumerate(static["counterexamples"]):
            findings.append({
                "id": "static:" + str(i),
                "kind": "abstract_softlock_risk",
                "cell": deepcopy(case["at"]),
                "witness": deepcopy(case["witness"]),
                "scope": "R29 static abstraction, NOT a Player softlock",
            })
        for cell in static["unreachable_goals"]:
            findings.append({
                "id": "unreachable:" + ",".join(map(str, cell)),
                "kind": "abstract_unreachable_goal",
                "cell": deepcopy(cell), "witness": [],
                "scope": "R29 static reachability only",
            })
    for run in report["runs"]:
        for index, error in enumerate(run["failures"]):
            findings.append({
                "id": "runtime:" + str(run["seed"]) + ":" + str(index),
                "kind": "runtime_exception",
                "seed": run["seed"], "tick": error["tick"],
                "cell": None, "witness": deepcopy(run["trace"]),
                "failed_command": deepcopy(error.get("command")),
                "error_type": error["error_type"],
                "message": error["message"],
                "scope": "R26 headless runtime; reproduce before confirmation",
            })
    paths = [{"goal": deepcopy(entry["cell"]), "steps": deepcopy(entry["witness"]),
              "length": len(entry["witness"]), "scope": "R29 shortest static BFS"}
             for entry in static["reachable_goals"]]
    return {"schema": 1, "kind": "r77b-exploration-lab",
            "scene": source["id"], "scene_sha256": _sha(source),
            "report_sha256": _sha(report),
            "dimensions": [source["width"], source["height"]],
            "status": report["status"],
            "coverage": deepcopy(report["coverage"]),
            "heatmap": [{"cell": list(cell), "visits": occupancy[cell],
                         "seeds": sorted(seeds_at[cell])}
                        for cell in sorted(occupancy)],
            "runs": runs, "critical_paths": paths, "findings": findings,
            "source_verified": True, "release_certified": False,
            "limitations": ["Visits count sampled fixed ticks, not time spent visible",
                            "Static witnesses do not prove runtime reachability",
                            "Simulation alone never certifies human UX/GPU/Player"]}


def compare_lab_views(before, after):
    """Read-only difference for two verified views; do not call it a regression gate."""
    if any(type(v) is not dict or v.get("kind") != "r77b-exploration-lab" or
           v.get("source_verified") is not True or v.get("release_certified") is not False
           for v in (before, after)):
        raise ValueError("Expected R77.B views")
    if before["scene"] != after["scene"] or (
            before["dimensions"] != after["dimensions"]):
        raise ValueError("Comparisons require matching scene ID and dimensions")
    original = {tuple(row["cell"]): row["visits"] for row in before["heatmap"]}
    updated = {tuple(row["cell"]): row["visits"] for row in after["heatmap"]}
    cells = sorted(set(original) | set(updated))
    old_goals = {tuple(c) for c in before["coverage"]["goals"]}
    new_goals = {tuple(c) for c in after["coverage"]["goals"]}
    return {"schema": 1, "kind": "r77b-comparison",
            "source_changed": before["scene_sha256"] != after["scene_sha256"],
            "config_or_source_changed": before["report_sha256"] != after["report_sha256"],
            "before_report_sha256": before["report_sha256"],
            "after_report_sha256": after["report_sha256"],
            "visits_delta": [{"cell": list(cell),
                              "delta": updated.get(cell, 0) - original.get(cell, 0)}
                             for cell in cells if updated.get(cell, 0) != original.get(cell, 0)],
            "newly_visited": [list(c) for c in sorted(set(updated) - set(original))],
            "no_longer_visited": [list(c) for c in sorted(set(original) - set(updated))],
            "newly_reached_goals": [list(c) for c in sorted(new_goals - old_goals)],
            "lost_goals": [list(c) for c in sorted(old_goals - new_goals)],
            "old_findings": len(before["findings"]),
            "new_findings": len(after["findings"]),
            "release_certified": False,
            "scope": "observed seed/tick coverage delta, NOT a gameplay regression verdict"}


def triage_finding(view, finding_id, decision, reason, *, existing=None):
    """Human annotation only, detached, never alters report/evidence or Studio."""
    if type(view) is not dict or view.get("kind") != "r77b-exploration-lab" or (
            view.get("source_verified") is not True):
        raise ValueError("Verified R77.B view required")
    if type(finding_id) is not str or finding_id not in {
            row["id"] for row in view["findings"]}:
        raise ValueError("Unknown finding")
    if decision not in REVIEW_CHOICES or type(reason) is not str or not (
            8 <= len(reason.strip()) <= 1000):
        raise ValueError("Select an explicit decision and reason (8..1000 chars)")
    annotations = deepcopy(existing) if existing is not None else {}
    if type(annotations) is not dict or len(annotations) > 64:
        raise ValueError("Too many review notes")
    if any(key not in {r["id"] for r in view["findings"]} for key in annotations):
        raise ValueError("Review notes belong to another report")
    annotations[finding_id] = {
        "decision": decision, "reason": reason.strip(),
        "scene_sha256": view["scene_sha256"],
        "report_sha256": view["report_sha256"], "human_review_only": True,
    }
    return annotations


def minimize_runtime_failure(scene, prefix, failing_command, *, error_type, message,
                             max_replays=32):
    """Bounded deletion minimizer for an actually reproducible R26 exception.

    Commands are renumbered after deletion. A shortest-by-BFS static witness is
    already exposed separately; this ddmin never claims global minimality.
    """
    source = validate_scene(scene)
    if (type(prefix) is not list or len(prefix) > 512 or
            type(failing_command) is not dict or type(error_type) is not str or
            not error_type or type(message) is not str or
            type(max_replays) is not int or not 1 <= max_replays <= MAX_REDUCTIONS):
        raise ValueError("Invalid minimization input/budget")
    commands = deepcopy(prefix) + [deepcopy(failing_command)]
    if not all(type(c) is dict and type(c.get("tick")) is int and
               c["tick"] == index for index, c in enumerate(commands, 1)):
        raise ValueError("Commands must use consecutive ticks")
    def reproduces(rows):
        runtime = ActionRuntime(source)
        for index, original in enumerate(rows, 1):
            command = {**original, "tick": index}
            try:
                runtime.step(command)
            except Exception as exc:
                return (type(exc).__name__ == error_type and str(exc) == message
                        and index == len(rows))
        return False

    attempts = 1
    if not reproduces(commands):
        return {"status": "not_reproduced", "attempts": attempts,
                "commands": deepcopy(commands), "release_certified": False}
    remaining = deepcopy(commands[:-1])
    chunk = max(1, len(remaining) // 2)
    while chunk and attempts < max_replays:
        changed = False
        for index in range(0, len(remaining), chunk):
            if attempts >= max_replays:
                break
            proposed = remaining[:index] + remaining[index + chunk:]
            attempts += 1
            if reproduces(proposed + [commands[-1]]):
                remaining = proposed
                changed = True
                break
        if not changed:
            chunk //= 2
    reduced = [{**row, "tick": i} for i, row in
               enumerate(remaining + [commands[-1]], 1)]
    return {"status": "reproduced_reduced" if len(reduced) < len(commands)
            else "reproduced_unreduced", "attempts": attempts,
            "commands": reduced, "release_certified": False,
            "scope": "locally minimal under bounded deletion attempts only"}

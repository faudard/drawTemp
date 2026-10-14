"""R13 combat-design services for DrawTemp 5.0.

All tactical state is supplied by the canonical Battle/Content implementation.
These adapters are read-only; variants are isolated copies, not savegames or
a second AI. The report format is independent of any Qt/Tk widgets.
"""
from __future__ import annotations

from copy import deepcopy

from sporebound.battle_lab import compare_reports, run_lab
from sporebound.balance_matrix import run_matrix
from sporebound.battle_diagnostics import trace_seed
from sporebound.encounter_balance6 import (
    ai_decision_analytics,
    campaign_balance_curve,
    campaign_curve_review,
    encounter_profile,
    human_variant_breakdown,
)
from sporebound.engine import Battle
from sporebound.model import Content, require
from sporebound.tactical_intents import tactical_intents

SCHEMA = 1


def inspect_encounter(content, mission_id, *, seed=1, rules=None, max_cells=1024):
    """Inspect actual encounter geometry and conditional AI telegraphs.

    This initial state does not predict future AI decisions. Scheduled casts,
    armed reactions and possible charges retain their certainty labels.
    """
    require(isinstance(content, Content) and mission_id in content.missions,
            "R13 requires an authored encounter")
    require(type(seed) is int and 0 <= seed < 2**32, "Invalid R13 seed")
    require(type(max_cells) is int and 1 <= max_cells <= 4096,
            "Invalid intent projection limit")
    battle = Battle(content, mission_id, seed=seed, rules=rules)
    before = battle.digest()
    intents = tactical_intents(battle, max_cells=max_cells)
    require(battle.digest() == before, "Tactical inspection changed the battle")
    mission = battle.mission
    return {
        "schema": SCHEMA, "kind": "r13_encounter_inspection",
        "mission": mission_id, "seed": seed, "battle_digest": before,
        "profile": encounter_profile(content, mission_id),
        "goal_cells": [list(cell) for cell in sorted(mission.goal)],
        "objects": deepcopy(mission.objects),
        "level_links": deepcopy(mission.level_links),
        "tiles": [
            {"cell": list(cell), "height": tile.height,
             "cover": tile.cover, "hazard": tile.hazard,
             "blocked": tile.blocked}
            for cell, tile in sorted(mission.board.tiles.items())
        ],
        "intent": intents,
        "note": "AI telegraphs describe known or possible threats, not predicted commands",
    }


def evaluate_variant(content, mission_id, edits, *, seeds=(1, 7, 42, 99),
                     max_commands=500):
    """Trial a hypothetical authored placement/terrain/equipment change.

    `edits` follows the existing Balance Matrix case contract. Neither this
    API nor run_matrix saves any change to the source Content.
    """
    require(isinstance(content, Content) and mission_id in content.missions,
            "Unknown encounter")
    require(type(edits) is dict and "mission" not in edits
            and "id" not in edits, "Edits must not change mission identity")
    spec = {"id": mission_id + "/r13-trial", "mission": mission_id,
            **deepcopy(edits)}
    return run_matrix(content, [spec], seeds=seeds, max_commands=max_commands)


def simulate_encounter(content, mission_id, *, seeds=(1, 7, 42, 99),
                       max_commands=500, rules=None, progress=None,
                       initial_state=None, trace_seed_id=None):
    """Run canonical AI, verify every replay, optionally include one drilldown.

    The diagnostic replay is capped separately from aggregate Battle Lab
    telemetry to avoid unexpectedly exporting large traces.
    """
    report = run_lab(content, mission_id, seeds=seeds,
                     max_commands=max_commands, rules=rules,
                     progress=progress, initial_state=initial_state)
    require(all(row.get("replay_verified") is True
                for row in report["samples"]), "Unverified battle replay")
    result = {"schema": SCHEMA, "kind": "r13_simulation",
              "battle_lab": report, "trace": None, "ai_analytics": None}
    if trace_seed_id is not None:
        require(type(trace_seed_id) is int and trace_seed_id in seeds,
                "Diagnostic seed must belong to the simulated batch")
        # Traces start from an ordinary battle, not a prepared campaign battle.
        require(progress is None, "Campaign-prepared diagnostics are unavailable")
        require(max_commands <= 5000, "Trace supports at most 5000 commands")
        trace = trace_seed(content, mission_id, seed=trace_seed_id,
                           max_commands=max_commands, rules=rules,
                           initial_state=initial_state)
        require(trace["replay_verified"] is True,
                "R13 diagnostic replay could not be verified")
        result["trace"] = trace
        result["ai_analytics"] = ai_decision_analytics(trace)
    return result


def trace_timeline(trace, *, limit=5000):
    """Small JSON-friendly frames for a timeline/map view. No invented turns."""
    require(type(trace) is dict and trace.get("kind") == "battle_diagnostics"
            and trace.get("replay_verified") is True
            and type(trace.get("steps")) is list,
            "Expected a replay-verified canonical trace")
    require(type(limit) is int and 1 <= limit <= 5000,
            "Invalid timeline length")
    frames = []
    for step in trace["steps"][:limit]:
        units = step["after"]["units"]
        frames.append({
            "index": step["index"], "actor": step["actor"],
            "team": step["team"], "command": deepcopy(step["command"]),
            "positions": [
                {"id": u["id"], "team": u["team"],
                 "cell": list(u["pos"]), "alive": u["alive"]}
                for u in units
            ],
            "events": deepcopy(step["events"]),
            "hold_ticks": step["after"]["hold_ticks"],
        })
    return {
        "kind": "r13_visual_timeline", "schema": SCHEMA,
        "mission": trace["mission"], "seed": trace["seed"],
        "digest": trace["digest"], "replay_verified": True,
        "truncated": len(trace["steps"]) > limit,
        "frames": frames,
    }


def compare_encounters(baseline, current, *, max_victory_drop=0.25,
                       max_p95_growth=0.30, max_new_limits=0):
    """Paired-seed regression with explicit authored-input change disclosure."""
    comparison = compare_reports(
        baseline, current, max_victory_drop=max_victory_drop,
        max_p95_growth=max_p95_growth, max_new_limits=max_new_limits)
    unverified = sorted({
        row["seed"] for report in (baseline, current)
        for row in report["samples"] if row.get("replay_verified") is not True
    })
    issues = list(comparison["issues"])
    if unverified:
        issues.append("Unverified replay seeds: " +
                      ", ".join(str(seed) for seed in unverified))
    return {
        "kind": "r13_regression", "schema": SCHEMA,
        "passed": not issues, "issues": sorted(set(issues)),
        "paired": comparison,
        "authored_inputs_changed": comparison["authored_inputs_changed"],
        "human_signoff_required": comparison["authored_inputs_changed"],
        "note": ("A changed encounter requires human duration/usability review; "
                 "simulated CT ticks cannot certify real player minutes"),
    }


def human_review(playtest_report, *, annotations=(), min_complete=5):
    """Analyze existing local opt-in playtests; never enable data collection."""
    return human_variant_breakdown(playtest_report, annotations,
                                   min_complete=min_complete)


def campaign_review(content, campaign, missions, *, seeds, max_commands=500,
                    rules=None):
    """Real campaign progression and XP/economy evidence, not a mock curve."""
    curve = campaign_balance_curve(content, campaign, missions, seeds=seeds,
                                   max_commands=max_commands, rules=rules)
    return {"curve": curve, "review": campaign_curve_review(curve)}

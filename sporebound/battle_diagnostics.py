"""Battle Lab 3.8.1 — explainable seeded diagnostics, never an alternate AI.

Capture before/after decisions through the canonical ai.simulate hooks; inspect
the exact executed Battle commands, not hypothetical forecasts. Diagnostics
are evidence-labelled heuristics and do not change victory conditions.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json

from .ai import simulate
from .engine import Battle
from .model import require

TRACE_VERSION = 1
MAX_TRACE_COMMANDS = 5000


def _frame(battle):
    """Small, JSON-safe tactical snapshot after one real engine command."""
    return {
        "tick": battle.tick,
        "active": battle.active_id,
        "result": battle.result,
        "hold_ticks": battle.hold_ticks,
        "carrier": battle.carrier,
        "relic_pos": battle.relic_pos,
        "fired": list(battle.fired),
        "units": [{
            "id": unit.id, "name": unit.name, "team": unit.team,
            "pos": list(unit.pos), "level": battle.unit_levels.get(unit.id, 0),
            "hp": unit.hp, "max_hp": unit.max_hp, "mp": unit.mp,
            "ct": unit.ct, "alive": unit.alive,
        } for unit in battle.units],
        "objects": [{
            "id": obj["id"], "kind": obj.get("kind"),
            "pos": list(obj.get("pos", ())), "open": obj.get("open"),
            "hp": obj.get("hp"),
        } for obj in battle.mission.objects],
    }


def _progress(frame):
    """Ignore expected CT-only clock advancement while detecting no progress."""
    return (
        tuple((u["id"], u["pos"][0], u["pos"][1], u["level"], u["hp"])
              for u in frame["units"]),
        tuple((o["id"], o["pos"], o["open"], o["hp"])
              for o in frame["objects"]),
        frame["hold_ticks"], frame["carrier"], str(frame["relic_pos"]),
        tuple(frame["fired"]),
    )


def diagnose_trace(steps, outcome, *, stall_window=20, idle_activations=4):
    """Return inspectable signals, not claims about AI optimality or soft-locks."""
    require(isinstance(steps, list), "Diagnostics need ordered steps")
    require(isinstance(outcome, str) and outcome in
            {"victory", "defeat", "draw", "limit"}, "Invalid diagnosis outcome")
    require(type(stall_window) is int and stall_window >= 2
            and type(idle_activations) is int and idle_activations >= 2,
            "Invalid diagnostic thresholds")
    findings = []
    wait_streak = Counter()
    no_progress = 0
    longest = 0
    for row in steps:
        kind = row["command"]["kind"]
        actor = row["actor"]
        index = row["index"]
        progress = row["progress"]
        no_progress = 0 if progress else no_progress + 1
        longest = max(longest, no_progress)
        if actor and kind == "end":
            wait_streak[actor] += 1
            if wait_streak[actor] == idle_activations:
                findings.append({
                    "code": "repeat_idle", "severity": "info",
                    "step": index, "actor": actor,
                    "message": "Activations terminées sans autre action : vérifier "
                               "l'objectif, la portée et les choix IA.",
                    "evidence": {"consecutive_end_commands": idle_activations},
                })
        elif actor:
            wait_streak[actor] = 0
        for event in row["events"]:
            if event["kind"] == "heal" and event.get("amount") == 0:
                findings.append({
                    "code": "zero_effect_heal", "severity": "warning",
                    "step": index, "actor": actor,
                    "message": "Soin exécuté sans points de vie restaurés.",
                    "evidence": {"target": event.get("unit"), "amount": 0},
                })
            elif event["kind"] == "cast_failed":
                findings.append({
                    "code": "failed_cast", "severity": "info",
                    "step": index, "actor": actor,
                    "message": "Incantation échouée : examiner les ressources ou "
                               "l'interruption dans les événements du moteur.",
                    "evidence": {"event": deepcopy(event)},
                })
    if outcome == "limit":
        findings.append({
            "code": "command_budget", "severity": "warning",
            "step": len(steps), "actor": steps[-1]["actor"] if steps else None,
            "message": "Budget de simulation atteint sans conclusion. "
                       "Cela ne prouve pas un blocage tactique.",
            "evidence": {"commands": len(steps)},
        })
        if no_progress >= stall_window:
            findings.append({
                "code": "no_progress_window", "severity": "warning",
                "step": len(steps), "actor": steps[-1]["actor"] if steps else None,
                "message": "Aucune progression observable récemment "
                           "(PV/positions/objets/objectif) : analyser le replay.",
                "evidence": {"consecutive_commands": no_progress,
                             "threshold": stall_window},
            })
    return {"findings": findings, "counts": dict(sorted(
        Counter(f["code"] for f in findings).items())),
            "longest_no_progress_commands": longest}


def trace_seed(content, mission_id, *, seed=42, max_commands=500, rules=None,
               stall_window=20):
    """Re-simulate one seed, capture every executed command, validate full replay.

    The trace is a separate export, not embedded into the existing 3.8 balance
    baseline. Every frame comes from canonical Battle.execute and is inspectable
    without mutating user authoring data.
    """
    require(mission_id in content.missions, "Unknown diagnostic mission")
    require(type(seed) is int and 0 <= seed < 2**32,
            "Invalid unsigned 32-bit seed")
    require(type(max_commands) is int and 1 <= max_commands <= MAX_TRACE_COMMANDS,
            "Diagnostic trace command cap must be 1..5000")
    require(type(stall_window) is int and 2 <= stall_window <= MAX_TRACE_COMMANDS,
            "Invalid no-progress threshold")
    battle = Battle(content, mission_id, seed=seed, rules=rules)
    initial = _frame(battle)
    steps = []
    before = None
    event_index = 0

    def on_decision(state, command):
        nonlocal before, event_index
        before = _frame(state)
        event_index = len(state.events)

    def after_decision(state, command):
        nonlocal before
        frame = _frame(state)
        steps.append({
            "index": len(steps) + 1,
            "actor": next((u["id"] for u in before["units"]
                           if u["id"] == before["active"]), None),
            "team": next((u["team"] for u in before["units"]
                          if u["id"] == before["active"]), "deployment"),
            "tick_before": before["tick"],
            "tick_after": frame["tick"],
            "command": deepcopy(command),
            "events": deepcopy(state.events[event_index:]),
            "progress": _progress(before) != _progress(frame),
            "after": frame,
        })
        before = None

    simulation = simulate(battle, max_commands=max_commands, observer=on_decision,
                          after_command=after_decision)
    recording = battle.recording()
    replay = Battle.replay(recording, rules=battle.rules)
    require(replay.digest() == simulation["digest"]
            and len(steps) == len(recording["commands"])
            and all(a["command"] == b for a, b in
                    zip(steps, recording["commands"])),
            "Diagnostic command trace/replay divergence")
    diagnostics = diagnose_trace(steps, simulation["result"],
                                 stall_window=stall_window)
    source_hash = hashlib.sha256(json.dumps(content.to_dict(),
                                           sort_keys=True,
                                           ensure_ascii=False,
                                           separators=(",", ":")).encode()).hexdigest()
    mission = battle.mission
    # Engine events may contain tuple cells; publish an ordinary JSON tree
    # so exported reports round-trip identically across Python and OS builds.
    payload = {
        "kind": "battle_diagnostics", "schema": TRACE_VERSION,
        "mission": mission_id, "seed": seed, "max_commands": max_commands,
        "content_sha256": source_hash, "rules_manifest": battle.rules.manifest(),
        "result": simulation["result"], "ticks": simulation["ticks"],
        "commands": simulation["commands"], "digest": simulation["digest"],
        "replay_verified": True,
        "board": {"width": mission.board.width, "height": mission.board.height,
                  "goals": [list(c) for c in mission.goal]},
        "initial": initial, "steps": steps, "diagnostics": diagnostics,
    }
    return json.loads(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def trace_report(path, report):
    """Export a trace without overwriting the authored Content or savegame."""
    from pathlib import Path
    require(isinstance(report, dict) and report.get("kind") == "battle_diagnostics"
            and report.get("schema") == TRACE_VERSION and
            report.get("replay_verified") is True, "Invalid diagnostic trace")
    target = Path(path)
    target.write_text(json.dumps(report, sort_keys=True, ensure_ascii=False,
                                 indent=2) + "\n", encoding="utf-8")
    return target

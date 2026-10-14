"""3.8.4 explicit opt-in, local human playtest measurements.

The recorder observes *committed* PlayerController actions only. It never
changes GameSession, Battle, replay journals, RNG or savegame schemas. Reports
contain authored mission/unit IDs, command kinds, coarse tactical evidence and
monotonic elapsed time; no player account, device identity, free text, personal
profile path or wall-clock timestamp is collected.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import time

from .model import require

SCHEMA = 1
MAX_EVENTS = 10000
RESULTS = {"victory", "defeat", "draw", "abandoned", "interrupted",
           "stopped", "in_progress"}
SAFE_EVENT_FIELDS = {"kind", "unit", "source", "amount", "tactic", "object",
                     "team", "skill"}
SAFE_COMMAND_FIELDS = {"kind", "skill", "item", "mode", "object", "unit"}
ACTION_CLASSES = {
    "execute": "combat_command",
    "choose_tactical_story_option": "tactical_choice",
    "choose_story_option": "narrative_choice",
    "start_mission": "start_mission",
    "abandon_encounter": "abandon",
    "return_to_campaign": "return_to_campaign",
    "switch_front": "switch_front",
    "advance_fronts": "advance_fronts",
}


def _unit_snapshot(battle):
    if battle is None:
        return None
    return {
        "battle_id": battle.battle_id,
        "mission": battle.mission.id,
        "result": battle.result,
        "tick": battle.tick,
        "event_index": len(battle.events),
        "command_index": len(battle.commands),
        "actor": battle.active.id if battle.active is not None else None,
        "team": battle.active.team if battle.active is not None else None,
        "objective": battle.mission.objective,
        "hold_ticks": battle.hold_ticks,
        "goal_occupied": any(u.alive and u.team == "player"
                             and u.pos in battle.mission.goal for u in battle.units),
        "hp": {u.id: u.hp for u in battle.units},
        "survival": {u.id: u.alive for u in battle.units},
    }


def _safe_engine_events(events):
    return [
        {key: deepcopy(value) for key, value in event.items()
         if key in SAFE_EVENT_FIELDS and isinstance(value, (str, int, float, bool))}
        for event in events
    ]


class PlaytestRecorder:
    """In-memory, off by default; clock injected for repeatable tests."""

    def __init__(self, *, clock=None, content=None, rules=None):
        self.clock = clock if clock is not None else time.monotonic
        from .battle_lab import _fingerprint
        self.content_sha256 = (_fingerprint(content.to_dict())
                               if content is not None else None)
        self.rules_manifest = rules.manifest() if rules is not None else None
        self.enabled = False
        self.revision = 0
        self.sessions = []
        self.active = None
        self.error = None

    def enable(self, battle=None):
        self.enabled = True
        if battle is not None and self.active is None:
            self._begin(_unit_snapshot(battle), partial=True)

    def disable(self):
        self.finish("stopped")
        self.enabled = False

    def _begin(self, frame, *, partial=False):
        require(frame is not None, "Playtest requires an active battle")
        if self.active is not None:
            return
        start = self.clock()
        require(isinstance(start, (float, int)) and math.isfinite(start),
                "Invalid monotonic clock")
        self.revision += 1
        self.active = {
            "started_monotonic": start,
            "mission": frame["mission"],
            "battle_id": frame["battle_id"], "objective": frame["objective"],
            "partial_capture": bool(partial),
            "start_tick": frame["tick"], "events": [],
            "truncated_events": 0, "last_tick": frame["tick"],
            "last_result": frame["result"], "last_hp": frame["hp"],
            "last_survival": frame["survival"],
            "last_hold_ticks": frame["hold_ticks"],
            "last_goal_occupied": frame["goal_occupied"],
        }

    def before(self, battle):
        """Capture pre-command state before the canonical action is attempted."""
        if not self.enabled or battle is None:
            return None
        return _unit_snapshot(battle)

    def committed(self, name, before, battle, *, command=None):
        """Called only AFTER persistent GameSession.save succeeds."""
        if not self.enabled:
            return
        after = _unit_snapshot(battle)
        if self.active is not None and (
                after is None or after["battle_id"] != self.active["battle_id"]):
            # A finished encounter is usually returned to campaign explicitly;
            # do not classify a completed victory as abandonment.
            result = self.active["last_result"]
            self.finish(result if result in {"victory", "defeat", "draw"}
                        else "abandoned" if name == "abandon_encounter"
                        else "interrupted")
        if after is None:
            return
        if self.active is None:
            self._begin(after, partial=(name != "start_mission"))
        current = self.active
        # Ignore unrelated inactive front battles; we only instrument the
        # focused battle. Switching focus creates a separate local sample.
        if current["battle_id"] != after["battle_id"]:
            return
        elapsed = max(0.0, self.clock() - current["started_monotonic"])
        detail = {}
        if name == "execute" and type(command) is dict:
            detail = {key: value for key, value in command.items()
                      if key in SAFE_COMMAND_FIELDS and
                      isinstance(value, (str, int, float, bool))}
        event_rows = _safe_engine_events(
            battle.events[before["event_index"]:]
            if before is not None and
            before["battle_id"] == after["battle_id"]
            else [])
        row = {
            "seconds": round(elapsed, 3), "event": ACTION_CLASSES.get(name, "other"),
            "actor": before["actor"] if before is not None else None,
            "team": before["team"] if before is not None else None,
            "command": detail, "tick": after["tick"],
            "command_count": after["command_index"],
            "objective_hold_ticks": after["hold_ticks"],
            "goal_occupied": after["goal_occupied"],
            "damage": sum(e.get("amount", 0) for e in event_rows
                          if e.get("kind") == "damage"),
            "healing": sum(e.get("amount", 0) for e in event_rows
                           if e.get("kind") == "heal"),
            "engine_events": event_rows,
            "units_down": sorted(uid for uid, alive in after["survival"].items()
                                 if not alive),
        }
        if len(current["events"]) < MAX_EVENTS:
            current["events"].append(row)
        else:
            current["truncated_events"] += 1
        self.revision += 1
        current["last_tick"] = after["tick"]
        current["last_hp"] = after["hp"]
        current["last_survival"] = after["survival"]
        current["last_result"] = after["result"]
        current["last_hold_ticks"] = after["hold_ticks"]
        current["last_goal_occupied"] = after["goal_occupied"]
        if after["result"] in {"victory", "defeat", "draw"}:
            self.finish(after["result"])

    def finish(self, reason="interrupted"):
        require(reason in RESULTS - {"in_progress"}, "Invalid finish reason")
        if self.active is None:
            return
        record = self._report_active(reason)
        self.sessions.append(record)
        self.revision += 1
        self.active = None

    def _report_active(self, result):
        current = self.active
        elapsed = max(0.0, self.clock() - current["started_monotonic"])
        actions = Counter(row["event"] for row in current["events"])
        commands = Counter(row["command"].get("kind") for row in current["events"]
                           if row["event"] == "combat_command")
        return {
            "mission": current["mission"], "objective": current["objective"],
            "outcome": result,
            "partial_capture": current["partial_capture"],
            "duration_seconds": round(elapsed, 3),
            "duration_basis": "wall_elapsed_monotonic_including_idle",
            "ct_start": current["start_tick"], "ct_end": current["last_tick"],
            "accepted_actions": dict(sorted(actions.items())),
            "command_kinds": dict(sorted(commands.items())),
            "objective_hold_ticks": current["last_hold_ticks"],
            "goal_occupied": current["last_goal_occupied"],
            "surviving_units": sum(current["last_survival"].values()),
            "damage_observed": sum(row["damage"] for row in current["events"]),
            "healing_observed": sum(row["healing"] for row in current["events"]),
            "truncated_events": current["truncated_events"],
            "events": deepcopy(current["events"]),
        }

    def report(self):
        sessions = deepcopy(self.sessions)
        if self.active is not None:
            sessions.append(self._report_active("in_progress"))
        return {
            "kind": "human_playtest", "schema": SCHEMA,
            "opt_in": True,
            "privacy": "local_export_only_no_personal_identifiers",
            "content_sha256": self.content_sha256,
            "rules_manifest": self.rules_manifest,
            "sessions": sessions,
        }


def validate_report(value):
    require(type(value) is dict and value.get("kind") == "human_playtest"
            and value.get("schema") == SCHEMA
            and value.get("opt_in") is True
            and type(value.get("sessions")) is list,
            "Invalid human playtest report")
    for row in value["sessions"]:
        require(type(row) is dict and
                type(row.get("mission")) is str and row["mission"]
                and row.get("outcome") in RESULTS
                and type(row.get("duration_seconds")) in (int, float)
                and math.isfinite(row["duration_seconds"])
                and row["duration_seconds"] >= 0
                and type(row.get("events")) is list
                and type(row.get("truncated_events")) is int
                and row["truncated_events"] >= 0,
                "Invalid human playtest session")
    return value


def save_playtest(path, report):
    """File creation is explicit; caller chooses the local destination."""
    validate_report(report)
    target = Path(path)
    target.write_text(json.dumps(report, sort_keys=True,
                                 ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return target


def analyze_playtests(report, *, mission=None, ai_report=None):
    """Human real-minute aggregates; AI metrics are separate, never converted."""
    from .balance3 import percentile
    validate_report(report)
    rows = [s for s in report["sessions"]
            if (mission is None or s["mission"] == mission)
            and s["outcome"] not in {"in_progress", "stopped", "interrupted"}]
    completed = [s for s in rows if s["outcome"] in
                 {"victory", "defeat", "draw"} and not s["partial_capture"]]
    durations = [s["duration_seconds"] for s in completed]
    result = {
        "mission": mission,
        "sessions": len(rows),
        "complete_observations": len(completed),
        "outcomes": dict(sorted(Counter(s["outcome"] for s in rows).items())),
        "abandonment_rate": round(
            sum(s["outcome"] == "abandoned" for s in rows) / len(rows), 4)
        if rows else None,
        "human_duration_minutes_p50": round(percentile(durations, 50) / 60, 2)
        if durations else None,
        "human_duration_minutes_p95": round(percentile(durations, 95) / 60, 2)
        if durations else None,
        "commands": dict(sorted(sum((Counter(s["command_kinds"]) for s in rows),
                                     Counter()).items())),
        "player_commands": dict(sorted(sum((
            Counter(event["command"].get("kind") for event in s["events"]
                    if event["event"] == "combat_command"
                    and event["team"] == "player" and event["command"])
            for s in rows), Counter()).items())),
        "enemy_commands": dict(sorted(sum((
            Counter(event["command"].get("kind") for event in s["events"]
                    if event["event"] == "combat_command"
                    and event["team"] == "enemy" and event["command"])
            for s in rows), Counter()).items())),
        "damage_observed": sum(s["damage_observed"] for s in rows),
        "healing_observed": sum(s["healing_observed"] for s in rows),
        "partial_or_incomplete": sum(
            s["partial_capture"] or s["outcome"] in
            {"in_progress", "stopped", "interrupted"} for s in report["sessions"]
            if mission is None or s["mission"] == mission),
    }
    if ai_report is not None:
        require(type(ai_report) is dict and
                ai_report.get("kind") == "battle_lab" and
                (mission is None or ai_report.get("mission") == mission),
                "AI reference needs a matching Battle Lab mission")
        result["ai_reference"] = {
            "mission": ai_report["mission"],
            "win_rate": ai_report["victory_rate"],
            "ct_p95": ai_report["ticks_p95"],
            "commands_p95": ai_report["commands_p95"],
            "note": "AI CT/commands are not human minutes",
            "matching_content": (
                report.get("content_sha256") == ai_report.get("content_sha256")
                if report.get("content_sha256") and ai_report.get("content_sha256")
                else None),
        }
    return result

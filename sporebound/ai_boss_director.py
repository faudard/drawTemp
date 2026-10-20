"""R37.E1 — canonical boss phase director, presentation and replay-safe diagnostics.

Boss transformations remain authored hp_below -> boss_phase R2.7.5 actions.
Reinforcement scheduling stays with EncounterDirector and waves remain
possible/queued/observed as exposed by R6B. This module only validates
presentation metadata and projects actual Battle state; no virtual phase
clock, attacks, wave spawning or hidden mutations.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from .model import require

MAX_DIRECTORS = 16
MAX_PHASES = 8
MAX_LABEL = 80
MAX_CUE = 160


def _ident(value):
    return (type(value) is str and 1 <= len(value) <= 64
            and value[0].isascii() and value[0].islower()
            and all(ch.isascii() and (ch.islower() or ch.isdigit() or ch == "_")
                    for ch in value))


def _starting_phase(actor):
    tags = [tag for tag in actor.tags if tag.startswith("boss_phase:")]
    require(len(tags) <= 1, "R37 boss has duplicate phase tags")
    if not tags:
        return 1
    try:
        phase = int(tags[0].partition(":")[2])
    except ValueError as exc:
        raise ValueError("R37 invalid boss phase tag") from exc
    require(1 <= phase <= MAX_PHASES, "R37 boss phase must be 1..8")
    return phase


def _scripted_transitions(mission, boss_id):
    """Only actual authored R8 hp triggers may advance a boss phase."""
    phases = {}
    for trigger in mission.triggers:
        for action in trigger.get("actions", []):
            if action.get("kind") != "boss_phase" or action.get("unit") != boss_id:
                continue
            require(trigger.get("condition") == "hp_below"
                    and trigger.get("unit") == boss_id
                    and type(trigger.get("percent")) is int
                    and 1 <= trigger["percent"] <= 99,
                    "Boss phase metadata requires canonical hp_below trigger")
            target = action.get("phase")
            require(type(target) is int and 2 <= target <= MAX_PHASES
                    and target not in phases,
                    "R37 boss phase trigger must be unique and in 2..8")
            phases[target] = {"trigger": trigger["id"],
                              "percent": trigger["percent"]}
    return phases


def validate_boss_directors(directors, *, content):
    """Reject ghost boss abilities/phases; phase references are canonical R8."""
    require(content is not None and hasattr(content, "missions"),
            "R37 boss directors require validated tactical content")
    require(type(directors) is list
            and 1 <= len(directors) <= MAX_DIRECTORS,
            "R37 requires 1..16 boss director documents")
    used = set()
    used_bosses = set()
    result = []
    for director in directors:
        require(type(director) is dict and set(director) ==
                {"id", "mission", "boss", "phases"}
                and _ident(director["id"]) and director["id"] not in used
                and type(director["mission"]) is str
                and director["mission"] in content.missions
                and type(director["boss"]) is str
                and type(director["phases"]) is list,
                "R37 boss director has malformed or duplicate identity")
        used.add(director["id"])
        identity = (director["mission"], director["boss"])
        require(identity not in used_bosses,
                "R37 boss already has a director in this mission")
        used_bosses.add(identity)
        mission = content.missions[director["mission"]]
        boss = next((unit for unit in mission.units
                     if unit.id == director["boss"]), None)
        require(boss is not None and boss.team == "enemy"
                and boss.behavior in ("phase_boss", "adaptive_boss"),
                "R37 boss requires a canonical enemy phase/adaptive boss actor")
        starting = _starting_phase(boss)
        authored = _scripted_transitions(mission, boss.id)
        phases = director["phases"]
        require(1 <= len(phases) <= MAX_PHASES
                and [p.get("phase") for p in phases if type(p) is dict] ==
                list(range(starting, starting + len(phases)))
                and len(phases) == len([p for p in phases if type(p) is dict]),
                "R37 authored boss phases must be contiguous from initial phase")
        require(set(authored) == {row["phase"] for row in phases[1:]},
                "R37 boss director must describe every real scripted transition")
        for index, row in enumerate(phases):
            require(set(row) == {"phase", "label", "cue", "trigger"}
                    and type(row["phase"]) is int
                    and 1 <= row["phase"] <= MAX_PHASES
                    and type(row["label"]) is str
                    and 1 <= len(row["label"]) <= MAX_LABEL
                    and type(row["cue"]) is str
                    and len(row["cue"]) <= MAX_CUE,
                    "Malformed R37 boss phase presentation")
            expected_trigger = (None if index == 0 else
                                authored[row["phase"]]["trigger"])
            require(type(row["trigger"]) is
                    (type(None) if index == 0 else str)
                    and row["trigger"] == expected_trigger,
                    "R37 boss phase is not backed by its canonical trigger")
        result.append(deepcopy(director))
    return sorted(result, key=lambda d: d["id"])


def preview_boss_director(battle, director):
    """A read-only encounter director overlay over actual CT Battle history."""
    require(type(director) is dict and set(director) ==
            {"id", "mission", "boss", "phases"}
            and director["mission"] == battle.mission.id,
            "R37 boss director does not belong to this battle")
    # Validate the exact authored trigger-to-phase contract before access.
    validate_boss_directors([director], content=battle.content)
    from .elite_boss_r6 import boss_r6_telegraph
    from .boss_encounter_r6b import arrived_reinforcements
    from .bosses3 import boss_preview
    actor = battle.unit(director["boss"])
    canonical = boss_preview(battle, actor.id)
    telegraph = boss_r6_telegraph(battle, actor.id)
    current = canonical["phase"]
    configured = {row["phase"]: row for row in director["phases"]}
    require(current in configured or not actor.alive,
            "Boss phase has no authored R37 presentation")
    current_presentation = configured.get(current)
    fired = set(battle.fired)
    phases = []
    for row in director["phases"]:
        phase = row["phase"]
        trigger = row["trigger"]
        if phase < current:
            status = "completed"
        elif phase == current:
            status = "active" if actor.alive else "defeated"
        elif trigger in fired:
            status = "trigger_fired"
        else:
            status = "possible"
        canonical_gate = next(
            (t for t in battle.mission.triggers if t["id"] == trigger), None)
        phases.append({
            "phase": phase, "label": row["label"], "cue": row["cue"],
            "trigger": trigger,
            "hp_gate_percent": canonical_gate["percent"] if trigger else None,
            "status": status,
            "certainty": ("observed" if status in (
                "completed", "active", "defeated", "trigger_fired")
                else "authored_possible"),
        })
    arrived = arrived_reinforcements(battle, actor)
    result = {
        "version": 1, "id": director["id"], "mission": director["mission"],
        "boss": actor.id, "tick": battle.tick,
        "current_phase": current, "hp_percent": canonical["hp_percent"],
        "current_label": (
            current_presentation["label"] if current_presentation else ""),
        "current_cue": (
            current_presentation["cue"] if current_presentation else ""),
        "phases": phases,
        "telegraph": telegraph,
        "queued_waves": deepcopy(telegraph["queued_waves"]),
        "possible_reinforcements": deepcopy(telegraph["reinforcements"]),
        "arrived_reinforcements": [
            {"actor_id": other.id, "pos": list(other.pos)}
            for other in arrived],
        "observed_phase_events": [
            {"tick": event["tick"], "phase": event["phase"]}
            for event in battle.events
            if event.get("kind") == "boss_phase"
            and event.get("unit") == actor.id],
        "preview_only": True,
    }
    result["digest"] = sha256(json.dumps(
        result, sort_keys=True, ensure_ascii=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    return result


__all__ = ["validate_boss_directors", "preview_boss_director",
           "MAX_DIRECTORS", "MAX_PHASES"]

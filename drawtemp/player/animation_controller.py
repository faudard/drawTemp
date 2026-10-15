"""R12.7 deterministic visual clips from committed R1 Simulation snapshots.

Presentation-only: no RNG draws, no Battle mutation, no fabricated hits.
The native gameplay event log is authoritative. Durations are visual budgets,
not action timers and never gate saving or combat progression.
"""
from collections.abc import Mapping

MAX_EVENTS = 100
MAX_CLIPS = 80
DURATIONS = {
    "move": 380, "attack": 270, "impact": 235, "heal": 260,
    "miss": 200, "cast": 290, "interrupt": 240,
}


def _unit_map(state):
    battle = getattr(state, "battle", None)
    return ({str(row["id"]): row for row in battle.get("units", ())}
            if battle is not None else {})


def _cell(value):
    if (not isinstance(value, (tuple, list)) or len(value) != 2 or
            type(value[0]) is not int or type(value[1]) is not int):
        return None
    return [value[0], value[1]]


def _clip(kind, actor, position, target=None, *, team="", amount=None, skill=""):
    origin = _cell(position)
    ending = _cell(target) if target is not None else origin
    if origin is None or ending is None:
        return None
    return {"kind": kind, "actor": str(actor), "team": team,
            "start": origin, "end": ending,
            "duration_ms": DURATIONS[kind],
            "amount": amount if type(amount) in (int, float) else None,
            "skill": str(skill)[:80] if skill else ""}


def compile_clips(before, after):
    """Build bounded clips only for a verified incremental battle journal.

    New game, load, mission switch, aborted/invalid commands, stale revision,
    or truncated/mismatched events: no playback, no stale visual state.
    """
    old = getattr(before, "battle", None)
    new = getattr(after, "battle", None)
    if (old is None or new is None or
            getattr(after, "revision", -1) <= getattr(before, "revision", -1) or
            old.get("mission_id") != new.get("mission_id")):
        return []
    past = old.get("events", ())
    now = new.get("events", ())
    if (not isinstance(past, (tuple, list)) or
            not isinstance(now, (tuple, list)) or
            len(now) < len(past) or tuple(now[:len(past)]) != tuple(past) or
            len(now) - len(past) > MAX_EVENTS):
        return []
    before_units, after_units = _unit_map(before), _unit_map(after)
    # Track position changes in event order, not through the final state alone.
    positions = {uid: _cell(row.get("pos")) for uid, row in before_units.items()}
    clips = []
    for event in now[len(past):]:
        if not isinstance(event, Mapping):
            continue
        kind = event.get("kind")
        actor = str(event.get("unit", ""))
        row = after_units.get(actor) or before_units.get(actor)
        current = positions.get(actor) or (_cell(row["pos"]) if row else None)
        team = str(row.get("team", "")) if row else ""
        clip = None
        if kind in {"move", "displace", "forced_move", "pursuit", "teleport"}:
            start = _cell(event.get("start")) or current
            end = (_cell(event.get("end")) or _cell(event.get("pos")) or
                   _cell(event.get("cell")))
            # "forced_move" and failed teleport can be emitted before outcome:
            # no end coordinate means no visible displacement is assumed.
            if start is not None and end is not None and start != end:
                clip = _clip("move", actor, start, end, team=team)
                positions[actor] = end
        elif kind in {"skill", "charge_started", "siege_attack", "item"}:
            destination = _cell(event.get("cell"))
            if current is not None:
                clip = _clip("attack" if kind != "item" else "cast",
                             actor, current, destination or current,
                             team=team, skill=event.get("skill", ""))
        elif kind == "cast_started":
            if current is not None:
                clip = _clip("cast", actor, current, team=team,
                             skill=event.get("skill", ""))
        elif kind == "damage":
            if current is not None:
                clip = _clip("impact", actor, current, team=team,
                             amount=event.get("amount"))
        elif kind == "heal":
            if current is not None:
                clip = _clip("heal", actor, current, team=team,
                             amount=event.get("amount"))
        elif kind in {"miss", "evade", "dodge"}:
            if current is not None:
                clip = _clip("miss", actor, current, team=team)
        elif kind in {"charge_interrupted", "cast_failed", "prepared_cancelled"}:
            if current is not None:
                clip = _clip("interrupt", actor, current, team=team)
        if clip:
            clips.append(clip)
            if len(clips) >= MAX_CLIPS:
                break
    # Some skills move the active actor without a dedicated "move" event.
    # Do not invent an animation path or extra damage: only animate logged facts.
    return clips


class AnimationDirector:
    """Generation invalidates in-flight QML clips on any committed scene transition."""

    def __init__(self):
        self._serial = 0
        self._plan = {"serial": 0, "revision": 0, "scene": "", "clips": []}

    def snapshot(self):
        from copy import deepcopy
        return deepcopy(self._plan)

    def update(self, before, after):
        self._serial += 1
        old_battle = getattr(before, "battle", None)
        new_battle = getattr(after, "battle", None)
        clips = compile_clips(before, after)
        self._plan = {
            "serial": self._serial,
            "revision": getattr(after, "revision", 0) if after else 0,
            "scene": new_battle["mission_id"] if new_battle else "",
            "clips": clips,
        }
        return self.snapshot()

    def cancel(self):
        self._serial += 1
        self._plan = {"serial": self._serial, "revision": 0,
                      "scene": "", "clips": []}
        return self.snapshot()

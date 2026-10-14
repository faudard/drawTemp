"""R7.19 — validated, immutable cinematic authoring operations.

All geometry and timelines remain ordinary GameProject.cinematics events.
This module contains no Tk widget, persistence shortcut or game-state command.
Callers commit one validated GameProject transaction per completed gesture.
"""
from copy import deepcopy

from .cinematics import motion_at
from .model import require

MAX_KEYFRAMES = 32


def _motion(event):
    require(event["kind"] in ("actor", "camera"),
            "Keyframes require an actor or camera event")


def _local(event, at_ms):
    require(type(at_ms) is int and 0 < at_ms < event["duration_ms"],
            "Keyframe must be strictly inside the event")


def add_motion_keyframe(event, at_ms):
    """Insert a key at the current evaluated pose, with no sudden jump."""
    _motion(event)
    _local(event, at_ms)
    result = deepcopy(event)
    keys = result.setdefault("keyframes", [])
    require(len(keys) < MAX_KEYFRAMES, "Too many motion keyframes")
    require(all(k["at_ms"] != at_ms for k in keys), "Duplicate keyframe time")
    pos, zoom = motion_at(result, result["start_ms"] + at_ms)
    key = {"at_ms": at_ms, "pos": list(pos)}
    if result["kind"] == "camera":
        key["zoom"] = zoom
    keys.append(key)
    keys.sort(key=lambda k: k["at_ms"])
    return result


def update_motion_keyframe(event, old_at_ms, *, at_ms=None, pos=None, zoom=None):
    """Edit an existing interior key in one transaction; do not touch neighbors."""
    _motion(event)
    result = deepcopy(event)
    keys = result.get("keyframes", [])
    key = next((k for k in keys if k["at_ms"] == old_at_ms), None)
    require(key is not None, "Unknown motion keyframe")
    new_at = old_at_ms if at_ms is None else at_ms
    _local(result, new_at)
    require(all(k is key or k["at_ms"] != new_at for k in keys),
            "Duplicate keyframe time")
    if pos is not None:
        require(isinstance(pos, (list, tuple)) and len(pos) == 2
                and all(type(v) in (int, float) and -2 <= v <= 2 for v in pos),
                "Invalid keyframe position")
        key["pos"] = list(pos)
    if zoom is not None:
        require(result["kind"] == "camera"
                and type(zoom) in (int, float) and .25 <= zoom <= 4,
                "Invalid camera keyframe zoom")
        key["zoom"] = zoom
    key["at_ms"] = new_at
    keys.sort(key=lambda k: k["at_ms"])
    return result


def remove_motion_keyframe(event, at_ms):
    _motion(event)
    result = deepcopy(event)
    keys = result.get("keyframes", [])
    require(any(k["at_ms"] == at_ms for k in keys), "Unknown motion keyframe")
    result["keyframes"] = [key for key in keys if key["at_ms"] != at_ms]
    if not result["keyframes"]:
        del result["keyframes"]
    return result


def move_event(event, start_ms, clip_duration):
    """Move an entire track, preserving duration and all interior key offsets."""
    require(type(start_ms) is int and 0 <= start_ms
            and start_ms + event["duration_ms"] <= clip_duration,
            "Event would leave the cinematic timeline")
    result = deepcopy(event)
    result["start_ms"] = start_ms
    return result


def resize_event(event, duration_ms, clip_duration):
    """Resize from the left edge; keyframes and sound fades remain valid."""
    require(type(duration_ms) is int and duration_ms > 0
            and event["start_ms"] + duration_ms <= clip_duration,
            "Invalid event duration")
    result = deepcopy(event)
    if result.get("keyframes"):
        # Fail rather than silently merging keys on a compressed timeline.
        mapped = [round(key["at_ms"] * duration_ms / event["duration_ms"])
                  for key in result["keyframes"]]
        require(all(type(t) is int and 0 < t < duration_ms for t in mapped)
                and len(set(mapped)) == len(mapped),
                "Resize collapses a motion keyframe")
        for key, new_time in zip(result["keyframes"], mapped):
            key["at_ms"] = new_time
    for fade in ("fade_in_ms", "fade_out_ms"):
        require(result.get(fade, 0) <= duration_ms,
                "Resize would truncate an audio fade")
    result["duration_ms"] = duration_ms
    return result


def clone_event(event, new_id, start_ms, clip_duration):
    require(type(new_id) is str and bool(new_id)
            and all(c.isalnum() or c in "_-" for c in new_id),
            "Invalid new cinematic event ID")
    return {**move_event(event, start_ms, clip_duration), "id": new_id}

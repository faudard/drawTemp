"""R7.20 — immutable multi-selection/clipboard commands for cinematic authoring.

Copy/paste is local to the Studio session and never touches OS clipboard,
GameSession or serialized GameProject schema. Every command returns new data:
the Studio must validate and commit it as *one* complete transaction.
"""
from copy import deepcopy

from .cinematic_authoring4 import move_event
from .model import RuleError, require

MAX_CLIPBOARD_EVENTS = 128


def selected_events(clip, ids):
    """Return selection in authoring order, rejecting missing/duplicate IDs."""
    require(isinstance(ids, (tuple, list)) and 0 < len(ids) <= MAX_CLIPBOARD_EVENTS,
            "Select between 1 and 128 cinematic events")
    require(all(isinstance(eid, str) and bool(eid) for eid in ids)
            and len(set(ids)) == len(ids), "Invalid cinematic selection")
    chosen = set(ids)
    result = [event for event in clip["events"] if event["id"] in chosen]
    require(len(result) == len(ids), "Selection contains a removed event")
    return result


def copy_events(clip, ids):
    """Deep-copy real events and retain relative authoring offsets."""
    events = selected_events(clip, ids)
    start = min(e["start_ms"] for e in events)
    return {"version": 1, "origin_clip": clip["id"],
            "events": deepcopy(events), "origin_ms": start}


def _clipboard_events(clipboard):
    require(isinstance(clipboard, dict)
            and set(clipboard) == {"version", "origin_clip", "events", "origin_ms"}
            and clipboard["version"] == 1
            and isinstance(clipboard["origin_clip"], str)
            and type(clipboard["origin_ms"]) is int
            and clipboard["origin_ms"] >= 0,
            "Invalid cinematic clipboard payload")
    events = clipboard["events"]
    require(isinstance(events, list) and 0 < len(events) <= MAX_CLIPBOARD_EVENTS
            and all(isinstance(e, dict) and type(e.get("start_ms")) is int
                    and type(e.get("duration_ms")) is int and
                    e.get("duration_ms", 0) > 0 and isinstance(e.get("id"), str)
                    for e in events),
            "Invalid cinematic clipboard events")
    require(len({e["id"] for e in events}) == len(events)
            and min(e["start_ms"] for e in events) == clipboard["origin_ms"],
            "Malformed cinematic clipboard origin")
    return events


def _unique_id(old_id, known):
    """Stay inside 64-character cinematic ID budget, deterministically."""
    root = old_id[:58] + "_copy"
    candidate = root
    suffix = 2
    while candidate in known:
        tail = str(suffix)
        candidate = root[:64-len(tail)] + tail
        suffix += 1
    known.add(candidate)
    return candidate


def paste_events(clip, clipboard, at_ms):
    """Paste all tracks atomically at cursor, preserving spacing and keyframes.

    Events get deterministic new IDs even when pasted into the source clip.
    Reject (rather than truncate) any clip that would overflow the target.
    """
    require(type(at_ms) is int and 0 <= at_ms <= clip["duration_ms"],
            "Paste position must be inside the cinematic")
    copied = _clipboard_events(clipboard)
    moved = []
    known = {e["id"] for e in clip["events"]}
    for event in copied:
        start = at_ms + event["start_ms"] - clipboard["origin_ms"]
        require(0 <= start and start+event["duration_ms"] <= clip["duration_ms"],
                "Paste would truncate an event at target cinematic boundary")
        duplicate = deepcopy(event)
        duplicate["start_ms"] = start
        duplicate["id"] = _unique_id(event["id"], known)
        moved.append(duplicate)
    result = deepcopy(clip)
    result["events"].extend(moved)
    return result, tuple(event["id"] for event in moved)


def shift_events(clip, ids, delta_ms):
    """Move selected clips together without clipping their relative offsets."""
    require(type(delta_ms) is int, "Timeline shift must be integer milliseconds")
    selected = selected_events(clip, ids)
    # Preflight *all* events: fail atomically if even one leaves the timeline.
    for event in selected:
        start = event["start_ms"] + delta_ms
        require(0 <= start and start+event["duration_ms"] <= clip["duration_ms"],
                "Group move would leave cinematic bounds")
    moving = {event["id"] for event in selected}
    result = deepcopy(clip)
    result["events"] = [
        move_event(event, event["start_ms"]+delta_ms, clip["duration_ms"])
        if event["id"] in moving else event for event in result["events"]
    ]
    return result


def delete_events(clip, ids):
    chosen = {event["id"] for event in selected_events(clip, ids)}
    result = deepcopy(clip)
    result["events"] = [event for event in result["events"]
                        if event["id"] not in chosen]
    return result

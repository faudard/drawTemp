"""R36.B2 portable, presentation-only animation marker tracks.

Markers are visual cues, *never* authoritative collision, damage, gameplay
events, or script callbacks. Times are integers measured against R28 clips.
Tick intervals are supplied by an already committed simulation, not Qt.
"""
from __future__ import annotations

from copy import deepcopy

from sporebound.animation_graph import (
    AnimationGraphError, _fail, _id, _shape, controllers_from_project,
)
from sporebound.assets import AssetRegistry

NAMESPACE = "org.drawtemp.animation.timeline"
VERSION = 1
MAX_TIMELINES = 16
MAX_TRACKS = 48
MAX_MARKERS = 32
MAX_MARKER_CUES = 128
CUES = frozenset(("spark", "dust", "trail", "glow"))


def validate_timeline(document, controller, registry):
    """Require typed cues aligned with existing controller states and R28 clips."""
    _shape(document, ("schema_version", "id", "controller_id", "tracks"), "timeline")
    if type(document["schema_version"]) is not int or document["schema_version"] != VERSION:
        _fail("timeline_version", "Unsupported visual timeline version")
    _id(document["id"], "timeline ID")
    _id(document["controller_id"], "linked controller ID")
    if document["controller_id"] != controller["id"]:
        _fail("timeline_controller", "Timeline refers to an unknown animation controller")
    tracks = document["tracks"]
    if type(tracks) is not list or not 1 <= len(tracks) <= MAX_TRACKS:
        _fail("timeline_track_budget", "Timeline requires 1..48 visual tracks")
    registry = registry if isinstance(registry, AssetRegistry) else AssetRegistry(registry)
    state_map = {s["id"]: s["animation"] for s in controller["states"]}
    seen_states = set()
    for track in tracks:
        _shape(track, ("state", "markers"), "timeline track")
        state = track["state"]
        if type(state) is not str or state not in state_map or state in seen_states:
            _fail("timeline_state", "Unknown or duplicated timeline state")
        seen_states.add(state)
        frames = registry.require_reference(state_map[state], "animation")["frames"]
        duration = sum(frame["duration_ms"] for frame in frames)
        markers = track["markers"]
        if type(markers) is not list or len(markers) > MAX_MARKERS:
            _fail("timeline_marker_budget", "Maximum 32 visual markers per state")
        seen_markers = set()
        for marker in markers:
            _shape(marker, ("id", "at_ms", "cue"), "visual cue")
            _id(marker["id"], "visual cue ID")
            if marker["id"] in seen_markers:
                _fail("timeline_duplicate_marker", "Duplicate visual cue ID")
            seen_markers.add(marker["id"])
            at_ms = marker["at_ms"]
            if type(at_ms) is not int or not 0 <= at_ms < duration:
                _fail("timeline_marker_time", "Visual cue must fall within the animation clip")
            if type(marker["cue"]) is not str or marker["cue"] not in CUES:
                _fail("timeline_cue", "Only bounded presentation cue kinds are supported")
    return deepcopy(document)


def timelines_from_project(project):
    """Read strictly validated optional R36 timeline extension on project load."""
    if hasattr(project, "to_dict"):
        project = project.to_dict()
    if type(project) is not dict:
        _fail("timeline_project", "Expected a GameProject document")
    extensions = project.get("extensions", {})
    if type(extensions) is not dict:
        _fail("timeline_extensions", "Project extensions must be a mapping")
    storage = extensions.get(NAMESPACE)
    if storage is None:
        return []
    if (type(storage) is not dict or set(storage) != {"schema_version", "data", "references"}
            or type(storage["schema_version"]) is not int or storage["schema_version"] != VERSION
            or storage["references"] != [] or type(storage["data"]) is not dict
            or set(storage["data"]) != {"timelines"} or
            type(storage["data"]["timelines"]) is not list):
        _fail("timeline_storage", "R36 timeline storage needs explicit migration")
    rows = storage["data"]["timelines"]
    if len(rows) > MAX_TIMELINES:
        _fail("timeline_budget", "At most 16 visual timelines")
    controllers = {c["id"]: c for c in controllers_from_project(project)}
    registry = AssetRegistry(project.get("assets") or None)
    values = []
    keys = set()
    assigned = set()
    for row in rows:
        if type(row) is not dict:
            _fail("timeline_shape", "Visual timeline must be a mapping")
        controller_id = row.get("controller_id")
        if type(controller_id) is not str or controller_id not in controllers:
            _fail("timeline_controller", "Dangling visual timeline controller ID")
        result = validate_timeline(row, controllers[controller_id], registry)
        if result["id"] in keys or result["controller_id"] in assigned:
            _fail("timeline_duplicate", "One visual timeline per controller, unique IDs")
        keys.add(result["id"])
        assigned.add(result["controller_id"])
        values.append(result)
    return values


def cues_crossed(document, controller, registry, *, state,
                 entered_tick, from_tick, to_tick, tick_rate=60):
    """Pure cue projection for a bounded range of *already committed* ticks.

    The caller provides the graph state and entry tick. No command is emitted
    into the simulation. The same committed tick interval always returns the
    same stable cue records, independent of renderer FPS.
    """
    timeline = validate_timeline(document, controller, registry)
    if (type(state) is not str or state not in {s["id"] for s in controller["states"]}):
        _fail("timeline_state", "Unknown animation state")
    if (any(type(value) is not int for value in
            (entered_tick, from_tick, to_tick, tick_rate)) or
            entered_tick < 0 or from_tick < entered_tick - 1 or
            to_tick < from_tick or to_tick - from_tick > 512 or
            not 1 <= tick_rate <= 240):
        _fail("timeline_tick", "Invalid committed tick interval or tick-rate budget")
    track = next((t for t in timeline["tracks"] if t["state"] == state), None)
    if track is None:
        return []
    registry = registry if isinstance(registry, AssetRegistry) else AssetRegistry(registry)
    animation_id = next(s["animation"] for s in controller["states"] if s["id"] == state)
    animation = registry.require_reference(animation_id, "animation")
    duration = sum(frame["duration_ms"] for frame in animation["frames"])
    result = []
    for tick in range(from_tick + 1, to_tick + 1):
        current = (tick - entered_tick) * 1000 // tick_rate
        previous = ((tick - 1 - entered_tick) * 1000 // tick_rate
                    if tick > entered_tick else -1)
        if not animation["loop"]:
            current = min(current, duration)
            previous = min(previous, duration)
        first_cycle = max(0, previous // duration)
        last_cycle = max(0, current // duration)
        for cycle in range(first_cycle, last_cycle + 1):
            if cycle and not animation["loop"]:
                continue
            for marker in track["markers"]:
                absolute = cycle * duration + marker["at_ms"]
                if previous < absolute <= current:
                    result.append({
                        "id": f'{timeline["id"]}:{state}:{marker["id"]}:{cycle}',
                        "tick": tick, "state": state, "cue": marker["cue"],
                        "offset_ms": marker["at_ms"], "cycle": cycle})
                    if len(result) > MAX_MARKER_CUES:
                        _fail("timeline_cue_budget", "Maximum 128 visible cues per query")
    return result

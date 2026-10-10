"""Validated, deterministic cinematic timeline. No Tk or battle dependencies."""
from copy import deepcopy
from dataclasses import dataclass

from .model import RuleError, require

KINDS = ("background", "actor", "camera", "dialogue", "fade", "sound")
TRIGGERS = ("campaign_start", "before_mission", "after_mission")
COLORS = ("#101a2b", "#243c56", "#f3dfbf", "#000000", "#ffffff")


def _id(value):
    return (isinstance(value, str) and 0 < len(value) <= 64
            and all(char.isalnum() or char in "_-" for char in value))


def _number(value, low, high):
    return type(value) in (int, float) and low <= value <= high


def _point(value):
    return (isinstance(value, list) and len(value) == 2
            and all(_number(x, -2, 2) for x in value))


def _color(value):
    return (isinstance(value, str) and len(value) == 7
            and value[0] == "#" and all(c in "0123456789abcdefABCDEF" for c in value[1:]))


def validate_cinematics(clips, content, campaigns):
    """Reject invalid / dangling authoring data before it reaches a save."""
    require(isinstance(clips, list) and len(clips) <= 128, "Cinematics must be a list (max 128)")
    ids = set()
    campaign_ids = {c["id"] for c in campaigns}
    mission_ids = set(content.missions)
    for clip in clips:
        require(isinstance(clip, dict) and set(clip) ==
                {"id", "name", "trigger", "duration_ms", "events"},
                "Cinematic needs id, name, trigger, duration_ms and events")
        require(_id(clip["id"]) and clip["id"] not in ids, "Duplicate / invalid cinematic id")
        ids.add(clip["id"])
        require(isinstance(clip["name"], str) and
                0 < len(clip["name"].strip()) <= 120, "Cinematic name must be 1..120 characters")
        require(type(clip["duration_ms"]) is int and
                500 <= clip["duration_ms"] <= 180000, "Cinematic duration must be 500..180000 ms")
        trigger = clip["trigger"]
        require(isinstance(trigger, dict) and set(trigger) == {"kind", "target"}
                and trigger["kind"] in TRIGGERS, "Invalid cinematic trigger")
        targets = campaign_ids if trigger["kind"] == "campaign_start" else mission_ids
        require(isinstance(trigger["target"], str) and trigger["target"] in targets,
                "Cinematic trigger refers to unknown campaign or mission")
        events = clip["events"]
        require(isinstance(events, list) and len(events) <= 256,
                "Cinematic timeline must be a list (max 256 events)")
        event_ids = set()
        for event in events:
            require(isinstance(event, dict), "Cinematic event must be an object")
            base = {"id", "kind", "start_ms", "duration_ms"}
            kind = event.get("kind")
            fields = {
                "background": {"color"},
                "actor": {"actor", "from", "to"},
                "camera": {"from", "to", "zoom_from", "zoom_to"},
                "dialogue": {"speaker", "text"},
                "fade": {"color"},
                "sound": {"cue"},
            }
            optional_audio = {
                "bus", "volume", "fade_in_ms", "fade_out_ms", "loop", "duck_percent"
            } if kind == "sound" else set()
            required = base | fields.get(kind, set())
            require(kind in KINDS and required <= set(event) <= required | optional_audio,
                    "Invalid fields for cinematic event")
            require(_id(event["id"]) and event["id"] not in event_ids,
                    "Duplicate / invalid cinematic event id")
            event_ids.add(event["id"])
            start, duration = event["start_ms"], event["duration_ms"]
            require(type(start) is int and type(duration) is int and
                    start >= 0 and duration > 0 and start + duration <= clip["duration_ms"],
                    "Cinematic event extends beyond the timeline")
            if kind in ("background", "fade"):
                require(_color(event["color"]), "Cinematic colors must be #RRGGBB")
            if kind in ("actor", "camera"):
                require(_point(event["from"]) and _point(event["to"]),
                        "Actor / camera positions must be [x,y] (normalized)")
            if kind == "actor":
                require(_id(event["actor"]), "Actor ID is required")
            if kind == "camera":
                require(_number(event["zoom_from"], .25, 4.0) and
                        _number(event["zoom_to"], .25, 4.0), "Camera zoom out of range")
            if kind == "dialogue":
                require(isinstance(event["speaker"], str) and len(event["speaker"]) <= 100
                        and isinstance(event["text"], str) and
                        0 < len(event["text"].strip()) <= 1600, "Dialogue text is required")
            if kind == "sound":
                require(_id(event["cue"]), "Sound cue ID is required")
                from .audio_timeline import BUSES
                bus = event.get("bus", "sfx")
                require(bus in BUSES, "Unknown cinematic audio bus")
                volume = event.get("volume", 100)
                require(type(volume) is int and 0 <= volume <= 100,
                        "Audio volume must be an integer 0..100")
                require(type(event.get("loop", False)) is bool,
                        "Audio loop must be boolean")
                for name in ("fade_in_ms", "fade_out_ms"):
                    fade = event.get(name, 0)
                    require(type(fade) is int and 0 <= fade <= duration,
                            f"{name} must be an integer 0..event duration")
                require("duck_percent" not in event or bus == "voice",
                        "Only voice events may duck music")
                if "duck_percent" in event:
                    duck = event["duck_percent"]
                    require(type(duck) is int and 0 <= duck <= 100,
                            "Voice duck percentage must be 0..100")


def matching_cinematics(project, kind, target):
    return [deepcopy(c) for c in project.cinematics
            if c["trigger"] == {"kind": kind, "target": target}]


def cinematic_template(cid, name, kind, target):
    return {"id": cid, "name": name,
            "trigger": {"kind": kind, "target": target},
            "duration_ms": 8000, "events": []}


def event_template(kind, eid, start_ms=0, duration_ms=1000):
    common = {"id": eid, "kind": kind, "start_ms": start_ms,
              "duration_ms": duration_ms}
    details = {
        "background": {"color": "#243c56"},
        "actor": {"actor": "jeanne", "from": [0.15, 0.65], "to": [0.65, 0.65]},
        "camera": {"from": [0., 0.], "to": [0., 0.], "zoom_from": 1., "zoom_to": 1.},
        "dialogue": {"speaker": "Jeanne", "text": "Notre histoire commence..."},
        "fade": {"color": "#000000"},
        "sound": {"cue": "cinematic"},
    }
    require(kind in details, "Unknown cinematic event type")
    return {**common, **deepcopy(details[kind])}


def _lerp(a, b, fraction):
    return a + (b - a) * fraction


def _progress(event, ms):
    return max(0., min(1., (ms - event["start_ms"]) / event["duration_ms"]))


@dataclass(frozen=True)
class CinematicFrame:
    time_ms: int
    background: str
    actors: tuple
    camera: tuple
    zoom: float
    dialogue: tuple | None
    fade: tuple | None
    sounds: tuple


def frame_at(clip, ms):
    """Seekable pure projection: stable irrespective of playback/tick frequency."""
    ms = max(0, min(clip["duration_ms"], int(ms)))
    events = sorted(enumerate(clip["events"]), key=lambda pair:
                    (pair[1]["start_ms"], pair[0]))
    background = "#101a2b"
    actors = {}
    camera = (0., 0.)
    zoom = 1.
    dialogue = None
    fade = None
    sounds = []
    for _, event in events:
        start = event["start_ms"]
        end = start + event["duration_ms"]
        if start > ms:
            continue
        kind = event["kind"]
        ratio = _progress(event, ms)
        if kind == "background" and ms < end:
            background = event["color"]
        elif kind == "actor":
            actors[event["actor"]] = (
                _lerp(event["from"][0], event["to"][0], ratio),
                _lerp(event["from"][1], event["to"][1], ratio))
        elif kind == "camera":
            camera = (_lerp(event["from"][0], event["to"][0], ratio),
                      _lerp(event["from"][1], event["to"][1], ratio))
            zoom = _lerp(event["zoom_from"], event["zoom_to"], ratio)
        elif kind == "dialogue" and ms < end:
            dialogue = (event["speaker"], event["text"])
        elif kind == "fade" and ms < end:
            fade = (event["color"], ratio)
        elif kind == "sound" and ms < end:
            sounds.append(event["cue"])
    return CinematicFrame(ms, background, tuple(sorted(actors.items())),
                          camera, zoom, dialogue, fade, tuple(sounds))

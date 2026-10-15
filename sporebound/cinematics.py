"""Validated, deterministic cinematic timeline. No Tk or battle dependencies."""
from copy import deepcopy
from dataclasses import dataclass

from .model import RuleError, require

KINDS = ("background", "actor", "camera", "dialogue", "fade", "sound", "fx")
FX_KINDS = ("fire", "smoke", "rain", "fog", "light", "camera_shake")
TRIGGERS = ("campaign_start", "before_mission", "after_mission", "scene", "tactical_event")
COLORS = ("#101a2b", "#243c56", "#f3dfbf", "#000000", "#ffffff")
EASINGS = ("linear", "ease_in", "ease_out", "ease_in_out", "step")
SHOT_TRANSITIONS = ("cut", "dissolve", "wipe")
EXPRESSIONS = ("neutral", "happy", "sad", "angry", "surprised", "determined")


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


def validate_cinematics(clips, content, campaigns, scenes=None):
    """Reject invalid / dangling authoring data before it reaches a save."""
    require(isinstance(clips, list) and len(clips) <= 128, "Cinematics must be a list (max 128)")
    ids = set()
    campaign_ids = {c["id"] for c in campaigns}
    mission_ids = set(content.missions)
    scene_ids = {scene["id"] for scene in (scenes or [])}
    # Exactly the existing mission trigger identities: never expose a second
    # script/event namespace or refer to a trigger that cannot be executed.
    tactical_ids = {
        f"{mission.id}/{trigger['id']}"
        for mission in content.missions.values()
        for trigger in mission.triggers
    }
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
        targets = (campaign_ids if trigger["kind"] == "campaign_start"
                   else scene_ids if trigger["kind"] == "scene"
                   else tactical_ids if trigger["kind"] == "tactical_event"
                   else mission_ids)
        require(isinstance(trigger["target"], str) and trigger["target"] in targets,
                "Cinematic trigger refers to unknown campaign, mission or scene")
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
                "fx": {"effect", "intensity", "seed", "at"},
            }
            optional_fields = {
                "actor": {"easing", "keyframes", "pose", "animation"},
                "camera": {"easing", "shot", "transition", "keyframes"},
                "fade": {"easing"},
                "dialogue": {"portrait", "expression", "chars_per_second"},
                "sound": {"bus", "volume", "volume_to", "fade_in_ms",
                          "fade_out_ms", "loop", "duck_percent"},
            }.get(kind, set())
            required = base | (fields[kind] if kind in KINDS else set())
            require(kind in KINDS and required <= set(event) <= required | optional_fields,
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
            if "easing" in event:
                require(event["easing"] in EASINGS, "Unknown cinematic easing")
            if kind == "actor":
                require(_id(event["actor"]), "Actor ID is required")
                if "pose" in event:
                    require(_id(event["pose"]), "Invalid actor pose ID")
                if "animation" in event:
                    require(_id(event["animation"]), "Invalid actor animation binding")
            if kind == "camera":
                require(_number(event["zoom_from"], .25, 4.0) and
                        _number(event["zoom_to"], .25, 4.0), "Camera zoom out of range")
                if "shot" in event:
                    require(_id(event["shot"]), "Invalid shot ID")
                if "transition" in event:
                    require(event["transition"] in SHOT_TRANSITIONS,
                            "Unknown shot transition")
            if "keyframes" in event:
                keys = event["keyframes"]
                require(kind in ("actor", "camera") and isinstance(keys, list)
                        and 1 <= len(keys) <= 32,
                        "Actor/camera keyframes must contain 1..32 interior keys")
                last = 0
                for key in keys:
                    fields = {"at_ms", "pos"}
                    if kind == "camera":
                        fields.add("zoom")
                    require(isinstance(key, dict) and set(key) == fields,
                            "Invalid motion keyframe fields")
                    at = key["at_ms"]
                    require(type(at) is int and last < at < duration,
                            "Keyframe timestamps must be strictly increasing")
                    require(_point(key["pos"]), "Invalid keyframe position")
                    if kind == "camera":
                        require(_number(key["zoom"], .25, 4.),
                                "Camera keyframe zoom out of range")
                    last = at
            if kind == "dialogue":
                require(isinstance(event["speaker"], str) and len(event["speaker"]) <= 100
                        and isinstance(event["text"], str) and
                        0 < len(event["text"].strip()) <= 1600, "Dialogue text is required")
                if "portrait" in event:
                    require(_id(event["portrait"]), "Invalid dialogue portrait")
                if "expression" in event:
                    require(event["expression"] in EXPRESSIONS, "Unknown facial expression")
                if "chars_per_second" in event:
                    cps = event["chars_per_second"]
                    require(type(cps) is int and 0 <= cps <= 120,
                            "Dialogue pacing must be 0..120 characters/second")
            if kind == "fx":
                require(event["effect"] in FX_KINDS, "Unknown cinematic effect")
                require(_number(event["intensity"], 0, 1),
                        "Effect intensity must be between 0 and 1")
                require(type(event["seed"]) is int and 0 <= event["seed"] <= 2147483647,
                        "Effect seed must be a nonnegative 32-bit integer")
                require(_point(event["at"]), "Effect location must be a normalized point")
            if kind == "sound":
                require(_id(event["cue"]), "Sound cue ID is required")
                from .audio_timeline import BUSES
                bus = event.get("bus", "sfx")
                require(bus in BUSES, "Unknown cinematic audio bus")
                for name in ("volume", "volume_to"):
                    if name in event:
                        volume = event[name]
                        require(type(volume) is int and 0 <= volume <= 100,
                                f"{name} must be an integer 0..100")
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


def tactical_event_target(mission_id, event_id):
    """Stable fully-qualified tactical event identity in the project manifest."""
    return f"{mission_id}/{event_id}"


def triggered_tactical_cinematics(project, battle, acknowledged=()):
    """Return newly fired clips in engine order, with a new acknowledgement set.

    Pure projection: does not change the Battle, its replay/save, or GameProject.
    The Player controls presentation and when to acknowledge a visible cue.
    """
    seen = set(acknowledged)
    fresh = [eid for eid in battle.fired if eid not in seen]
    clips = [
        clip
        for event_id in fresh
        for clip in matching_cinematics(
            project, 'tactical_event',
            tactical_event_target(battle.mission.id, event_id))
    ]
    return clips, seen | set(battle.fired)


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
        "fx": {"effect": "fire", "intensity": .7, "seed": 1,
               "at": [.5, .55]},
    }
    require(kind in details, "Unknown cinematic event type")
    return {**common, **deepcopy(details[kind])}


def _lerp(a, b, fraction):
    # An authored keyframe boundary is an exact pose, not a rounded blend.
    if fraction <= 0:
        return a
    if fraction >= 1:
        return b
    return a + (b - a) * fraction


def _ease(ratio, easing):
    if easing == "ease_in":
        return ratio * ratio
    if easing == "ease_out":
        return 1 - (1 - ratio) ** 2
    if easing == "ease_in_out":
        return ratio * ratio * (3 - 2 * ratio)
    if easing == "step":
        return 1. if ratio >= 1. else 0.
    return ratio


def _progress(event, ms):
    ratio = max(0., min(1., (ms - event["start_ms"]) / event["duration_ms"]))
    return _ease(ratio, event.get("easing", "linear"))


def motion_at(event, ms):
    """Pure piecewise motion evaluation (also used by the visual keyframe editor).

    No keyframes means exact legacy interpolation. New keys subdivide the
    authored start/end range, preserving both boundary poses.
    """
    from_pos, to_pos = event["from"], event["to"]
    zoom_from = event.get("zoom_from")
    zoom_to = event.get("zoom_to")
    local = max(0, min(event["duration_ms"], int(ms) - event["start_ms"]))
    stops = [(0, from_pos, zoom_from)]
    stops.extend((key["at_ms"], key["pos"], key.get("zoom"))
                 for key in event.get("keyframes", ()))
    stops.append((event["duration_ms"], to_pos, zoom_to))
    left, right = stops[0], stops[-1]
    for index in range(len(stops) - 1):
        if local <= stops[index + 1][0]:
            left, right = stops[index], stops[index + 1]
            break
    length = right[0] - left[0]
    # _progress also applies the legacy easing curve; normalize to this segment.
    ratio = _ease(max(0., min(1., (local - left[0]) / length)),
                  event.get("easing", "linear"))
    pos = (_lerp(left[1][0], right[1][0], ratio),
           _lerp(left[1][1], right[1][1], ratio))
    zoom = (_lerp(left[2], right[2], ratio)
            if event["kind"] == "camera" else None)
    return pos, zoom


@dataclass(frozen=True)
class DialoguePresentation:
    portrait: str
    expression: str
    visible_text: str
    progress: float


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
    dialogue_presentation: DialoguePresentation | None = None
    shot: str | None = None
    shot_transition: tuple | None = None


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
    presentation = None
    shot = None
    shot_transition = None
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
            actors[event["actor"]] = motion_at(event, ms)[0]
        elif kind == "camera":
            camera, zoom = motion_at(event, ms)
            shot = event.get("shot")
            # The opening quarter of a shot may use a presentation transition.
            # A seek projects the same visual regardless of playback history.
            transition = event.get("transition", "cut")
            phase = min(1., max(0., (ms - start) / max(1, event["duration_ms"] / 4)))
            shot_transition = ((transition, phase)
                               if transition != "cut" and ms < end and phase < 1
                               else None)
        elif kind == "dialogue" and ms < end:
            dialogue = (event["speaker"], event["text"])
            cps = event.get("chars_per_second", 0)
            visible = (event["text"] if not cps else
                       event["text"][:min(len(event["text"]),
                                           int((ms - start) * cps / 1000))])
            presentation = DialoguePresentation(
                event.get("portrait", ""), event.get("expression", "neutral"),
                visible, round((ms - start) / event["duration_ms"], 6))
        elif kind == "fade" and ms < end:
            fade = (event["color"], ratio)
        elif kind == "sound" and ms < end:
            sounds.append(event["cue"])
    return CinematicFrame(ms, background, tuple(sorted(actors.items())),
                          camera, zoom, dialogue, fade, tuple(sounds),
                          presentation, shot, shot_transition)


def effects_at(clip, ms):
    """Deterministic optional FX projection without changing legacy frame hashes.

    FX belong to the presentation plane. Old CinematicFrame fields and
    canonical signature remain untouched, including for old save/replay QA.
    """
    ms = max(0, min(clip["duration_ms"], int(ms)))
    return tuple(
        (event["effect"], event["intensity"], event["seed"],
         tuple(event["at"]),
         round((ms - event["start_ms"]) / event["duration_ms"], 6))
        for event in clip["events"]
        if event["kind"] == "fx" and
        event["start_ms"] <= ms < event["start_ms"] + event["duration_ms"]
    )

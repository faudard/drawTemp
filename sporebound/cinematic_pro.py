"""R46.A — opt-in logical cues on the *existing* R11 cinematic timeline.

The canonical cinematic and its timestamps remain GameProject.cinematics.
Only typed, side-effecting cue bindings live in the versioned project
extension. There is no second timeline, clock, renderer or save file.

GameSession is the sole owner of CinematicProRuntime and its progress. A
presentation-only seek never changes gameplay; advancing or skipping commits
unapplied cues in stable (event start, event ID) order. Checkpoints include
both the cursor and the once-only ledger.
"""
from __future__ import annotations

from copy import deepcopy

from .model import require

EXTENSION = "drawtemp.cinematicpro"
VERSION = 1
MAX_CUES = 256


def _identifier(value):
    return (type(value) is str and 0 < len(value) <= 64
            and all(char.isalnum() or char in "_-" for char in value))


def validate_cinematic_pro(data, cinematics):
    """Validate opt-in bindings against canonical, already-validated R11 clips.

    Binds by existing event ID; a second authorable timestamp would introduce
    divergent timelines and is deliberately forbidden. Only boolean set_flag
    is enabled in R46.A; game commands/choices are reserved for later gates.
    """
    require(type(data) is dict and set(data) == {"version", "cues"}
            and type(data["version"]) is int and data["version"] == VERSION
            and type(data["cues"]) is list and len(data["cues"]) <= MAX_CUES,
            "Unsupported R46 cinematic cue schema")
    clips = {clip["id"]: clip for clip in cinematics}
    seen = set()
    for cue in data["cues"]:
        require(type(cue) is dict and set(cue) == {"clip", "event", "effect"},
                "Invalid R46 cue fields")
        cid, eid = cue["clip"], cue["event"]
        require(_identifier(cid) and cid in clips and _identifier(eid),
                "R46 cue references unknown cinematic")
        require(any(event["id"] == eid for event in clips[cid]["events"]),
                "R46 cue references unknown timeline event")
        require((cid, eid) not in seen, "Duplicate R46 logical cue binding")
        seen.add((cid, eid))
        effect = cue["effect"]
        require(type(effect) is dict and set(effect) == {"kind", "flag", "value"}
                and effect["kind"] == "set_flag"
                and _identifier(effect["flag"]) and type(effect["value"]) is bool,
                "Unsupported R46 logical effect")
    return deepcopy(data)


class CinematicProRuntime:
    """Headless logical cursor/ledger, always owned by a GameSession.

    The external Player/Studio use R11's frame_at()/audio_payload() to render
    at position_ms. They must not apply logical effects during a redraw.
    """

    def __init__(self, project):
        spec = project.extensions[EXTENSION]
        self.data = validate_cinematic_pro(spec["data"], project.cinematics)
        self.clips = {clip["id"]: deepcopy(clip) for clip in project.cinematics}
        self._cues = {}
        for cid, clip in self.clips.items():
            starts = {event["id"]: event["start_ms"] for event in clip["events"]}
            cues = [(starts[cue["event"]], cue["event"], deepcopy(cue["effect"]))
                    for cue in self.data["cues"] if cue["clip"] == cid]
            self._cues[cid] = tuple(sorted(cues, key=lambda row: (row[0], row[1])))
        self._valid_tokens = {
            cid + "/" + eid for cid, cues in self._cues.items()
            for _, eid, _ in cues
        }
        self.clip_id = ""
        self.position_ms = 0
        self.playing = False
        self.applied = set()

    def _active(self):
        require(self.clip_id in self.clips, "No active R46 cinematic")
        return self.clips[self.clip_id]

    def _commit(self, progress, start_ms, end_ms, *, include_zero=False,
                include_missed=False):
        require(type(progress.story_flags) is dict,
                "R46 effects require canonical campaign flags")
        pending = []
        for at, eid, effect in self._cues[self.clip_id]:
            token = self.clip_id + "/" + eid
            if token in self.applied:
                continue
            if ((include_missed and at <= end_ms)
                    or (start_ms < at <= end_ms)
                    or (include_zero and at == 0)):
                pending.append((token, effect))
        # Validation precedes mutations and R46.A only supports total,
        # non-throwing boolean assignments to canonical campaign flags.
        for token, effect in pending:
            progress.story_flags[effect["flag"]] = effect["value"]
            self.applied.add(token)
        return tuple(token for token, _ in pending)

    def start(self, clip_id, progress):
        require(type(clip_id) is str and clip_id in self.clips,
                "Unknown R46 cinematic")
        require(not self.clip_id or
                self.position_ms == self.clips[self.clip_id]["duration_ms"],
                "Finish or skip the current cinematic before starting another")
        self.clip_id = clip_id
        self.position_ms = 0
        self.playing = True
        return self._commit(progress, -1, 0, include_zero=True)

    def advance(self, elapsed_ms, progress):
        """Advance logical time; caller supplies *integer* simulation elapsed ms."""
        self._active()
        require(type(elapsed_ms) is int and elapsed_ms >= 0,
                "R46 advance requires nonnegative integer milliseconds")
        require(self.playing, "R46 cinematic is paused")
        old = self.position_ms
        self.position_ms = min(self._active()["duration_ms"], old + elapsed_ms)
        committed = self._commit(progress, old, self.position_ms)
        if self.position_ms == self._active()["duration_ms"]:
            self.playing = False
        return committed

    def pause(self):
        self._active()
        self.playing = False
        return self.position_ms

    def resume(self):
        clip = self._active()
        require(self.position_ms < clip["duration_ms"], "R46 cinematic ended")
        self.playing = True
        return self.position_ms

    def seek(self, position_ms):
        """Presentation scrub. Does NOT execute effects or reverse the ledger."""
        clip = self._active()
        require(type(position_ms) is int and
                0 <= position_ms <= clip["duration_ms"],
                "R46 seek is outside the canonical clip")
        self.position_ms = position_ms
        if position_ms == clip["duration_ms"]:
            self.playing = False
        return self.position_ms

    def skip(self, progress):
        """Resolve even cues bypassed by seeks, once each, then end the clip."""
        clip = self._active()
        committed = self._commit(
            progress, -1, clip["duration_ms"], include_missed=True)
        self.position_ms = clip["duration_ms"]
        self.playing = False
        return committed

    def snapshot(self):
        return {"version": VERSION, "clip": self.clip_id,
                "position_ms": self.position_ms, "playing": self.playing,
                "applied": sorted(self.applied)}

    def restore(self, record):
        require(type(record) is dict and
                set(record) == {"version", "clip", "position_ms", "playing", "applied"}
                and type(record["version"]) is int and record["version"] == VERSION,
                "Invalid R46 cinematic checkpoint schema")
        cid = record["clip"]
        require(type(cid) is str and (not cid or cid in self.clips),
                "Invalid R46 checkpoint clip")
        limit = self.clips[cid]["duration_ms"] if cid else 0
        position = record["position_ms"]
        playing = record["playing"]
        require(type(position) is int and 0 <= position <= limit
                and type(playing) is bool
                and (not playing or (cid and position < limit)),
                "Invalid R46 checkpoint cursor")
        applied = record["applied"]
        require(type(applied) is list and len(applied) <= MAX_CUES
                and all(type(token) is str for token in applied)
                and applied == sorted(set(applied))
                and set(applied) <= self._valid_tokens,
                "Invalid R46 checkpoint effect ledger")
        self.clip_id = cid
        self.position_ms = position
        self.playing = playing
        self.applied = set(applied)
        return self.snapshot()

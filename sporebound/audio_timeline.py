"""Deterministic cinematic audio envelopes and a playback-only track director.

The pure mix can be tested without a sound card or Tk. The director issues
transport commands only; it never mutates scene, campaign or tactical state.
"""
from dataclasses import dataclass


BUSES = ("music", "ambience", "voice", "sfx")


@dataclass(frozen=True)
class MixedTrack:
    event_id: str
    cue: str
    bus: str
    level: float
    loop: bool


def is_track(event):
    """Older cinematic 'sound' events keep their one-shot cue semantics."""
    return event["kind"] == "sound" and any(
        key in event for key in ("bus", "volume", "loop", "fade_in_ms",
                                  "fade_out_ms", "duck_percent"))


def _envelope(event, now):
    elapsed = now - event["start_ms"]
    remaining = event["start_ms"] + event["duration_ms"] - now
    factor = 1.0
    if event.get("fade_in_ms", 0):
        factor = min(factor, max(0., elapsed / event["fade_in_ms"]))
    if event.get("fade_out_ms", 0):
        factor = min(factor, max(0., remaining / event["fade_out_ms"]))
    return max(0., factor)


def mix_at(clip, time_ms):
    """Return the per-track gain at a timeline instant (0..1), ordered by event.

    Voices attenuate music by their authored duck percentage. Overlapping
    voices use the strongest reduction; fade edges modulate ducking smoothly.
    """
    now = max(0, min(clip["duration_ms"], int(time_ms)))
    audio = [
        e for e in clip["events"]
        if is_track(e) and e["start_ms"] <= now <
        e["start_ms"] + e["duration_ms"]
    ]
    duck = 1.
    for e in audio:
        if e.get("bus", "sfx") == "voice":
            limit = e.get("duck_percent", 40) / 100
            envelope = _envelope(e, now)
            duck = min(duck, 1 - (1 - limit) * envelope)
    tracks = []
    for e in audio:
        bus = e.get("bus", "sfx")
        # R7.15: authored level automation is a pure function of playhead time.
        # The legacy volume-only track remains bit-for-bit unchanged.
        start = e.get("volume", 100)
        end = e.get("volume_to", start)
        ratio = (now - e["start_ms"]) / e["duration_ms"]
        gain = ((start + (end - start) * ratio) / 100) * _envelope(e, now)
        if bus == "music":
            gain *= duck
        tracks.append(MixedTrack(
            e["id"], e["cue"], bus, round(gain, 6),
            e.get("loop", False)))
    return tuple(tracks)


class CinematicAudioDirector:
    """Transitions from the playhead without replaying old one-shot sounds.

    `advance` handles [old,new] crossings; `seek` reconstructs sustained
    tracks without playing historical SFX. A missing audio backend is safe.
    """
    def __init__(self, clip, stage=None):
        self.clip = clip
        self.stage = stage
        self.position = -1
        self._active = set()
        self._played = set()
        if stage is not None:
            stage.music(None)

    def advance(self, now):
        now = max(0, min(self.clip["duration_ms"], int(now)))
        if now < self.position:
            return self.seek(now)
        self._render(now, fire_cues=True)
        self.position = now

    def _render(self, now, *, fire_cues):
        if self.stage is None:
            return
        tracks = mix_at(self.clip, now)
        desired = {t.event_id for t in tracks}
        for eid in sorted(self._active - desired):
            self.stage.stop_track(eid)
        self._active.intersection_update(desired)
        if fire_cues:
            for event in self.clip["events"]:
                if (event["kind"] == "sound" and not is_track(event)
                        and event["id"] not in self._played
                        and self.position < event["start_ms"] <= now):
                    self.stage.cue(event["cue"])
                    self._played.add(event["id"])
        for track in tracks:
            if track.event_id not in self._active:
                # A seek into a sustained loop can start it at its beginning.
                self.stage.play_track(track.event_id, track.cue, bus=track.bus,
                                      loop=track.loop)
                self._active.add(track.event_id)
            self.stage.set_track_level(track.event_id, track.level)

    def seek(self, now):
        now = max(0, min(self.clip["duration_ms"], int(now)))
        self.stop()
        # Do not retroactively emit one-shots on a seek.
        self.position = now
        self._played = {e["id"] for e in self.clip["events"]
                        if e["kind"] == "sound" and not is_track(e)
                        and e["start_ms"] <= now}
        self._render(now, fire_cues=False)

    def pause(self):
        if self.stage is not None:
            self.stage.pause_tracks()

    def resume(self):
        if self.stage is not None:
            self.stage.resume_tracks()

    def restart(self):
        self.stop()
        self.position = -1
        self._played.clear()
        self.advance(0)

    def stop(self):
        if self.stage is not None:
            for eid in sorted(self._active):
                self.stage.stop_track(eid)
        self._active.clear()

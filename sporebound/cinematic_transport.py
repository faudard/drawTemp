"""Wall-clock cinematic transport: timing only, no Tk, mixer or game state.

Tk after() controls repaint *frequency*, not the simulated time. Repaints can
be delayed during asset decoding, window resizing or OS scheduling; audio and
visual projections must still read the same monotonic playhead.
"""
import time

from .model import require


class CinematicTransport:
    """Deterministic playhead state with an injectable monotonic clock."""

    def __init__(self, duration_ms, *, monotonic=None):
        require(type(duration_ms) is int and duration_ms > 0,
                "Cinematic duration must be positive")
        self.duration_ms = duration_ms
        self._now = monotonic if monotonic is not None else time.monotonic
        self.position_ms = 0
        self.playing = True
        self._anchor = self._now()

    def read(self):
        if self.playing:
            elapsed = max(0, int((self._now() - self._anchor) * 1000))
            self.position_ms = min(self.duration_ms, self.position_ms + elapsed)
            self._anchor = self._now_anchor()  # do not accumulate per-frame rounding
        return self.position_ms

    def _now_anchor(self):
        # Preserve fractional milliseconds by measuring from an origin
        # representing the *integer* committed playhead, not by adding 40 ms.
        return self._now()

    def pause(self):
        position = self.read()
        self.playing = False
        return position

    def resume(self):
        if not self.playing:
            self._anchor = self._now()
            self.playing = True
        return self.position_ms

    def seek(self, position_ms):
        require(type(position_ms) is int, "Cinematic seek must be in milliseconds")
        self.position_ms = max(0, min(self.duration_ms, position_ms))
        self._anchor = self._now()
        return self.position_ms

    def restart(self):
        self.seek(0)
        self.playing = True
        return 0

    def checkpoint(self):
        return {"time_ms": self.read(), "playing": self.playing}

    def restore(self, checkpoint):
        require(isinstance(checkpoint, dict) and
                set(checkpoint) == {"time_ms", "playing"} and
                type(checkpoint["time_ms"]) is int and
                0 <= checkpoint["time_ms"] <= self.duration_ms and
                type(checkpoint["playing"]) is bool,
                "Invalid cinematic playback checkpoint")
        self.seek(checkpoint["time_ms"])
        self.playing = checkpoint["playing"]
        return self.position_ms

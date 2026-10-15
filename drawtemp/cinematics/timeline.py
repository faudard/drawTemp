"""R11 timeline coordinate and snapping contract, independent of Qt and the Player.

All gestures are previews until release; the canonical GameProject is committed
only via CinematicDocument, never from a pointer-move event.
"""
from dataclasses import dataclass

from sporebound.model import require


@dataclass(frozen=True)
class TimelineScale:
    duration_ms: int
    origin_x: float = 130.0
    width_px: float = 920.0
    snap_ms: int = 100

    def __post_init__(self):
        require(type(self.duration_ms) is int and self.duration_ms > 0,
                "Timeline duration must be a positive integer")
        require(self.width_px > 0 and self.snap_ms > 0,
                "Timeline width and grid must be positive")

    def time_to_x(self, time_ms):
        return self.origin_x + self.width_px * (time_ms / self.duration_ms)

    def x_to_time(self, x):
        return round((x - self.origin_x) * self.duration_ms / self.width_px)

    def width_for(self, duration_ms):
        return self.width_px * duration_ms / self.duration_ms

    def _quantize(self, value):
        # Avoid Python round() ties-to-even for timeline snapping.
        return int((value + self.snap_ms / 2) // self.snap_ms) * self.snap_ms

    def absolute(self, x, event_duration):
        """Clamped snapped event start, no event can escape the clip."""
        require(type(event_duration) is int and 0 < event_duration <= self.duration_ms,
                "Invalid event duration")
        max_start = self.duration_ms - event_duration
        return min(max_start, max(0, self._quantize(self.x_to_time(x))))

    def local_key(self, x, event_start, event_duration):
        """Strict interior local key time, preserving canonical key constraints."""
        require(type(event_start) is int and type(event_duration) is int
                and event_duration >= 2, "Motion needs at least 2 ms")
        absolute = self.x_to_time(x)
        snapped = self._quantize(absolute)
        return min(event_duration - 1, max(1, snapped - event_start))

    def seek(self, x):
        return min(self.duration_ms, max(0, self.x_to_time(x)))

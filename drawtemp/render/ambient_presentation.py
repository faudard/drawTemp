"""R52.B: safe, deterministic camera and ambient-daylight presentation controls.

Light tint is a flat scene overlay, NOT a lightmap, physical lights or
per-pixel shadows. Nothing here changes Core simulation or saved GameSession.
"""
from collections.abc import Mapping
from math import isfinite
import re


LIGHTING_VERSION = 1
MAX_TRANSITION_MS = 60000
_HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")

_PRESETS = (
    {"id": "iso-wide", "title": "Isométrique — large", "mode": "isometric", "zoom": 0.7},
    {"id": "iso-close", "title": "Isométrique — proche", "mode": "isometric", "zoom": 1.35},
    {"id": "top-wide", "title": "Top-down — large", "mode": "top_down", "zoom": 0.8},
    {"id": "top-close", "title": "Top-down — proche", "mode": "top_down", "zoom": 1.5},
    {"id": "side-preview", "title": "Side — bandes 2.5D",
     "mode": "side", "zoom": 1.0},
    {"id": "side-close", "title": "Side — proche",
     "mode": "side", "zoom": 1.5},
)

_DEFAULT = {
    "version": LIGHTING_VERSION, "dayTint": "#ffffff",
    "nightTint": "#10224c", "dayOpacity": 0.0,
    "nightOpacity": 0.52, "phase": 0.0,
}


def _finite(value, name, low=0.0, high=1.0):
    if type(value) not in (int, float) or not isfinite(value) or not low <= value <= high:
        raise ValueError("%s must be finite in [%s,%s]" % (name, low, high))
    return float(value)


def normalize_lighting_profile(value=None):
    """Reject additional, malformed, or unsafe values before applying a draft."""
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise ValueError("Lighting profile must be an object")
    if set(value) - set(_DEFAULT):
        raise ValueError("Unknown lighting profile fields")
    result = dict(_DEFAULT)
    result.update(value)
    if type(result["version"]) is not int or result["version"] != LIGHTING_VERSION:
        raise ValueError("Unsupported lighting profile version")
    for name in ("dayTint", "nightTint"):
        color = result[name]
        if not isinstance(color, str) or not _HEX.fullmatch(color):
            raise ValueError("Lighting colors must be #RRGGBB")
        result[name] = color.lower()
    for name in ("phase", "dayOpacity", "nightOpacity"):
        result[name] = _finite(result[name], name)
    return result


def camera_presets(mode):
    """Describe side preview but never mark it as supported for actual picking."""
    if mode not in ("isometric", "top_down", "side"):
        raise ValueError("Unsupported active camera")
    return [dict(item, enabled=(item["mode"] == mode),
                 reason=("" if item["mode"] == mode
                         else "projection-or-picking-not-available"))
            for item in _PRESETS]


def resolve_camera_preset(identifier, mode):
    """Only change zoom within an existing R3 projection (no renderer switch)."""
    for candidate in camera_presets(mode):
        if candidate["id"] == identifier:
            if not candidate["enabled"]:
                raise ValueError("Camera preset requires a different certified projection")
            return dict(candidate)
    raise ValueError("Unknown camera preset")


def _rgb(color):
    return [int(color[i:i + 2], 16) for i in (1, 3, 5)]


def sample_lighting(profile, phase):
    """Interpolated scene tint; no gameplay clock, random input or asset access."""
    t = _finite(phase, "phase")
    start, end = _rgb(profile["dayTint"]), _rgb(profile["nightTint"])
    mixed = [round(a + (b - a) * t) for a, b in zip(start, end)]
    return {
        "color": "#%02x%02x%02x" % tuple(mixed),
        "opacity": profile["dayOpacity"] + (
            profile["nightOpacity"] - profile["dayOpacity"]) * t,
        "phase": t,
    }


class AmbientTransition:
    """Presentation-only fixed-step interpolator; not an R25 gameplay tick."""

    def __init__(self, phase=0.0):
        self.phase = _finite(phase, "phase")
        self.active = False
        self._start = self.phase
        self._target = self.phase
        self._elapsed = 0
        self._duration = 0

    def reset(self, phase):
        self.phase = _finite(phase, "phase")
        self.active = False

    def start(self, target, duration_ms):
        target = _finite(target, "target")
        if type(duration_ms) is not int or not 0 <= duration_ms <= MAX_TRANSITION_MS:
            raise ValueError("Duration must be an integer in [0,60000]ms")
        self._start = self.phase
        self._target = target
        self._duration = duration_ms
        self._elapsed = 0
        self.active = duration_ms > 0 and self._start != target
        if not self.active:
            self.phase = target
        return self.active

    def advance(self, elapsed_ms):
        if type(elapsed_ms) is not int or not 1 <= elapsed_ms <= 1000:
            raise ValueError("Presentation delta must be an integer in [1,1000]ms")
        if not self.active:
            return self.phase
        self._elapsed = min(self._duration, self._elapsed + elapsed_ms)
        t = self._elapsed / self._duration
        ease = t * t * (3 - 2 * t)
        self.phase = self._start + (self._target - self._start) * ease
        if self._elapsed >= self._duration:
            self.phase = self._target
            self.active = False
        return self.phase

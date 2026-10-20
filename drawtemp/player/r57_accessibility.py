"""R57.C persistent presentation-only accessibility preferences for Qt Player.

Deliberately independent from PlayerPreferences v1 and GameSession checkpoints.
A bad or incompatible file is not overwritten without retaining evidence.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile


class AccessibilityError(ValueError):
    """A persisted accessibility setting is invalid or cannot be loaded safely."""


LANGUAGES = ("fr", "en", "qps-ploc", "qps-plocm")
FIELDS = frozenset({"language", "subtitle_scale", "reduce_motion", "reduce_flashes"})


def defaults(language="fr"):
    if language not in ("fr", "en"):
        raise AccessibilityError("Unsupported project source language")
    return {
        "version": 1,
        "language": language,
        "subtitle_scale": 1.0,
        "reduce_motion": False,
        "reduce_flashes": False,
    }


def validate(data):
    if type(data) is not dict or set(data) != FIELDS | {"version"}:
        raise AccessibilityError("Invalid accessibility settings document")
    if type(data["version"]) is not int or data["version"] != 1:
        raise AccessibilityError("Unsupported accessibility settings version")
    if type(data["language"]) is not str or data["language"] not in LANGUAGES:
        raise AccessibilityError("Language must be fr, en or a supported pseudo-locale")
    value = data["subtitle_scale"]
    if type(value) not in (int, float) or not 1.0 <= value <= 2.0:
        raise AccessibilityError("Subtitle scale must be in 1.0..2.0")
    for key in ("reduce_motion", "reduce_flashes"):
        if type(data[key]) is not bool:
            raise AccessibilityError(key + " must be boolean")
    return data


class AccessibilityPreferences:
    """Detached, atomic local UI preferences; one per Player save directory."""

    def __init__(self, path, *, default_language="fr"):
        self.path = Path(path)
        self._data = defaults(default_language)
        self.warning = ""
        self._invalid = False
        if self.path.is_symlink():
            self.warning = "Accessibility preferences symlink refused"
            self._invalid = True
        elif self.path.exists():
            try:
                if not self.path.is_file() or self.path.stat().st_size > 16384:
                    raise AccessibilityError("Invalid/oversized accessibility preferences")
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                validate(loaded)
            except (OSError, ValueError, UnicodeError, TypeError, KeyError) as exc:
                self.warning = "Invalid accessibility preferences: " + str(exc)
                self._invalid = True
            else:
                self._data = loaded

    def view(self):
        return deepcopy(self._data)

    def update(self, key, value):
        if key not in FIELDS:
            raise AccessibilityError("Unknown accessibility option")
        candidate = self.view()
        candidate[key] = value
        validate(candidate)
        self._persist(candidate)
        self._data = candidate
        self._invalid = False
        self.warning = ""
        return self.view()

    def _persist(self, candidate):
        if self.path.is_symlink():
            raise AccessibilityError("Symlinked preferences cannot be modified")
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        if self._invalid and self.path.exists():
            saved = self.path.with_name(self.path.name + ".invalid")
            if saved.exists() or saved.is_symlink():
                raise AccessibilityError("A previous invalid preferences backup exists")
            with saved.open("xb") as output:
                output.write(self.path.read_bytes())
                output.flush()
                os.fsync(output.fileno())
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=parent,
                    prefix=".r57-a11y-", suffix=".tmp", delete=False) as output:
                temp_path = Path(output.name)
                json.dump(candidate, output, ensure_ascii=False,
                          sort_keys=True, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp_path, self.path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


def presentation_animation(plan, accessibility):
    """Filter playback visuals only, preserving engine event/revision history."""
    if not accessibility["reduce_motion"]:
        return plan
    from copy import deepcopy as detach
    result = detach(plan)
    result["clips"] = []
    return result


def filtered_cinematic_frame(frame, accessibility):
    """Do not introduce flashing/light or camera shake into visual output.

    Only the detached frame projection changes; canonical cinematic timing
    and the GameSession's next-action conditions are untouched.
    """
    result = deepcopy(frame)
    if accessibility["reduce_motion"] or accessibility["reduce_flashes"]:
        result["effects"] = [
            effect for effect in result.get("effects", [])
            if not (
                (accessibility["reduce_motion"] and effect.get("kind") == "camera_shake")
                or (accessibility["reduce_flashes"] and effect.get("kind") == "light")
            )
        ]
    if accessibility["reduce_flashes"]:
        result["fadeOpacity"] = 0
        result["transitionOpacity"] = 0
    return result

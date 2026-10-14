"""R7.7 Player-only settings sidecar, independent from GameSession saves.

Malformed preferences never prevent launching the Player or trigger a silent
migration. Saving is atomic, and failed writes retain the previous file.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .player_ux import DEFAULT_KEYS, KeyBindings


SETTINGS_VERSION = 1


def default_preferences():
    return {
        "version": SETTINGS_VERSION,
        "keybindings": dict(DEFAULT_KEYS),
        "text_scale": 100,
        "high_contrast": False,
        "compact_hud": False,
    }


def preferences_path(profile):
    """Use an explicit UI sidecar; do not share save slots or project manifests."""
    profile = Path(profile)
    return profile.with_name(profile.name + ".player-ux.json")


def validate_preferences(document):
    if type(document) is not dict:
        raise ValueError("Player preferences must be an object")
    expected = {"version", "keybindings", "text_scale",
                "high_contrast", "compact_hud"}
    if set(document) != expected:
        raise ValueError("Unrecognized or incomplete Player preferences")
    if type(document["version"]) is not int or document["version"] != SETTINGS_VERSION:
        raise ValueError("Unsupported Player preferences version")
    if type(document["keybindings"]) is not dict or set(document["keybindings"]) != set(DEFAULT_KEYS):
        raise ValueError("Incomplete or unknown Player keyboard mapping")
    keys = KeyBindings(document["keybindings"])
    scale = document["text_scale"]
    if type(scale) is not int or scale not in (100, 125, 150):
        raise ValueError("Text scale must be 100, 125 or 150 percent")
    for field in ("high_contrast", "compact_hud"):
        if type(document[field]) is not bool:
            raise ValueError(field + " must be a boolean")
    return {
        "version": SETTINGS_VERSION,
        "keybindings": dict(keys.items()),
        "text_scale": scale,
        "high_contrast": document["high_contrast"],
        "compact_hud": document["compact_hud"],
    }


def load_preferences(profile):
    """Return (validated settings, optional diagnostic); retain corrupt originals."""
    path = preferences_path(profile)
    if not path.exists():
        return default_preferences(), None
    try:
        contents = path.read_text(encoding="utf-8")
        return validate_preferences(json.loads(contents)), None
    except (OSError, UnicodeError, ValueError) as exc:
        return default_preferences(), ("Fichier de préférences ignoré : " +
                                       str(exc) + " (" + str(path) + ")")


def save_preferences(profile, document):
    """Validate before touching disk; never truncate a prior settings file."""
    validated = validate_preferences(document)
    target = preferences_path(profile)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(
            prefix=".player-ux-", suffix=".tmp", dir=target.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(validated, handle, sort_keys=True, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
    return target

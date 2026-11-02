"""Validated opt-in presentation for the Player title screen.

Stored in the canonical GameProject.extensions envelope; old games retain
exactly the same visuals and serialised project data until edited.
"""
from copy import deepcopy
from pathlib import PurePosixPath

from .model import RuleError, require
from .title_screen_layout import ELEMENTS

NAMESPACE = "org.drawtemp.titlescreen"
LABEL_KEYS = ("continue", "new", "load", "campaign", "options", "quit")
DEFAULTS = {
    "background": "auto",
    "image": "",
    "accent": "#e3b970",
    "panel": "#111a27",
    "text": "#f4ead7",
    "show_campaign": True,
    "labels": {},
    "positions": {},
}


def validate_title_screen(data):
    """Validate the small, declarative title-screen schema; return full defaults."""
    require(type(data) is dict, "Title screen must be an object")
    require(not (set(data) - set(DEFAULTS)), "Unknown title-screen field")
    settings = deepcopy(DEFAULTS)
    settings.update(deepcopy(data))
    require(settings["background"] in ("auto", "solid", "image"),
            "Title screen background must be auto, solid or image")
    path = settings["image"]
    require(type(path) is str and len(path) <= 240, "Invalid title-screen image path")
    if path:
        pure = PurePosixPath(path)
        require(not path.startswith("/") and "\\" not in path and ":" not in path
                and all(part not in (".", "..") for part in path.split("/"))
                and len(pure.parts) >= 2 and pure.parts[0] == "art"
                and pure.suffix.lower() in (".png", ".jpg", ".jpeg"),
                "Title-screen image must be a relative art/*.png or art/*.jpg path")
    require(settings["background"] != "image" or bool(path),
            "Choose a title-screen image for image mode")
    for key in ("accent", "panel", "text"):
        value = settings[key]
        require(type(value) is str and len(value) == 7 and value.startswith("#")
                and all(ch in "0123456789abcdefABCDEF" for ch in value[1:]),
                "Title-screen %s must be a #RRGGBB color" % key)
    require(type(settings["show_campaign"]) is bool,
            "Title-screen show_campaign must be boolean")
    labels = settings["labels"]
    require(type(labels) is dict and not (set(labels) - set(LABEL_KEYS)),
            "Unknown title-screen action label")
    for key, value in labels.items():
        require(type(value) is str and 0 < len(value.strip()) <= 48,
                "Title-screen label %s must have 1..48 characters" % key)
    positions = settings["positions"]
    require(type(positions) is dict and not (set(positions) - set(ELEMENTS)),
            "Unknown title-screen element position")
    for key, xy in positions.items():
        require(type(xy) is list and len(xy) == 2
                and all(type(value) in (int, float) and 0 <= value <= 1
                        for value in xy),
                "Title-screen position %s must be normalized [x,y]" % key)
    return settings


def settings_for(project):
    """Get normalized settings without modifying a GameProject."""
    extensions = getattr(project, "extensions", {})
    envelope = extensions.get(NAMESPACE)
    if envelope is None:
        return deepcopy(DEFAULTS)
    return validate_title_screen(envelope["data"])


def extension_for(data):
    """Build the immutable-schema envelope used by the existing extension API."""
    return {"schema_version": 1, "data": validate_title_screen(data)}

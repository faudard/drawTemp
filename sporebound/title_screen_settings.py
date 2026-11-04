"""Validated opt-in presentation for the Player title screen.

Stored in the canonical GameProject.extensions envelope; old games retain
exactly the same visuals and serialised project data until edited.
"""
from copy import deepcopy
from pathlib import PurePosixPath
import re

from .model import RuleError, require
from .title_screen_layout import ELEMENTS

NAMESPACE = "org.drawtemp.titlescreen"
LABEL_KEYS = ("continue", "new", "load", "campaign", "options", "quit")
STRING_KEYS = ("logo", "campaign_heading", "campaign_change",
               "advanced", "credits", "help", "footer_brand")
LANGUAGES = ("en", "fr")
ENGLISH_LABELS = {
    "continue": "Continue", "new": "New game", "load": "Load game",
    "campaign": "Campaigns", "options": "Options", "quit": "Quit",
}
ENGLISH_CAPTIONS = {
    "continue": "Resume your last game", "new": "Start a new adventure",
    "load": "Choose an existing save", "campaign": "Choose a campaign",
    "options": "Graphics, audio, controls…", "quit": "Exit the game",
}
ENGLISH_STRINGS = {
    "logo": "⚜", "campaign_heading": "Current campaign",
    "campaign_change": "Change campaign", "advanced": "Advanced tools",
    "credits": "Credits", "help": "Help", "footer_brand": "DrawTemp · Player",
}
FRENCH_STRINGS = {
    "logo": "⚜", "campaign_heading": "Campagne actuelle",
    "campaign_change": "Changer de campagne", "advanced": "Outils avancés",
    "credits": "Crédits", "help": "Aide", "footer_brand": "DrawTemp · Player",
}


def display_text(settings, language, group, key, fallback):
    """Look up an authored language variant with safe legacy fallback."""
    source = settings.get("source_language") or language
    override = settings.get("translations", {}).get(language, {})
    if group in ("title", "subtitle"):
        return override.get(group, fallback)
    if key in override.get(group, {}):
        return override[group][key]
    if language == source:
        authored = settings.get(group, {})
        if group == "extras":
            return fallback
        if key in authored:
            return authored[key]
        if language == "en" and settings.get("source_language") == "en":
            return {"labels": ENGLISH_LABELS, "captions": ENGLISH_CAPTIONS,
                    "strings": ENGLISH_STRINGS}.get(group, {}).get(key, fallback)
        return fallback
    if language == "en":
        return {"labels": ENGLISH_LABELS, "captions": ENGLISH_CAPTIONS,
                "strings": ENGLISH_STRINGS}.get(group, {}).get(key, fallback)
    if language == "fr" and group == "strings":
        return FRENCH_STRINGS.get(key, fallback)
    return fallback


def _art_path(value):
    if not isinstance(value, str) or not value or len(value) > 240:
        return False
    pure = PurePosixPath(value)
    return (not value.startswith("/") and chr(92) not in value and ":" not in value
            and all(part not in (".", "..", "") for part in value.split("/"))
            and len(pure.parts) >= 2 and pure.parts[0] == "art"
            and pure.suffix.lower() in (".png", ".jpg", ".jpeg"))


def extra_box(item, width, height):
    """Responsive normalized geometry for user-authored overlays."""
    w, h = item["width"] * width, item["height"] * height
    x = min(item["x"] * width, width - w)
    y = min(item["y"] * height, height - h)
    return (x, y, x + w, y + h)

DEFAULTS = {
    "background": "auto",
    "image": "",
    "accent": "#e3b970",
    "panel": "#111a27",
    "text": "#f4ead7",
    "show_campaign": True,
    "labels": {},
    "positions": {},
    "source_language": "",
    "captions": {},
    "strings": {},
    "hidden": [],
    "extras": [],
    "translations": {},
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
        require(_art_path(path),
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
    require(settings["source_language"] in ("", *LANGUAGES),
            "Title-screen source language must be English or French")
    for group, keys, maximum in (("captions", LABEL_KEYS, 120),
                                 ("strings", STRING_KEYS, 120)):
        values = settings[group]
        require(type(values) is dict and not (set(values) - set(keys)),
                "Unknown title-screen " + group + " key")
        for key, value in values.items():
            require(type(value) is str and len(value) <= maximum,
                    "Invalid title-screen %s text: %s" % (group, key))
    hidden = settings["hidden"]
    require(type(hidden) is list
            and all(type(key) is str and key in ELEMENTS for key in hidden)
            and len(hidden) == len(set(hidden)),
            "Invalid hidden title-screen element")
    extras = settings["extras"]
    require(type(extras) is list and len(extras) <= 64,
            "Title screen supports at most 64 extra elements")
    identifiers = set()
    for item in extras:
        require(type(item) is dict and set(item) ==
                {"id", "kind", "text", "image", "color", "size",
                 "x", "y", "width", "height"}, "Invalid extra element fields")
        ident = item["id"]
        require(type(ident) is str and re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", ident)
                and ident not in identifiers, "Duplicate or invalid extra element ID")
        identifiers.add(ident)
        require(item["kind"] in ("text", "image"), "Unknown extra element type")
        require(type(item["text"]) is str and len(item["text"]) <= 240,
                "Extra text is too long")
        require(type(item["image"]) is str and
                (not item["image"] or _art_path(item["image"])),
                "Extra image must be a project-relative art/ asset")
        require(item["kind"] != "image" or bool(item["image"]),
                "Image element requires an image")
        require(type(item["color"]) is str and re.fullmatch(
            r"#[0-9a-fA-F]{6}", item["color"]), "Invalid extra text color")
        require(type(item["size"]) is int and 8 <= item["size"] <= 120,
                "Extra font size must be 8..120")
        for field in ("x", "y", "width", "height"):
            value = item[field]
            require(type(value) in (int, float) and 0 <= value <= 1,
                    "Extra geometry must be normalized")
        require(item["width"] > 0 and item["height"] > 0,
                "Extra dimensions must be positive")
    translations = settings["translations"]
    require(type(translations) is dict and not (set(translations) - set(LANGUAGES)),
            "Unknown title-screen language")
    for language, overrides in translations.items():
        require(type(overrides) is dict and not (set(overrides) -
                {"title", "subtitle", "labels", "captions", "strings", "extras"}),
                "Invalid translations for " + language)
        for field in ("title", "subtitle"):
            if field in overrides:
                require(type(overrides[field]) is str and len(overrides[field]) <= 240,
                        "Invalid translated " + field)
        for group, keys in (("labels", LABEL_KEYS), ("captions", LABEL_KEYS),
                            ("strings", STRING_KEYS), ("extras", identifiers)):
            values = overrides.get(group, {})
            require(type(values) is dict and not (set(values) - set(keys)),
                    "Unknown translated " + group + " key")
            require(all(type(value) is str and len(value) <= 240
                        for value in values.values()),
                    "Invalid translated " + group)
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

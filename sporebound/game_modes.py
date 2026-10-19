"""R25: versioned, declarative game-mode capabilities in canonical GameProject.

This module does not implement action combat or introduce a second game registry.
An absent manifest is *read* as the historical tactical default and is never
written back to legacy GameProject JSON as a side effect.
"""
from copy import deepcopy

from .model import require


SCHEMA_VERSION = 1
FIELDS = ("movement", "combat", "camera", "interaction", "ui")
VALUES = {
    "movement": {"GRID_CT", "FREE_REALTIME", "GRID_TURN"},
    "combat": {"TACTICAL_CT", "ACTION_REALTIME", "RPG_TURN", "NONE"},
    "camera": {"ISOMETRIC", "TOP_DOWN"},
    "interaction": {"TACTICAL", "CONTEXTUAL", "NARRATIVE"},
    "ui": {"TACTICAL", "ACTION", "RPG", "NARRATIVE"},
}
PRESETS = {
    "srpg": {
        "movement": "GRID_CT", "combat": "TACTICAL_CT", "camera": "ISOMETRIC",
        "interaction": "TACTICAL", "ui": "TACTICAL",
    },
    "action": {
        "movement": "FREE_REALTIME", "combat": "ACTION_REALTIME", "camera": "TOP_DOWN",
        "interaction": "CONTEXTUAL", "ui": "ACTION",
    },
    "classic_rpg": {
        "movement": "GRID_TURN", "combat": "RPG_TURN", "camera": "TOP_DOWN",
        "interaction": "CONTEXTUAL", "ui": "RPG",
    },
    "narrative": {
        "movement": "FREE_REALTIME", "combat": "NONE", "camera": "TOP_DOWN",
        "interaction": "NARRATIVE", "ui": "NARRATIVE",
    },
    "hybrid": {
        "movement": "FREE_REALTIME", "combat": "ACTION_REALTIME", "camera": "TOP_DOWN",
        "interaction": "CONTEXTUAL", "ui": "ACTION",
    },
}


def _profile(value):
    require(type(value) is dict and set(value) == set(FIELDS),
            "Game mode profile needs movement, combat, camera, interaction and ui")
    for name, allowed in VALUES.items():
        require(type(value[name]) is str and value[name] in allowed,
                f"Unknown game mode {name}: {value[name]!r}")
    combat, movement = value["combat"], value["movement"]
    if combat == "TACTICAL_CT":
        require(movement == "GRID_CT", "TACTICAL_CT requires GRID_CT movement")
    else:
        require(movement != "GRID_CT", "GRID_CT requires TACTICAL_CT combat")
    if combat == "ACTION_REALTIME":
        require(movement == "FREE_REALTIME",
                "Action combat requires FREE_REALTIME movement")
    if movement == "FREE_REALTIME":
        require(value["camera"] == "TOP_DOWN",
                "Free movement currently requires TOP_DOWN camera")
    return deepcopy(value)


def _entry(value):
    require(type(value) is dict and len(value) == 1
            and ("preset" in value or "profile" in value),
            "Game mode selection requires one preset OR one complete profile")
    if "preset" in value:
        preset = value["preset"]
        require(type(preset) is str and preset in PRESETS,
                f"Unknown game mode preset: {preset!r}")
        return deepcopy(PRESETS[preset])
    return _profile(value["profile"])


def legacy_modes():
    """Explicit in-memory migration; never modifies existing project files."""
    return {"version": SCHEMA_VERSION, "default": {"preset": "srpg"}, "scenes": {}}


def validate_game_modes(manifest, content, project):
    """Fail closed on schema, capabilities, and dangling scene references."""
    require(type(manifest) is dict, "Game modes must be an object")
    if not manifest:
        return  # Old project (v1) remains byte-for-byte unchanged on save.
    require(set(manifest) == {"version", "default", "scenes"},
            "Unknown/missing game mode fields")
    require(type(manifest["version"]) is int
            and manifest["version"] == SCHEMA_VERSION,
            "Unsupported game mode schema version")
    _entry(manifest["default"])
    scenes = manifest["scenes"]
    require(type(scenes) is dict and len(scenes) <= 4096,
            "Invalid game mode scene index")
    # Scene definitions live only in the existing Content/GameProject model.
    known = set(content.missions) | set(project.exploration)
    known.update(s["id"] for s in project.story.get("scenes", []))
    for scene_id, entry in scenes.items():
        require(type(scene_id) is str and scene_id in known,
                f"Unknown game mode scene: {scene_id!r}")
        profile = _entry(entry)
    # Every tactical mission remains CT, including missions that inherit
    # the project default instead of carrying an explicit scene override.
    for mission_id in content.missions:
        active = _entry(scenes.get(mission_id, manifest["default"]))
        require(active["combat"] == "TACTICAL_CT",
                "Existing tactical missions must retain CT rules")


def resolve_scene_profile(manifest, scene_id=None):
    """Return detached capabilities for a project or an authored scene."""
    require(type(manifest) is dict, "Game modes must be an object")
    if not manifest:
        return deepcopy(PRESETS["srpg"])
    require(set(manifest) == {"version", "default", "scenes"}
            and type(manifest["version"]) is int
            and manifest["version"] == SCHEMA_VERSION
            and type(manifest["scenes"]) is dict, "Invalid game mode manifest")
    if scene_id is not None:
        require(type(scene_id) is str and bool(scene_id),
                "Invalid scene identity")
    return _entry(manifest["scenes"].get(scene_id, manifest["default"]))


__all__ = ["SCHEMA_VERSION", "PRESETS", "legacy_modes",
           "validate_game_modes", "resolve_scene_profile"]

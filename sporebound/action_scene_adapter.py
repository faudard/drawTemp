"""R50.B opt-in R26 action-scene authoring bound to canonical GameProject.

Only a strict project extension may enable action ticks in GameSession.
The extension adds no executable code, second project format or save sidecar.
R26 action loot is kept isolated until an explicit future R50 settlement gate.
"""
from __future__ import annotations

from copy import deepcopy

from .action_runtime import validate_scene
from .game_modes import resolve_scene_profile
from .model import RuleError, require

EXTENSION = "org.drawtemp.actioncombat"
VERSION = 1


def validate_action_catalog(spec, *, project):
    """Validate exact version, scene identity, geometry and active game mode."""
    require(type(spec) is dict and set(spec) == {"version", "scenes"}
            and type(spec["version"]) is int and spec["version"] == VERSION,
            "Unsupported action-combat project extension")
    scenes = spec["scenes"]
    require(type(scenes) is dict and 1 <= len(scenes) <= 32,
            "Action-combat catalogue requires 1..32 authored scenes")
    require(bool(project.scene_routes), "Action-combat scenes require R25 scene routing")
    for key, payload in scenes.items():
        require(type(key) is str and key in project.exploration,
                "Action scene needs a canonical exploration identity")
        scene = validate_scene(payload)
        stage = project.exploration[key]
        require(scene["id"] == key and
                scene["width"] == stage["width"] and
                scene["height"] == stage["height"] and
                {tuple(cell) for cell in scene["walls"]} ==
                {tuple(cell) for cell in stage["blocked"]} and
                scene["hero"]["pos"] == stage["start"],
                "Action scene must match authored exploration geometry")
        require(resolve_scene_profile(project.game_modes, key)["combat"] ==
                "ACTION_REALTIME", "Action scene requires an ACTION_REALTIME profile")
    return deepcopy(spec)


def authored_action_scene(project, scene_id):
    """Read only a validated scene; no defaults that impersonate action combat."""
    envelope = project.extensions.get(EXTENSION)
    require(envelope is not None, "No R26 action-combat project extension")
    validated = validate_action_catalog(envelope["data"], project=project)
    require(scene_id in validated["scenes"], "Scene has no R26 action combat")
    return deepcopy(validated["scenes"][scene_id])

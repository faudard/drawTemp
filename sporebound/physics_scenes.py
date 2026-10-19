"""R32.C authoring contract: platform scenes live in GameProject.extensions.

No runtime state, arbitrary code, Qt imports, or independent document store.
The R32 geometry validator remains the one used by the physics runtime.
"""
from __future__ import annotations

from copy import deepcopy

from sporebound.model import RuleError
from sporebound.platform_physics import validate_platform_scene

EXTENSION = "drawtemp.physics"
MAX_SCENES = 8


def physics_scene_ids(content, project):
    """Resolve canonical authored identities; do not invent a scene registry."""
    ids = set(content.missions)
    ids.update(project.exploration)
    ids.update(row["id"] for row in project.story.get("scenes", []))
    return ids


def validate_physics_catalog(data, *, known_ids):
    """Strictly validate optional extension data on every GameProject load.

    Unknown physics scenes cannot be smuggled into a generic JSON extension.
    The extension remains inert unless an explicit R32 mode owner activates it.
    """
    if type(data) is not dict or set(data) != {"scenes"}:
        raise RuleError("R32 physics extension expects exactly 'scenes'")
    scenes = data["scenes"]
    if type(scenes) is not dict or len(scenes) > MAX_SCENES:
        raise RuleError("R32 physics scene count exceeds supported limit")
    for scene_id, authored in scenes.items():
        if type(scene_id) is not str or scene_id not in known_ids:
            raise RuleError("R32 physics scene has no canonical authored identity")
        checked = validate_platform_scene(authored)
        if checked["id"] != scene_id:
            raise RuleError("R32 physics scene identity disagrees with project")
    return deepcopy(data)


def physics_catalog(project):
    """Detached optional data; never materialize defaults into legacy projects."""
    raw = project.get("extensions", {}).get(EXTENSION)
    if raw is None:
        return {"scenes": {}}
    if type(raw) is not dict or raw.get("schema_version") != 1:
        raise RuleError("Unsupported R32 physics extension version")
    return deepcopy(raw["data"])


__all__ = ["EXTENSION", "MAX_SCENES", "physics_scene_ids",
           "validate_physics_catalog", "physics_catalog"]

"""R32.C transactional collider authoring on the one canonical AuthoringSession.

The physics definition is a typed GameProject v1 extension. Preview/apply
and undo/redo belong to R1; no sidecar JSON or local edit history is created.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.model import RuleError
from sporebound.physics_scenes import (
    EXTENSION, MAX_SCENES, physics_catalog, validate_physics_catalog,
)
from sporebound.platform_physics import PlatformPhysics, validate_platform_scene


class ColliderAuthoringError(RuleError):
    """Unsafe or stale R32 authoring request."""


def _identities(pair):
    return (set(pair["project"].get("exploration", {}))
            | {row["id"] for row in pair["project"].get("story", {}).get("scenes", [])}
            | {row["id"] for row in pair["content"]["missions"]})


class PlatformColliderStudio:
    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise TypeError("R32 Collider Studio requires AuthoringSession")
        self.session = session

    def targets(self):
        snap = self.session.snapshot().to_dict()
        return tuple(sorted(_identities(snap)))

    def catalog(self):
        return physics_catalog(self.session.snapshot().to_dict()["project"])

    def scene(self, scene_id):
        rows = self.catalog()["scenes"]
        if scene_id not in rows:
            raise ColliderAuthoringError("R32 scene has no authored collider definition")
        return deepcopy(rows[scene_id])

    def preview_playtest(self, scene_id):
        """Detached headless preview; does not start or replace GameSession."""
        return PlatformPhysics(self.scene(scene_id))

    def _plan(self, transform, *, revision, kind):
        if type(revision) is not int or revision != self.session.revision:
            raise ColliderAuthoringError("Stale physics edit; refresh the Studio")
        def edit(project):
            raw = physics_catalog(project)
            transform(raw)
            if raw["scenes"]:
                # Project-level validator also enforces canonical identities.
                project.setdefault("extensions", {})[EXTENSION] = {
                    "schema_version": 1, "data": raw,
                }
            else:
                project.get("extensions", {}).pop(EXTENSION, None)
                if not project.get("extensions"):
                    project.pop("extensions", None)
            return project
        return self.session.preview_project(edit, kind="r32-" + kind)

    def preview_create(self, scene_id, *, revision, width=12000, height=6000):
        if scene_id not in self.targets():
            raise ColliderAuthoringError("Unknown canonical scene")
        if type(width) is not int or type(height) is not int:
            raise ColliderAuthoringError("Scene dimensions must be integers")
        if width < 4000 or height < 4000:
            raise ColliderAuthoringError("Scene must fit actor and safe floor")
        scene = {
            "id": scene_id, "width": width, "height": height, "gravity": 40,
            "hero": {"pos": [1000, height - 1800],
                     "size": [500, 800], "speed": 240,
                     "jump": 520, "max_fall": 900, "coyote": 4},
            "colliders": [{
                "id": "floor", "rect": [0, height - 1000, width, 1000],
                "layer": 1, "mask": 1, "trigger": False, "one_way": False,
            }],
        }
        validate_platform_scene(scene)
        def change(data):
            if scene_id in data["scenes"] or len(data["scenes"]) >= MAX_SCENES:
                raise ColliderAuthoringError("Scene already authored or catalog full")
            data["scenes"][scene_id] = deepcopy(scene)
        return self._plan(change, revision=revision, kind="create-physics-scene")

    def preview_put(self, scene_id, collider, *, revision):
        if type(collider) is not dict or type(collider.get("id")) is not str:
            raise ColliderAuthoringError("Expected a named typed collider")
        edited = deepcopy(collider)
        def change(data):
            if scene_id not in data["scenes"]:
                raise ColliderAuthoringError("Author the physics scene first")
            scene = data["scenes"][scene_id]
            objects = [item for item in scene["colliders"] if item["id"] != edited["id"]]
            objects.append(deepcopy(edited))
            scene["colliders"] = sorted(objects, key=lambda row: row["id"])
            validate_platform_scene(scene)
        return self._plan(change, revision=revision, kind="put-collider")

    def preview_remove(self, scene_id, collider_id, *, revision):
        def change(data):
            if scene_id not in data["scenes"]:
                raise ColliderAuthoringError("Unknown physics scene")
            scene = data["scenes"][scene_id]
            before = len(scene["colliders"])
            scene["colliders"] = [r for r in scene["colliders"] if r["id"] != collider_id]
            if len(scene["colliders"]) == before:
                raise ColliderAuthoringError("Collider was not found")
            validate_platform_scene(scene)
        return self._plan(change, revision=revision, kind="remove-collider")

    def preview_remove_scene(self, scene_id, *, revision):
        def change(data):
            if scene_id not in data["scenes"]:
                raise ColliderAuthoringError("Unknown physics scene")
            del data["scenes"][scene_id]
        return self._plan(change, revision=revision, kind="remove-physics-scene")

    def apply(self, plan):
        return self.session.apply(plan)


__all__ = ["PlatformColliderStudio", "ColliderAuthoringError"]

"""R36.A: animation controller authoring in canonical GameProject.extensions.

States refer to R28 AssetRegistry animations, not a second sprite database.
Preview/apply goes through R1 AuthoringSession for undo/redo and stale checks.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.animation_graph import (
    NAMESPACE, AnimationGraphError, validate_controller,
)
from sporebound.assets import AssetRegistry

MAX_CONTROLLERS = 16


def controllers_from_project(project):
    if hasattr(project, "to_dict"):
        project = project.to_dict()
    if type(project) is not dict:
        raise AnimationGraphError("invalid_project", "Expected GameProject object")
    extension = project.get("extensions", {}).get(NAMESPACE)
    if extension is None:
        return []
    if (type(extension) is not dict or
            set(extension) != {"schema_version", "data", "references"} or
            type(extension["schema_version"]) is not int or
            extension["schema_version"] != 1 or
            extension["references"] != [] or
            type(extension["data"]) is not dict or
            set(extension["data"]) != {"controllers"} or
            type(extension["data"]["controllers"]) is not list):
        raise AnimationGraphError("invalid_storage", "R36 extension needs explicit migration")
    controllers = extension["data"]["controllers"]
    if len(controllers) > MAX_CONTROLLERS:
        raise AnimationGraphError("controller_budget", "At most 16 animation controllers")
    registry = AssetRegistry(project.get("assets") or None)
    validated = [validate_controller(row, registry) for row in controllers]
    identifiers = [row["id"] for row in validated]
    if len(set(identifiers)) != len(identifiers):
        raise AnimationGraphError("duplicate_controller", "Controller IDs must be unique")
    return validated


class AnimationControllerAuthoring:
    def __init__(self, session):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected canonical AuthoringSession")
        self.session = session

    def controllers(self):
        return controllers_from_project(self.session.snapshot().to_dict()["project"])

    def preview(self, document, *, expected_revision=None):
        if expected_revision is not None and self.session.revision != expected_revision:
            raise AnimationGraphError("stale_revision", "Reload animation controller before editing")
        # Validate the draft before R1 preview; validate again inside transaction
        # to reject asset edits that invalidate refs between operations.
        before = self.session.snapshot().to_dict()["project"]
        candidate = validate_controller(document, AssetRegistry(before.get("assets") or None))

        def transform(project):
            current = controllers_from_project(project)
            registry = AssetRegistry(project.get("assets") or None)
            value = validate_controller(candidate, registry)
            result = [row for row in current if row["id"] != value["id"]]
            result.append(value)
            result.sort(key=lambda row: row["id"])
            if len(result) > MAX_CONTROLLERS:
                raise AnimationGraphError("controller_budget", "At most 16 animation controllers")
            project.setdefault("extensions", {})[NAMESPACE] = {
                "schema_version": 1, "data": {"controllers": result}, "references": []}
            return project
        return self.session.preview_project(transform, kind="r36.animation.controller")

    def preview_remove(self, controller_id, *, expected_revision=None):
        if expected_revision is not None and self.session.revision != expected_revision:
            raise AnimationGraphError("stale_revision", "Reload animation controller before editing")
        if controller_id not in {row["id"] for row in self.controllers()}:
            raise AnimationGraphError("unknown_controller", "Controller does not exist")

        def transform(project):
            rows = [row for row in controllers_from_project(project)
                    if row["id"] != controller_id]
            if rows:
                project["extensions"][NAMESPACE] = {
                    "schema_version": 1, "data": {"controllers": rows},
                    "references": []}
            else:
                project["extensions"].pop(NAMESPACE)
            return project
        return self.session.preview_project(transform, kind="r36.animation.remove")

    def apply(self, plan):
        return self.session.apply(plan)

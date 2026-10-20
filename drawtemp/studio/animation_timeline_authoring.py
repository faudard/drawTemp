"""R36.B2 transactional visual-cue marker editor over canonical R1 projects."""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.animation_graph import (
    AnimationGraphError, controllers_from_project,
)
from sporebound.animation_timeline import (
    NAMESPACE, MAX_TIMELINES, timelines_from_project, validate_timeline,
)
from sporebound.assets import AssetRegistry


class AnimationTimelineAuthoring:
    def __init__(self, session):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected an R1 AuthoringSession")
        self.session = session

    def timelines(self):
        return timelines_from_project(self.session.snapshot().to_dict()["project"])

    def _revision(self, expected_revision):
        if (expected_revision is not None and
                self.session.revision != expected_revision):
            raise AnimationGraphError("stale_revision", "Reload timeline before editing")

    def preview(self, document, *, expected_revision=None):
        self._revision(expected_revision)

        def transform(project):
            controllers = {
                row["id"]: row for row in controllers_from_project(project)}
            controller_id = document.get("controller_id") if type(document) is dict else None
            if type(controller_id) is not str or controller_id not in controllers:
                raise AnimationGraphError("unknown_controller", "Timeline requires existing R36 controller")
            item = validate_timeline(
                document, controllers[controller_id],
                AssetRegistry(project.get("assets") or None))
            rows = [
                row for row in timelines_from_project(project)
                if row["id"] != item["id"] and
                row["controller_id"] != item["controller_id"]]
            rows.append(item)
            rows.sort(key=lambda row: row["id"])
            if len(rows) > MAX_TIMELINES:
                raise AnimationGraphError("timeline_budget", "At most 16 visual timelines")
            project.setdefault("extensions", {})[NAMESPACE] = {
                "schema_version": 1, "data": {"timelines": rows}, "references": []}
            return project

        return self.session.preview_project(
            transform, kind="r36.animation.visual_timeline")

    def preview_remove(self, timeline_id, *, expected_revision=None):
        self._revision(expected_revision)
        if timeline_id not in {t["id"] for t in self.timelines()}:
            raise AnimationGraphError("unknown_timeline", "Visual timeline not found")

        def transform(project):
            rows = [t for t in timelines_from_project(project) if t["id"] != timeline_id]
            if rows:
                project["extensions"][NAMESPACE] = {
                    "schema_version": 1, "data": {"timelines": rows},
                    "references": []}
            else:
                project["extensions"].pop(NAMESPACE)
            return project

        return self.session.preview_project(
            transform, kind="r36.animation.visual_timeline_remove")

    def apply(self, plan):
        return self.session.apply(plan)

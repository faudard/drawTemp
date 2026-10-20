"""R65.B canonical authoring: reversible presets, no standalone editor save."""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.action_combat_catalog_r65 import (
    NAMESPACE, catalog_from_project, hitbox_preview, starter_preset,
    validate_catalog, validate_preset, windows_preview,
)
from sporebound.action_runtime import ActionError, _check, _id


class CombatComposerDraft:
    """Disposable R1 edit: preview is read-only, apply is exactly one Undo step."""

    def __init__(self, session, document, *, original_id=None):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected R1 AuthoringSession")
        self.session = session
        self.source_revision = session.revision
        self.original_id = original_id
        self.document = validate_preset(document)
        self.pending = None

    @classmethod
    def create(cls, session, identifier="starter"):
        return cls(session, starter_preset(identifier))

    @classmethod
    def load(cls, session, identifier):
        catalog = catalog_from_project(session.snapshot().to_dict()["project"])
        for row in catalog["presets"]:
            if row["id"] == identifier:
                return cls(session, row, original_id=identifier)
        raise ActionError("Unknown R65 preset")

    def replace(self, value):
        self.document = deepcopy(value)
        self.pending = None

    def preview(self, *, scene=None, default=None):
        self.pending = None
        if self.session.revision != self.source_revision:
            raise ActionError("Stale R65 draft; refresh after Studio edit")
        new = validate_preset(self.document)
        if self.original_id is not None:
            _check(new["id"] == self.original_id, "Cannot rename existing combat preset")
        pair = self.session.snapshot().to_dict()
        catalog = catalog_from_project(pair["project"])
        before = next((deepcopy(item) for item in catalog["presets"]
                       if item["id"] == new["id"]), None)
        if before is not None and self.original_id is None:
            raise ActionError("Existing R65 preset ID; load before editing")
        if before is None and self.original_id is not None:
            raise ActionError("Original R65 preset disappeared")
        after = deepcopy(catalog)
        if before is None:
            after["presets"].append(new)
        else:
            after["presets"] = [
                new if item["id"] == self.original_id else item
                for item in after["presets"]]
        if default is None:
            default = after["default"] or new["id"]
        after["default"] = default
        after = validate_catalog(after)
        _check(after != catalog, "No R65 changes to apply")

        def update(project):
            extensions = project.setdefault("extensions", {})
            extensions[NAMESPACE] = {"schema_version": 1, "data": deepcopy(after),
                                     "references": []}
            return project

        plan = self.session.preview_project(update, kind="r65.combat.compose")
        report = {
            "revision": plan.source_revision, "before": before, "after": deepcopy(new),
            "default": default, "timeline": windows_preview(new),
            "geometry": (hitbox_preview(scene, new) if scene is not None else None),
            "runtime": "R65.A headless only; boss patterns are declarative R65.C input",
        }
        self.pending = (plan, report)
        return deepcopy(report)

    def apply(self):
        _check(self.pending is not None, "R65 preview required before apply")
        plan, _ = self.pending
        self.pending = None
        result = self.session.apply(plan)
        self.source_revision = self.session.revision
        self.original_id = self.document["id"]
        return result


def inspect_combat_presets(snapshot):
    project = (snapshot.to_dict()["project"] if hasattr(snapshot, "to_dict")
               and "project" in snapshot.to_dict() else snapshot)
    return catalog_from_project(project)


__all__ = ["CombatComposerDraft", "inspect_combat_presets"]

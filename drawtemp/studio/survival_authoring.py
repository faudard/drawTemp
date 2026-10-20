"""R63.B foundation: typed survival authoring via canonical Studio Undo/Redo.

This headless adapter does not claim the Qt graphical designer is complete.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.survival import EXTENSION, validate_survival


@dataclass(frozen=True)
class SurvivalDesignPreview:
    plan: object
    report: dict


def preview_survival_design(session, document, *, expected_revision=None):
    if not isinstance(session, AuthoringSession):
        raise TypeError("Expected the active AuthoringSession")
    snap = session.snapshot().to_dict()
    if expected_revision is not None and (
            type(expected_revision) is not int
            or snap["revision"] != expected_revision):
        raise ValueError("Outdated R63 survival authoring revision")
    exploration = snap["project"].get("exploration", {})
    scenes = set(exploration)
    spec = validate_survival(document, scenes, exploration=exploration) if document is not None else None

    def edit(project):
        extensions = project.setdefault("extensions", {})
        if spec is None:
            extensions.pop(EXTENSION, None)
        else:
            extensions[EXTENSION] = {
                "schema_version": 1, "data": deepcopy(spec), "references": []}
        return project

    plan = session.preview_project(edit, kind="r63.survival.design")
    return SurvivalDesignPreview(plan, {
        "source_revision": snap["revision"],
        "enabled": spec is not None,
        "recipes": len(spec["recipes"]) if spec else 0,
        "nodes": len(spec["nodes"]) if spec else 0,
        "shelters": len(spec["shelters"]) if spec else 0,
        "hazards": sum(row["cold"] > 0 for row in spec["nodes"]) if spec else 0})


def apply_survival_design(session, preview):
    if not isinstance(session, AuthoringSession):
        raise TypeError("Expected the active AuthoringSession")
    if not isinstance(preview, SurvivalDesignPreview):
        raise TypeError("Expected a validated R63 preview")
    return session.apply(preview.plan)

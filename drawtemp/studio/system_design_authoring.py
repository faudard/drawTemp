"""R55.B headless authoring adapter for the canonical Studio history.

Graph edits remain detached until AuthoringSession accepts the full project
pair. No shadow database or implicit rewrite of authored Content.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.system_design import EXTENSION, SystemEconomy, validate_systems


@dataclass(frozen=True)
class SystemDesignPreview:
    plan: object
    report: dict


def preview_system_design(session, document, *, expected_revision=None):
    if not isinstance(session, AuthoringSession):
        raise TypeError("Expected the active AuthoringSession")
    snap = session.snapshot().to_dict()
    if expected_revision is not None and (
            type(expected_revision) is not int
            or snap["revision"] != expected_revision):
        raise ValueError("Outdated R55 system designer revision")
    # Merchant commands are permitted only in authored exploration scenes.
    known_scenes = set(snap["project"].get("exploration", {}))
    if document is not None:
        spec = validate_systems(document, known_scenes)
    else:
        spec = None
    before = snap["project"].get("extensions", {}).get(EXTENSION)
    def edit(project):
        extensions = project.setdefault("extensions", {})
        if spec is None:
            extensions.pop(EXTENSION, None)
        else:
            extensions[EXTENSION] = {
                "schema_version": 1, "data": deepcopy(spec), "references": []}
        return project
    plan = session.preview_project(edit, kind="r55.systems.design")
    return SystemDesignPreview(plan, {
        "source_revision": snap["revision"],
        "before_enabled": before is not None,
        "after_enabled": spec is not None,
        "resource_count": len(spec["resources"]) if spec else 0,
        "producer_count": len(spec["producers"]) if spec else 0,
        "merchant_count": len(spec["merchants"]) if spec else 0,
        "quest_count": len(spec["quests"]) if spec else 0})


def apply_system_design(session, preview):
    if not isinstance(preview, SystemDesignPreview):
        raise TypeError("Expected a validated R55 design preview")
    return session.apply(preview.plan)


def forecast_system_design(document, scenes, *, ticks=16):
    """Read-only production/consumption forecast from authored initial stock."""
    economy = SystemEconomy(document, scenes)
    before = economy.snapshot()
    after = economy.preview(ticks)
    return {
        "ticks": ticks,
        "before": before["stocks"],
        "after": after["stocks"],
        "delta": {key: after["stocks"][key] - before["stocks"][key]
                  for key in sorted(before["stocks"])},
        "stalled": sorted(
            row["id"] for row in document["producers"]
            if any(after["stocks"][key] < qty
                   for key, qty in row["inputs"].items())),
        "edges": sorted({
            (source, target)
            for producer in document["producers"]
            for source in producer["inputs"]
            for target in producer["outputs"]}),
    }

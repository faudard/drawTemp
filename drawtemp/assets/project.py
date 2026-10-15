"""Project-facing R4 import and verification; reuses GameProject.assets v1."""
from __future__ import annotations

from pathlib import Path

from sporebound.assets import AssetRegistry
from sporebound.game_project import GameProject
from sporebound.model import Content

from .atlas import AtlasPlan, load_annotations, license_issues, save_annotations


def annotations_path(project_path: Path) -> Path:
    return Path(project_path).parent / ".drawtemp" / "r4-annotations.json"


def import_into_project(project_path: Path, content: Content, plan: AtlasPlan) -> GameProject:
    """Commit import and project manifest, preserving the existing project schema.

    Files are write-once. On ordinary errors restore original project and
    annotations; a crash can leave an orphan copied PNG, never overwrite art.
    """
    project_path = Path(project_path)
    root = project_path.resolve().parent
    original = project_path.read_bytes()
    project = GameProject.load(project_path, content)
    old_registry = project.asset_registry()
    annotations_file = annotations_path(project_path)
    before_annotations = annotations_file.read_bytes() if annotations_file.exists() else None
    existing = load_annotations(annotations_file, old_registry)
    new_registry = AssetRegistry(plan.manifest)
    combined = {"version": 1, "sprites": {
        **existing["sprites"], **plan.annotations,
    }}
    from .atlas import validate_annotations
    validate_annotations(new_registry, combined)
    if project_path.read_bytes() != original:
        raise RuntimeError("Project changed during asset import")
    destination = plan.copy_into(root)
    project.assets = plan.manifest
    wrote_project = False
    try:
        if project_path.read_bytes() != original:
            raise RuntimeError("Project changed during asset import")
        project.save(project_path, content)
        wrote_project = True
        save_annotations(annotations_file, new_registry, combined)
        return GameProject.load(project_path, content)
    except BaseException:
        # Keep all previous bytes, including optional omitted assets fields.
        # Restore only when safe; never delete a PNG referenced by another writer.
        from sporebound.storage import write_json
        if wrote_project:
            try:
                if project_path.read_bytes() == original:
                    pass
                else:
                    import json
                    write_json(project_path, json.loads(original.decode("utf-8")))
            except Exception as restore_error:
                raise RuntimeError(
                    "Project rollback failed; imported artwork was retained"
                ) from restore_error
        if before_annotations is None:
            annotations_file.unlink(missing_ok=True)
        else:
            import os
            rollback = annotations_file.with_name(annotations_file.name + ".rollback")
            try:
                with rollback.open("xb") as stream:
                    stream.write(before_annotations)
                    stream.flush()
                    os.fsync(stream.fileno())
                rollback.replace(annotations_file)
            finally:
                rollback.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise


def validate_project_assets(project_path: Path, content: Content) -> list[dict]:
    project = GameProject.load(project_path, content)
    registry = project.asset_registry()
    issues = registry.diagnostics(Path(project_path).parent)
    metadata = load_annotations(annotations_path(project_path), registry)
    return sorted(issues + license_issues(registry, metadata),
                  key=lambda item: (item["asset_id"], item["message"]))

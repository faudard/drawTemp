"""R58.B2: versioned resource pack replacement with explicit reversible history.

This is intentionally the *isolated-package* upgrade path, not general
multi-package migration. It preserves R24.C's canonical AssetRegistry and
receipt envelope. AuthoringSession owns the only document transaction. Old
versioned bytes are retained for Undo or an explicitly pinned downgrade.
No archive executes, no license assertions are converted to legal clearance.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
from zipfile import ZipFile

from drawtemp.assets.packs import (
    RECEIPT_NAMESPACE, ResourcePackError, _inspect_raw, _new_entries,
    _path, _read_archive, _receipt, _safe_destination, inspect_pack,
    verify_installed_packs,
)
from drawtemp.sdk.authoring import AuthoringPlan
from drawtemp.sdk.capability_contracts import parse_semver
from drawtemp.sdk.simulation import thaw
from drawtemp.studio.package_manager import (
    PackageManagerError, _project_root, _read_snapshot, _snapshot_digest,
    _walk_refs,
)
from sporebound.assets import AssetRegistry

_MAX_DIFF = 512


class PackageUpgradeError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(detail)


def _reject(code, detail):
    raise PackageUpgradeError(code, detail)


@dataclass(frozen=True)
class PackageUpgradePreview:
    package_id: str
    previous_version: str
    previous_sha256: str
    version: str
    sha256: str
    source_revision: int
    source_digest: str
    archive_path: Path
    added_paths: tuple[str, ...]
    retained_paths: tuple[str, ...]
    reuse_existing_bytes: bool
    downgrade: bool
    _manifest: object = field(repr=False, compare=False)
    _edit: AuthoringPlan = field(repr=False, compare=False)

    def to_dict(self):
        return {
            "operation": "version-replacement",
            "id": self.package_id,
            "from_version": self.previous_version,
            "to_version": self.version,
            "from_sha256": self.previous_sha256,
            "to_sha256": self.sha256,
            "source_revision": self.source_revision,
            "files_to_add": list(self.added_paths),
            "files_retained_for_undo": list(self.retained_paths),
            "reusing_verified_bytes": self.reuse_existing_bytes,
            "explicit_downgrade": self.downgrade,
            "same_asset_ids_and_kinds": True,
            "requires_explicit_save": True,
            "authenticity_verified": False,
            "rights_verified": False,
            "release_approved": False,
        }


def _version_root(root, manifest):
    pack_base = root / "assets" / "packs" / manifest["id"]
    # Existing R24.C pack creates this directory. Refuse unknown path types,
    # links, and directories outside canonical project root.
    if pack_base.is_symlink() or not pack_base.is_dir():
        _reject("unsafe_destination", "Missing/unsafe versioned pack directory")
    if not pack_base.resolve(strict=True).is_relative_to(root):
        _reject("unsafe_destination", "Pack directory escapes project root")
    target = pack_base / manifest["version"]
    if target.is_symlink():
        _reject("unsafe_destination", "Version directory is a symlink")
    return target


def _check_reusable(root, manifest):
    target = _version_root(root, manifest)
    if not target.exists():
        return False
    if not target.is_dir():
        _reject("destination_exists", "New version path is not a directory")
    declared = {"files/" + row["path"] for row in manifest["files"]}
    existing = set()
    for node in target.rglob("*"):
        if node.is_symlink() or not (node.is_file() or node.is_dir()):
            _reject("unsafe_destination", "Version directory contains an unsafe entry")
        if node.is_file():
            existing.add("files/" + node.relative_to(target).as_posix())
    # Versioned paths contain files directly, no extra 'files' prefix.
    expected = {row["path"] for row in manifest["files"]}
    actual = {item[len("files/"):] for item in existing}
    if actual != expected:
        _reject("destination_exists", "Existing version contains unexpected/missing files")
    for row in manifest["files"]:
        path = _safe_existing(root, manifest, row["path"])
        if (path.stat().st_size != row["bytes"] or
                sha256(path.read_bytes()).hexdigest() != row["sha256"]):
            _reject("hash_mismatch", "Existing version bytes differ: " + row["path"])
    return True


def _safe_existing(root, manifest, relative):
    expected = ("assets/packs/" + manifest["id"] + "/" +
                manifest["version"] + "/" + _path(relative))
    node = root
    for part in expected.split("/"):
        node = node / part
        if node.is_symlink():
            _reject("unsafe_destination", "Installed resource path is a symlink")
    if not node.is_file() or not node.resolve(strict=True).is_relative_to(root):
        _reject("unsafe_destination", "Expected canonical versioned resource file")
    return node


def _snapshot_and_pack(editor, root, pack_id):
    snapshot, installed = _read_snapshot(editor, root)
    current = next((row for row in installed if row["id"] == pack_id), None)
    if current is None:
        _reject("unknown_package", "Selected installed pack does not match archive")
    if len(installed) > 1:
        # Multi-pack upgrades are safe only if every receipt records complete
        # dependency provenance AND no dependent pins the selected version.
        if any("dependencies" not in row for row in installed):
            _reject("dependency_unknown",
                    "Legacy receipt prevents safe multi-pack version change")
        users = sorted(row["id"] for row in installed
                       if row["id"] != pack_id and any(
                           dep["id"] == pack_id for dep in row["dependencies"]))
        if users:
            _reject("dependency_in_use",
                    "Existing package pins the old version: " + ", ".join(users))
    return snapshot, current


def _check_compatibility(snapshot, current, manifest):
    # R58.B3: existing dependencies must remain EXACTLY pinned. A change
    # would require a new multi-package migration transaction and new proofs.
    original = current.get("dependencies")
    if original is None:
        if manifest["dependencies"]:
            _reject("dependency_unknown",
                    "Legacy receipt cannot prove former package dependencies")
    elif sorted(original, key=lambda dep: dep["id"]) != sorted(
            manifest["dependencies"], key=lambda dep: dep["id"]):
        _reject("dependency_migration_required",
                "Cannot change dependency version/digest during isolated upgrade")
    assets = AssetRegistry(snapshot["project"].get("assets") or None).to_dict()
    old_ids = frozenset(current["asset_ids"])
    current_entries = {row["id"]: row for row in assets["entries"] if row["id"] in old_ids}
    proposed = _new_entries(manifest)
    proposed_entries = {row["id"]: row for row in proposed}
    if set(current_entries) != set(proposed_entries):
        _reject("migration_required", "Upgrades cannot add or remove asset IDs yet")
    if any(current_entries[name]["kind"] != proposed_entries[name]["kind"]
           for name in current_entries):
        _reject("migration_required", "Upgrades cannot change asset kinds yet")
    old_paths = frozenset(file["path"] for file in current["files"])
    project = deepcopy(snapshot["project"])
    project.pop("assets", None)
    extensions = project.get("extensions") or {}
    extensions.pop(RECEIPT_NAMESPACE, None)
    project["extensions"] = extensions
    uses = _walk_refs(snapshot["content"], old_paths, prefix="content")
    uses += _walk_refs(project, old_paths, prefix="project")
    for other in assets["entries"]:
        if other["id"] not in old_ids and other["kind"] != "animation":
            if other["path"] in old_paths:
                uses += ("asset:" + other["id"],)
    if uses:
        _reject("migration_required", "Old physical paths referenced externally: " +
                "; ".join(uses[:8]))
    return old_ids, proposed


def preview_package_upgrade(
    editor, project_root, archive_path, *, expected_sha256,
    allow_downgrade=False, expected_revision=None,
):
    """Read-only diff; no filesystem writes, no editing or implicit grant."""
    root = _project_root(project_root)
    if type(expected_sha256) is not str or len(expected_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in expected_sha256):
        _reject("invalid_pin", "Supply an independently verified lowercase SHA-256")
    source = Path(archive_path)
    if source.is_symlink() or not source.is_file():
        _reject("unsafe_archive", "Archive must be a regular non-symlink file")
    try:
        preview = inspect_pack(source)
    except ResourcePackError as exc:
        raise PackageUpgradeError("invalid_archive", str(exc)) from exc
    if preview.sha256 != expected_sha256:
        _reject("digest_mismatch", "Pack archive does not match the supplied pin")
    manifest = thaw(preview.manifest)
    snapshot, current = _snapshot_and_pack(editor, root, manifest["id"])
    if expected_revision is not None and (
            type(expected_revision) is not int or
            editor.revision != expected_revision):
        _reject("stale_revision", "Studio changed before preview")
    old_version = parse_semver(current["version"])
    new_version = parse_semver(manifest["version"])
    if old_version == new_version:
        _reject("same_version", "Replacing the same version requires an explicit migration")
    downgrade = new_version < old_version
    if downgrade and allow_downgrade is not True:
        _reject("downgrade_denied", "Older version needs explicit user approval")
    old_ids, candidate_entries = _check_compatibility(snapshot, current, manifest)

    def transform(project):
        registry = project["assets"]
        registry["entries"] = [
            row for row in registry["entries"] if row["id"] not in old_ids
        ] + deepcopy(candidate_entries)
        receipts = project["extensions"][RECEIPT_NAMESPACE]["data"]["packs"]
        receipts[:] = [_receipt(manifest, preview.sha256)]
        return project

    try:
        edit = editor.preview_project(transform, kind="r58.package-upgrade")
    except (ValueError, KeyError, TypeError, PackageManagerError) as exc:
        raise PackageUpgradeError("invalid_candidate", str(exc)) from exc

    reusable = _check_reusable(root, manifest)
    new_paths = tuple(sorted(
        "assets/packs/" + manifest["id"] + "/" + manifest["version"] + "/" +
        row["path"] for row in manifest["files"]
    ))
    retained = tuple(sorted(row["path"] for row in current["files"]))
    if len(new_paths) > _MAX_DIFF:
        _reject("size_limit", "Too many resources in one diff")
    return PackageUpgradePreview(
        manifest["id"], current["version"], current["sha256"],
        manifest["version"], preview.sha256, snapshot["revision"],
        _snapshot_digest(snapshot), source,
        () if reusable else new_paths, retained, reusable, downgrade,
        preview.manifest, edit,
    )


def _create_new_version(root, manifest, raw):
    """Exclusive new-version directory, with best-effort cleanup on failure.

    If a process dies mid-copy, the *old* canonical project/pack remains intact,
    and a partial new-version directory blocks retry until explicitly inspected.
    No existing files are overwritten or removed.
    """
    directory = _version_root(root, manifest)
    if directory.exists() or directory.is_symlink():
        _reject("destination_exists", "New version appeared since preview")
    directory.mkdir()  # exclusive; never replace an existing version
    created = []
    try:
        with ZipFile(BytesIO(raw)) as archive:
            for row in manifest["files"]:
                relative = _path(row["path"])
                target = directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                # Ensure the path is still inside the version directory.
                if not target.parent.resolve(strict=True).is_relative_to(directory):
                    _reject("unsafe_destination", "New resource escaped version directory")
                digest = sha256()
                written = 0
                with archive.open("files/" + relative) as source, target.open("xb") as sink:
                    created.append(target)
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        written += len(block)
                        if written > row["bytes"]:
                            _reject("size_limit", "Resource exceeds declared size")
                        sink.write(block)
                        digest.update(block)
                    sink.flush()
                    os.fsync(sink.fileno())
                if written != row["bytes"] or digest.hexdigest() != row["sha256"]:
                    _reject("hash_mismatch", "Resource changed while staging")
    except BaseException:
        _cleanup(directory, created)
        raise
    return directory, created


def _cleanup(directory, created):
    """Delete *only* the paths this operation created, never legacy bytes."""
    for path in reversed(created):
        if not path.is_symlink() and path.is_file():
            path.unlink(missing_ok=True)
    for path in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
            except OSError:
                pass
    try:
        directory.rmdir()
    except OSError:
        pass


def apply_package_upgrade(preview, editor, project_root):
    """Revalidate all pins and the source snapshot; then apply ONE Undo step."""
    if not isinstance(preview, PackageUpgradePreview):
        _reject("invalid_preview", "Expected versioned upgrade preview")
    root = _project_root(project_root)
    snapshot, old = _snapshot_and_pack(editor, root, preview.package_id)
    if (snapshot["revision"] != preview.source_revision or
            _snapshot_digest(snapshot) != preview.source_digest or
            old["version"] != preview.previous_version or
            old["sha256"] != preview.previous_sha256):
        _reject("stale_preview", "Project or pack changed since version preview")
    raw = _read_archive(preview.archive_path)
    if sha256(raw).hexdigest() != preview.sha256:
        _reject("stale_preview", "Pack archive changed since version preview")
    checked = _inspect_raw(raw, preview.archive_path)
    if checked.manifest != preview._manifest:
        _reject("stale_preview", "Pack manifest changed since preview")
    manifest = thaw(checked.manifest)
    _check_compatibility(snapshot, old, manifest)
    reuse = _check_reusable(root, manifest)
    if reuse != preview.reuse_existing_bytes:
        _reject("stale_preview", "Version directory appeared/disappeared since preview")
    created_dir = None
    created_files = []
    try:
        if not reuse:
            created_dir, created_files = _create_new_version(root, manifest, raw)
        # Verify project-level provenance and every new resource BEFORE apply.
        candidate = thaw(preview._edit.project)
        problems = verify_installed_packs(root, candidate)
        if problems:
            _reject("invalid_candidate", "; ".join(problems[:8]))
        proposed = AssetRegistry(candidate.get("assets") or None)
        diagnostics = proposed.diagnostics(root)
        if diagnostics:
            _reject("invalid_candidate", str(diagnostics[0]["message"]))
        if (editor.revision != preview.source_revision or
                _snapshot_digest(editor.snapshot().to_dict()) != preview.source_digest):
            _reject("stale_preview", "Editor changed during installation")
        # No documents are saved; the preexisting on-disk project stays valid.
        return editor.apply(preview._edit)
    except BaseException:
        if created_dir is not None:
            _cleanup(created_dir, created_files)
        raise

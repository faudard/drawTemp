"""R58.B1: conservative package usage audit and reversible logical removal.

R24.C remains the sole asset registry, on-disk format and receipt authority.
No filesystem bytes are deleted on removal: an AuthoringSession Undo can restore
the exact project references without needing an unavailable archive or network.
Existing receipts do not record dependency edges, so multiple installed packs
block removal until a stronger provenance/dependency contract is available.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path

from drawtemp.assets.packs import RECEIPT_NAMESPACE, verify_installed_packs
from drawtemp.sdk.authoring import AuthoringPlan, AuthoringSession
from sporebound.assets import AssetRegistry

MAX_AUDIT_NODES = 100_000


class PackageManagerError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise PackageManagerError(code, message)


def _project_root(value):
    if value is None:
        _fail("missing_project_root", "Save/open a project directory before managing its packs")
    root = Path(value)
    if root.is_symlink() or not root.is_dir():
        _fail("invalid_project_root", "Expected an existing non-symlink project directory")
    return root.resolve(strict=True)


def _read_snapshot(editor, root):
    if not isinstance(editor, AuthoringSession):
        _fail("invalid_editor", "Use the canonical AuthoringSession")
    current = editor.snapshot().to_dict()
    project = current["project"]
    issues = verify_installed_packs(root, project)
    if issues:
        _fail("invalid_receipts", "; ".join(issues[:8]))
    extensions = project.get("extensions") or {}
    receipt = extensions.get(RECEIPT_NAMESPACE)
    installed = () if receipt is None else tuple(receipt["data"]["packs"])
    return current, installed


def _walk_refs(value, needles, *, prefix):
    """Conservative scan of canonical content and other GameProject metadata.

    Unknown extensions may carry string references. Never silently remove a
    pack if the same ID or physical path is used outside its own receipt/entries.
    A finite budget refuses unusually large or recursive inputs.
    """
    result = []
    pending = [(prefix, value)]
    seen = set()
    nodes = 0
    while pending:
        position, item = pending.pop()
        nodes += 1
        if nodes > MAX_AUDIT_NODES:
            _fail("audit_limit", "Project reference graph exceeds safety budget")
        if type(item) in (dict, list, tuple):
            if id(item) in seen:
                continue
            seen.add(id(item))
        if type(item) is dict:
            pending.extend(
                (position + "/" + str(key), entry)
                for key, entry in item.items()
            )
        elif type(item) in (list, tuple):
            pending.extend((position + "/" + str(index), entry)
                           for index, entry in enumerate(item))
        elif type(item) is str and any(
                item == needle or item.startswith("asset://" + needle)
                or item.startswith("asset:" + needle)
                for needle in needles):
            result.append(position)
    return tuple(sorted(set(result)))


def installed_package_usage(editor, project_root):
    """Pure UI-safe inspection with explicit blockers for each installed pack."""
    root = _project_root(project_root)
    snapshot, installed = _read_snapshot(editor, root)
    assets = AssetRegistry(snapshot["project"].get("assets") or None).to_dict()
    entries = assets["entries"]
    extensions = deepcopy(snapshot["project"].get("extensions") or {})
    extensions.pop(RECEIPT_NAMESPACE, None)
    remaining_project = deepcopy(snapshot["project"])
    remaining_project.pop("assets", None)
    remaining_project["extensions"] = extensions
    reports = []
    for receipt in sorted(installed, key=lambda item: item["id"]):
        pack_id = receipt["id"]
        own_ids = frozenset(receipt["asset_ids"])
        own_paths = frozenset(row["path"] for row in receipt["files"])
        blockers = []
        complete_graph = all("dependencies" in row for row in installed)
        if len(installed) > 1 and not complete_graph:
            # Unknown historical R24.C dependency edges: never guess.
            blockers.append("other-installed-pack-dependencies-unrecorded")
        if complete_graph:
            blockers.extend(
                "required-by:" + other["id"]
                for other in installed if other["id"] != pack_id
                for dep in other["dependencies"] if dep["id"] == pack_id
            )
        for kind, slots in sorted(assets["bindings"].items()):
            for slot, asset_id in sorted(slots.items()):
                if asset_id in own_ids:
                    blockers.append("binding:" + kind + "/" + slot)
        for entry in entries:
            if entry["id"] in own_ids:
                continue
            if entry["kind"] == "animation":
                for frame in entry["frames"]:
                    if frame["sprite"] in own_ids:
                        blockers.append("animation:" + entry["id"])
            elif entry["path"] in own_paths:
                # Different IDs may share one physical atlas. A remaining
                # entry would otherwise lose the original pack provenance.
                blockers.append("shared-path:" + entry["id"])
        blockers.extend("reference:" + path for path in _walk_refs(
            snapshot["content"], own_ids | own_paths, prefix="content"))
        blockers.extend("reference:" + path for path in _walk_refs(
            remaining_project, own_ids | own_paths, prefix="project"))
        reports.append({
            "id": pack_id, "version": receipt["version"],
            "sha256": receipt["sha256"],
            "asset_ids": sorted(own_ids),
            "files": sorted(own_paths),
            "used_by": sorted(set(blockers)),
            "removable": not blockers,
            "reverse_dependencies_verified": complete_graph,
            "direct_dependencies": (
                deepcopy(receipt["dependencies"])
                if "dependencies" in receipt else None
            ),
            "upgradable": (
                len(installed) == 1 or
                (complete_graph and not any(
                    dep["id"] == pack_id for other in installed
                    if other["id"] != pack_id for dep in other["dependencies"]
                ))
            ),
            "file_policy": "retain-for-undo",
            "rights_verified": False,
        })
    return tuple(reports)


def _snapshot_digest(snapshot):
    blob = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)
    return sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PackageRemovalPreview:
    package_id: str
    version: str
    sha256: str
    source_revision: int
    source_digest: str
    asset_ids: tuple[str, ...]
    files_retained: tuple[str, ...]
    _plan: AuthoringPlan = field(repr=False, compare=False)

    def to_dict(self):
        return {
            "operation": "remove-package-references",
            "id": self.package_id, "version": self.version,
            "sha256": self.sha256, "source_revision": self.source_revision,
            "asset_ids_removed": list(self.asset_ids),
            "files_retained": list(self.files_retained),
            "filesystem_deleted": False,
            "reversible_via_editor_undo": True,
            "requires_explicit_save": True,
            "rights_verified": False,
        }


def preview_package_removal(editor, project_root, pack_id, *, expected_revision=None):
    """Prepare one validated, reversible edit; refuse unknown consumers."""
    root = _project_root(project_root)
    current, installed = _read_snapshot(editor, root)
    if type(pack_id) is not str or not pack_id:
        _fail("invalid_package", "A package id is required")
    if expected_revision is not None and (
            type(expected_revision) is not int or editor.revision != expected_revision):
        _fail("stale_revision", "Refresh the Studio before removing a package")
    report = next((item for item in installed_package_usage(editor, root)
                   if item["id"] == pack_id), None)
    if report is None:
        _fail("unknown_package", "Package is not installed")
    if not report["removable"]:
        _fail("package_in_use", "; ".join(report["used_by"]))
    ids = frozenset(report["asset_ids"])

    def transform(project):
        registry = project.get("assets")
        if type(registry) is not dict:
            _fail("invalid_registry", "Installed pack has no asset registry")
        registry["entries"] = [
            entry for entry in registry["entries"] if entry["id"] not in ids
        ]
        extensions = project["extensions"]
        record = extensions[RECEIPT_NAMESPACE]["data"]["packs"]
        record[:] = [entry for entry in record if entry["id"] != pack_id]
        if not record:
            del extensions[RECEIPT_NAMESPACE]
        # Keep other entries/bindings/metadata exactly unchanged.
        if not registry["entries"] and not registry["bindings"]:
            del project["assets"]
        return project

    try:
        edit = editor.preview_project(transform, kind="r58.package-remove")
    except (ValueError, TypeError, KeyError) as exc:
        _fail("invalid_candidate", str(exc))
    if edit.source_revision != current["revision"]:
        _fail("stale_revision", "Project changed during preview")
    return PackageRemovalPreview(
        pack_id, report["version"], report["sha256"],
        current["revision"], _snapshot_digest(current),
        tuple(report["asset_ids"]), tuple(report["files"]), edit,
    )


def apply_package_removal(preview, editor, project_root):
    """Revalidate project/physical receipts, then create ONE editor Undo entry.

    Physical files intentionally remain in place. Deleting them would break
    AuthoringSession.undo() and historical project replays/backup restore.
    """
    if not isinstance(preview, PackageRemovalPreview):
        _fail("invalid_preview", "Expected a removal preview")
    root = _project_root(project_root)
    current, _ = _read_snapshot(editor, root)
    if (editor.revision != preview.source_revision or
            _snapshot_digest(current) != preview.source_digest):
        _fail("stale_preview", "Project changed since removal was previewed")
    report = next((item for item in installed_package_usage(editor, root)
                   if item["id"] == preview.package_id), None)
    if (report is None or not report["removable"] or
            report["version"] != preview.version or
            report["sha256"] != preview.sha256 or
            tuple(report["asset_ids"]) != preview.asset_ids or
            tuple(report["files"]) != preview.files_retained):
        _fail("stale_preview", "Pack integrity, uses or receipts changed")
    return editor.apply(preview._plan)

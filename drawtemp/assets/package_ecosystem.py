"""R58.A — read-only, fail-closed planning for R24.C resource packages.

This deliberately reuses the single R24.C archive/AssetRegistry/receipt contract.
A digest pin proves byte identity, not author identity or legal redistribution.
No download, extraction, executable code, filesystem write or grant occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re

from drawtemp.assets.packs import (
    RECEIPT_NAMESPACE, PackPreview, ResourcePackError,
    inspect_pack, verify_installed_packs,
)
from drawtemp.sdk.simulation import thaw

MAX_PLAN_PACKS = 64
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PACK_ID = re.compile(r"[a-z][a-z0-9-]{2,47}\Z")


class PackagePlanError(ValueError):
    """Stable diagnostics suitable for a future native Package Manager."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code: str, message: str):
    raise PackagePlanError(code, message)


@dataclass(frozen=True)
class PlannedPackage:
    preview: PackPreview
    pack_id: str
    version: str
    sha256: str
    dependencies: tuple[tuple[str, str, str], ...]
    license_assertions: tuple[tuple[str, str, str], ...]

    def to_dict(self) -> dict:
        return {
            "id": self.pack_id,
            "version": self.version,
            "sha256": self.sha256,
            "dependencies": [
                {"id": pack_id, "version": version, "sha256": digest}
                for pack_id, version, digest in self.dependencies
            ],
            "license_assertions": [
                {"path": path, "license_id": license_id, "rights_holder": owner}
                for path, license_id, owner in self.license_assertions
            ],
            "integrity": "verified-at-preview",
            "authenticity": "not-verified",
            "rights_verified": False,
            "executable": False,
        }


@dataclass(frozen=True)
class PackageInstallPlan:
    """Dependency-first immutable preview. Re-inspect at the time of apply."""

    packages: tuple[PlannedPackage, ...]
    fingerprint: str

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "kind": "drawtemp-r58-install-plan",
            "fingerprint": self.fingerprint,
            "packages": [item.to_dict() for item in self.packages],
            "permissions_granted": [],
            "signature_verified": False,
            "rights_verified": False,
            "export_approved": False,
            "side_effects": False,
        }


def _installed_receipts(project: dict, root: Path) -> dict:
    if type(project) is not dict:
        _fail("invalid_project", "Expected canonical GameProject dictionary")
    extensions = project.get("extensions", {})
    if type(extensions) is not dict:
        _fail("invalid_project", "Invalid GameProject extensions")
    problems = verify_installed_packs(root, project)
    if problems:
        _fail("invalid_receipts", "; ".join(problems[:5]))
    record = extensions.get(RECEIPT_NAMESPACE)
    if record is None:
        return {}
    # verify_installed_packs checked receipt shape, referenced IDs and on-disk bytes.
    return {row["id"]: row for row in record["data"]["packs"]}


def plan_package_install(
    archives,
    *,
    project_root,
    project: dict,
    expected_sha256: dict[str, str],
) -> PackageInstallPlan:
    """Check local pack bytes, caller-supplied pins and dependency closure.

    `expected_sha256` MUST be obtained independently of the untrusted archives.
    A dependency may already be installed (with the exact version and SHA-256)
    or be provided as another archive in the plan. There is no auto-download,
    newest-version selection or inferred permission/rights approval.
    """
    if type(archives) not in (list, tuple) or not 1 <= len(archives) <= MAX_PLAN_PACKS:
        _fail("invalid_input", "Supply 1..64 explicit local archives")
    if type(expected_sha256) is not dict or len(expected_sha256) != len(archives):
        _fail("missing_pin", "Require one independently obtained SHA-256 per archive")
    for name, digest in expected_sha256.items():
        if (type(name) is not str or not _PACK_ID.fullmatch(name) or
                type(digest) is not str or not _SHA256.fullmatch(digest)):
            _fail("invalid_pin", "Pins require portable IDs and lowercase SHA-256")

    root = Path(project_root)
    if root.is_symlink() or not root.is_dir():
        _fail("invalid_project", "Project root must be a regular local directory")
    existing = _installed_receipts(project, root)
    available: dict[str, PlannedPackage] = {}
    for archive in archives:
        if not isinstance(archive, (str, Path)):
            _fail("invalid_input", "Archive must be a local filesystem path")
        path = Path(archive)
        if path.is_symlink() or not path.is_file():
            _fail("unsafe_archive", "Archive must be a regular, non-symlink file")
        try:
            preview = inspect_pack(path)
        except ResourcePackError as exc:
            raise PackagePlanError("invalid_archive", str(exc)) from exc
        manifest = thaw(preview.manifest)
        identity = manifest["id"]
        if identity in available:
            _fail("duplicate_package", "Only one version per package ID is allowed")
        if identity in existing:
            _fail("already_installed", "Use a separate explicit migration for " + identity)
        if identity not in expected_sha256:
            _fail("missing_pin", "Missing independently supplied digest for " + identity)
        if preview.sha256 != expected_sha256[identity]:
            _fail("digest_mismatch", "Untrusted archive differs from pinned bytes: " + identity)
        deps = tuple(sorted(
            (dep["id"], dep["version"], dep["sha256"])
            for dep in manifest["dependencies"]
        ))
        rights = tuple(sorted(
            (entry["path"], entry["license"]["id"], entry["license"]["rights_holder"])
            for entry in manifest["files"]
        ))
        available[identity] = PlannedPackage(
            preview, identity, manifest["version"], preview.sha256, deps, rights
        )
    if set(available) != set(expected_sha256):
        _fail("invalid_pin", "Unexpected pin outside the selected archive set")

    for item in available.values():
        for dep_id, version, digest in item.dependencies:
            dependency = available.get(dep_id)
            installed = existing.get(dep_id)
            if dependency is not None:
                actual = (dependency.version, dependency.sha256)
            elif installed is not None:
                actual = (installed["version"], installed["sha256"])
            else:
                _fail("missing_dependency", item.pack_id + " requires " + dep_id)
            if actual != (version, digest):
                _fail("dependency_conflict", item.pack_id + " needs a different " + dep_id)

    state: dict[str, int] = {}
    ordered: list[PlannedPackage] = []

    def visit(pack_id: str):
        if state.get(pack_id) == 1:
            _fail("dependency_cycle", "Pack dependency cycle contains " + pack_id)
        if state.get(pack_id) == 2:
            return
        state[pack_id] = 1
        item = available[pack_id]
        for dep_id, _, _ in item.dependencies:
            if dep_id in available:
                visit(dep_id)
        state[pack_id] = 2
        ordered.append(item)

    for pack_id in sorted(available):
        visit(pack_id)
    record = [
        {"id": item.pack_id, "version": item.version,
         "sha256": item.sha256,
         "dependencies": [
             {"id": dep_id, "version": version, "sha256": digest}
             for dep_id, version, digest in item.dependencies
         ]}
        for item in ordered
    ]
    fingerprint = sha256(json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")).hexdigest()
    return PackageInstallPlan(tuple(ordered), fingerprint)

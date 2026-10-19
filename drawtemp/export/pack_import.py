"""R30.B: safe, opt-in import of inert creator pack assets to a NEW project copy.

An import is never applied to a live project directory. A preview validates
the archive and canonical GameProject assets; execution revalidates the same
inputs, stages documents/resources, performs the R15 preflight, then publishes
one new directory. No plugin code executes, no licensing is auto-approved.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from tempfile import TemporaryDirectory
import zipfile
import zlib

from drawtemp.export.creator_packs import (
    MAX_TOTAL_BYTES, MAX_MANIFEST_BYTES, PackError, _read_and_verify,
)
from drawtemp.export.r15 import preflight, project_path
from drawtemp.quality.r14 import safe_asset_path
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.assets import AssetRegistry, EXTENSIONS
from sporebound.studio_transaction import validate_pair

_ASSET_KINDS = frozenset({"sprite", "portrait", "sound"})
_LOCAL_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_COMPRESSED_BUDGET = MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES + 2 * 1024 * 1024


class PackImportError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class AssetSelection:
    path: str
    kind: str
    name: str
    asset_id: str
    target_path: str

    def to_dict(self):
        return {"path": self.path, "kind": self.kind, "name": self.name,
                "asset_id": self.asset_id, "target_path": self.target_path}


@dataclass(frozen=True)
class PackImportPreview:
    content_path: str
    archive_path: str
    source_content_sha256: str
    source_project_sha256: str
    source_asset_hashes: tuple[tuple[str, str], ...]
    archive_sha256: str
    pack_id: str
    pack_version: str
    selections: tuple[AssetSelection, ...]
    candidate_fingerprint: str

    def to_dict(self):
        return {
            "source_content": self.content_path,
            "archive_sha256": self.archive_sha256,
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "selections": [selection.to_dict() for selection in self.selections],
            "source_asset_count": len(self.source_asset_hashes),
            "rights_verified": False,
            "mode": "new-project-copy",
        }


def _hash(data: bytes) -> str:
    return sha256(data).hexdigest()


def _filehash(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _archive(path: Path):
    if path.is_symlink() or not path.is_file():
        raise PackImportError("missing_pack", "Require a regular, non-symlink ZIP")
    try:
        if path.stat().st_size > _COMPRESSED_BUDGET:
            raise PackImportError("oversized_pack", "Compressed ZIP too large")
        data = path.read_bytes()
        if len(data) > _COMPRESSED_BUDGET:
            raise PackImportError("oversized_pack", "Compressed ZIP too large")
        with zipfile.ZipFile(BytesIO(data), "r") as archive:
            checked = _read_and_verify(archive)
        return data, checked["manifest"]
    except (OSError, zipfile.BadZipFile, RuntimeError,
            NotImplementedError, EOFError, zlib.error, PackError) as exc:
        raise PackImportError("invalid_pack", str(exc)) from exc


def _source_snapshot(content_path: Path):
    if content_path.is_symlink() or not content_path.is_file():
        raise PackImportError("missing_source", "Content must be a regular file")
    game_path = project_path(content_path)
    if game_path.is_symlink() or not game_path.is_file():
        raise PackImportError("missing_source", "GameProject must be a regular file")
    result = preflight(content_path)
    if not result["passed"]:
        raise PackImportError("invalid_source", "; ".join(result["errors"]))
    content_data, project_data = validate_pair(
        json.loads(content_path.read_text(encoding="utf-8")),
        json.loads(game_path.read_text(encoding="utf-8")),
    )
    hashes = []
    for relative in result["assets"]:
        asset_path = safe_asset_path(content_path.parent, relative)
        hashes.append((relative, _filehash(asset_path)))
    return (content_data, project_data, _filehash(content_path),
            _filehash(game_path), tuple(sorted(hashes)))


def _select(document: dict, bindings, project: dict):
    if not isinstance(bindings, (list, tuple)) or not 1 <= len(bindings) <= 128:
        raise PackImportError("invalid_selections", "Select 1..128 resources")
    known = {entry["path"]: entry for entry in document["files"]}
    existing = AssetRegistry(project.get("assets") or None).to_dict()
    known_ids = {entry["id"].casefold() for entry in existing["entries"]}
    known_paths = {entry["path"].casefold() for entry in existing["entries"]
                   if entry["kind"] != "animation"}
    selections = []
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != {"path", "kind", "name"}:
            raise PackImportError("invalid_selections", "Require path, kind, name")
        path, kind, name = binding["path"], binding["kind"], binding["name"]
        if not isinstance(path, str) or path not in known:
            raise PackImportError("unknown_resource", "Unlisted pack resource")
        if not isinstance(kind, str) or kind not in _ASSET_KINDS:
            raise PackImportError("unsupported_asset", "Registry supports sprite/portrait/sound")
        if not isinstance(name, str) or not _LOCAL_ID.fullmatch(name):
            raise PackImportError("invalid_id", "Use a simple lower-case resource name")
        if PurePosixPath(path).suffix.lower() not in EXTENSIONS[kind]:
            raise PackImportError("unsupported_asset", "Kind does not match resource type")
        asset_id = document["id"] + "." + name
        target = "packs/" + document["id"] + "/" + document["version"] + "/" + path
        if asset_id.casefold() in known_ids or target.casefold() in known_paths:
            raise PackImportError("collision", "Asset id or target path already exists")
        known_ids.add(asset_id.casefold())
        known_paths.add(target.casefold())
        selections.append(AssetSelection(path, kind, name, asset_id, target))
    return tuple(sorted(selections, key=lambda item: item.asset_id))


def _candidate(content: dict, project: dict, selections: tuple[AssetSelection, ...]):
    updated = deepcopy(project)
    registry = AssetRegistry(updated.get("assets") or None).to_dict()
    for selected in selections:
        registry["entries"].append({
            "id": selected.asset_id, "kind": selected.kind, "path": selected.target_path,
        })
    updated["assets"] = registry
    # Canonical R1/Content/GameProject validation, no secondary registry.
    checked_content, checked_project = validate_pair(content, updated)
    if checked_content != content:
        raise PackImportError("invalid_candidate", "Import must not edit game rules")
    return checked_project


def _fingerprint(value) -> str:
    return _hash(json.dumps(value, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":")).encode("utf-8"))


def preview_pack_import(content_path, archive_path, bindings) -> PackImportPreview:
    """Read-only preflight, including a canonical candidate GameProject validation."""
    source = Path(content_path).absolute()
    archive_path = Path(archive_path).absolute()
    content, project, c_hash, p_hash, asset_hashes = _source_snapshot(source)
    pack_bytes, manifest = _archive(archive_path)
    selections = _select(manifest, bindings, project)
    updated = _candidate(content, project, selections)
    return PackImportPreview(str(source), str(archive_path), c_hash, p_hash,
                             asset_hashes, _hash(pack_bytes),
                             manifest["id"], manifest["version"], selections,
                             _fingerprint(updated))


def _verify_selected_bytes(data, manifest, selections):
    by_path = {entry["path"]: entry for entry in manifest["files"]}
    selected = {}
    with zipfile.ZipFile(BytesIO(data), "r") as archive:
        for item in selections:
            raw = archive.read(item.path)
            expected = by_path[item.path]
            if len(raw) != expected["size"] or _hash(raw) != expected["sha256"]:
                raise PackImportError("pack_changed", "Selected resource digest mismatch")
            if item.kind in ("sprite", "portrait"):
                valid = raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24
            elif item.target_path.endswith(".ogg"):
                valid = raw.startswith(b"OggS")
            else:
                valid = len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WAVE"
            if not valid:
                raise PackImportError("invalid_asset", item.path + ": invalid file signature")
            selected[item.target_path] = raw
    return selected


def import_pack_to_copy(preview: PackImportPreview, destination):
    """Stage and publish a *new* project; never edit source or overwrite target.

    Revalidation catches changed input documents, resources, archive and any
    modified preview. A failed build leaves no output project.
    """
    if not isinstance(preview, PackImportPreview):
        raise PackImportError("invalid_preview", "Expected a read-only import preview")
    source = Path(preview.content_path)
    archive_path = Path(preview.archive_path)
    dest = Path(destination).absolute()
    root = source.parent.resolve(strict=True)
    # Never stage inside the source project's root or overwrite the project.
    if dest == root or root in dest.parents:
        raise PackImportError("invalid_destination", "Output must be outside source project")
    if dest.exists() or dest.is_symlink():
        raise PackImportError("destination_exists", "Existing destination not replaced")
    content, project, c_hash, p_hash, asset_hashes = _source_snapshot(source)
    if (c_hash != preview.source_content_sha256 or
            p_hash != preview.source_project_sha256 or
            asset_hashes != preview.source_asset_hashes):
        raise PackImportError("source_changed", "Source changed since the import preview")
    data, manifest = _archive(archive_path)
    if (_hash(data) != preview.archive_sha256 or
            manifest["id"] != preview.pack_id or
            manifest["version"] != preview.pack_version):
        raise PackImportError("pack_changed", "Pack changed since the import preview")
    source_bindings = [
        {"path": entry.path, "kind": entry.kind, "name": entry.name}
        for entry in preview.selections
    ]
    expected_selections = _select(manifest, source_bindings, project)
    if expected_selections != preview.selections:
        raise PackImportError("preview_changed", "Selections changed after review")
    updated_project = _candidate(content, project, expected_selections)
    if _fingerprint(updated_project) != preview.candidate_fingerprint:
        raise PackImportError("preview_changed", "Candidate project changed after review")
    payloads = _verify_selected_bytes(data, manifest, expected_selections)

    dest.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".drawtemp-r30b-", dir=dest.parent) as folder:
        stage = Path(folder) / "project"
        stage.mkdir()
        for relative, expected_hash in asset_hashes:
            asset = safe_asset_path(root, relative)
            if _filehash(asset) != expected_hash:
                raise PackImportError("source_changed", "Asset changed since review")
            target = stage / PurePosixPath(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset, target)
            if _filehash(target) != expected_hash:
                raise PackImportError("source_changed", "Copied source asset mismatch")
        for relative, payload in payloads.items():
            target = stage / PurePosixPath(relative)
            if target.exists() or target.is_symlink():
                raise PackImportError("collision", "Target resource already exists")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as sink:
                sink.write(payload)

        # Preserve existing rights index and evidence, but never add unapproved
        # attestations for the imported files.
        initial = preflight(source)
        for relative in ["asset-licenses.json", *initial["rights_evidence"]]:
            existing = root / PurePosixPath(relative)
            if existing.is_file():
                target = stage / PurePosixPath(relative)
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(safe_asset_path(root, relative), target)

        session = AuthoringSession.new(content, project)
        plan = session.preview_project(lambda _project: deepcopy(updated_project),
                                       kind="r30b-pack-import")
        session.apply(plan)
        session.save_as(stage / source.name)

        report = preflight(stage / source.name)
        if not report["passed"]:
            raise PackImportError("staged_preflight", "; ".join(report["errors"]))
        expected_assets = sorted([item[0] for item in asset_hashes] + list(payloads))
        if sorted(report["assets"]) != expected_assets:
            raise PackImportError("staged_preflight", "Imported asset inventory changed")
        if _filehash(source) != c_hash or _filehash(project_path(source)) != p_hash:
            raise PackImportError("source_changed", "Source changed during staging")
        for relative, expected_hash in asset_hashes:
            if _filehash(safe_asset_path(root, relative)) != expected_hash:
                raise PackImportError("source_changed", "Source assets changed during staging")

        (stage / "r30-pack-import-report.json").write_text(
            json.dumps({
                "schema": 1, "pack_id": preview.pack_id,
                "pack_version": preview.pack_version,
                "pack_sha256": preview.archive_sha256,
                "asset_ids": [entry.asset_id for entry in expected_selections],
                "rights_verified": False, "release_certified": False,
                "source_modified": False,
            }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if dest.exists() or dest.is_symlink():
            raise PackImportError("destination_exists", "Destination appeared during staging")
        os.rename(stage, dest)
    return dest

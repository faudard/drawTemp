"""R30.2 — auditable, inert creator resource packs.

A pack is a ZIP of manifest.json plus explicitly listed inert resource bytes.
Inspection verifies integrity; it never extracts, imports or executes a plugin.
A self-declared SPDX identifier or source is NOT legal clearance for release.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
import zlib

from drawtemp.sdk.capability_contracts import CapabilityError, require_sdk

PACK_SCHEMA = 1
MAX_FILES = 256
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 128 * 1024
_ALLOWED_TYPES = {".json", ".png", ".jpg", ".jpeg", ".webp",
                  ".ogg", ".wav", ".md", ".txt"}
_KINDS = {"template", "quest", "enemy", "terrain", "puzzle", "hud", "mixed"}
_ID = re.compile(r"[a-z][a-z0-9-]{2,63}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_LICENSE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]{1,63}\Z")
_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


class PackError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class PackInspection:
    pack_id: str
    version: str
    kind: str
    files: tuple[str, ...]
    total_bytes: int
    archive_sha256: str
    sdk_status: str

    def to_dict(self) -> dict:
        return {
            "id": self.pack_id, "version": self.version, "kind": self.kind,
            "files": list(self.files), "total_bytes": self.total_bytes,
            "sha256": self.archive_sha256, "sdk_status": self.sdk_status,
            "rights_verified": False, "executable": False,
        }


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackError("duplicate_json_key", "Manifest has duplicate keys")
        result[key] = value
    return result


def _safe_path(value: object) -> str:
    if (not isinstance(value, str) or len(value) > 220 or
            not value.isascii() or "\\" in value or ":" in value or
            value.startswith("/") or "\x00" in value):
        raise PackError("unsafe_path", "Pack path must be a relative POSIX path")
    parts = PurePosixPath(value).parts
    if (not parts or any(part in (".", "..") or not _PART.fullmatch(part)
                         for part in parts) or "/".join(parts) != value or
            len(parts) > 12 or PurePosixPath(value).suffix.lower() not in _ALLOWED_TYPES):
        raise PackError("unsafe_path", "Only inert resource files are allowed")
    if value == "manifest.json":
        raise PackError("unsafe_path", "Manifest must not be duplicated as a resource")
    return value


def validate_manifest(document: dict) -> dict:
    """Validate exact versioned schema, SDK needs, bytes and rights declarations."""
    if not isinstance(document, dict) or set(document) != {
            "schema", "id", "version", "kind", "requires", "files"}:
        raise PackError("invalid_manifest", "Unexpected pack manifest fields")
    if type(document["schema"]) is not int or document["schema"] != PACK_SCHEMA:
        raise PackError("unsupported_schema", "Unsupported pack schema")
    if not isinstance(document["id"], str) or not _ID.fullmatch(document["id"]):
        raise PackError("invalid_id", "Invalid pack namespace")
    from drawtemp.sdk.capability_contracts import parse_semver
    try:
        parse_semver(document["version"])
    except CapabilityError as exc:
        raise PackError(exc.code, str(exc)) from exc
    if not isinstance(document["kind"], str) or document["kind"] not in _KINDS:
        raise PackError("invalid_kind", "Unknown pack kind")
    requirements = document["requires"]
    if not isinstance(requirements, dict) or set(requirements) != {
            "min_api", "max_api", "features"}:
        raise PackError("invalid_requirements", "Expected version range and features")
    if not isinstance(requirements["features"], list):
        raise PackError("invalid_requirements", "Features must be a list")
    try:
        compat = require_sdk(min_api=requirements["min_api"],
                             max_api=requirements["max_api"],
                             required_features=requirements["features"])
    except CapabilityError as exc:
        raise PackError("incompatible_sdk", str(exc)) from exc
    files = document["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise PackError("invalid_files", "Pack must have a bounded nonempty file list")
    seen = set()
    total = 0
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {
                "path", "sha256", "size", "license", "origin"}:
            raise PackError("invalid_file", "Missing provenance or hash")
        name = _safe_path(entry["path"])
        if name.casefold() in seen:
            raise PackError("duplicate_path", "Duplicate pack filename")
        seen.add(name.casefold())
        if (not isinstance(entry["sha256"], str) or
                not _DIGEST.fullmatch(entry["sha256"])):
            raise PackError("invalid_hash", "Expected lower-case SHA-256")
        size = entry["size"]
        if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
            raise PackError("invalid_size", "Oversized resource")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise PackError("pack_too_large", "Uncompressed pack exceeds budget")
        if (not isinstance(entry["license"], str) or
                not _LICENSE.fullmatch(entry["license"])):
            raise PackError("invalid_license", "Explicit SPDX identifier required")
        if (not isinstance(entry["origin"], str) or
                not 1 <= len(entry["origin"]) <= 500 or
                any(ord(ch) < 32 for ch in entry["origin"])):
            raise PackError("invalid_origin", "Every asset needs provenance")
    return {"manifest": document, "compatibility": compat, "total_bytes": total}


def _read_and_verify(archive: zipfile.ZipFile):
    entries = archive.infolist()
    if not 2 <= len(entries) <= MAX_FILES + 1:
        raise PackError("invalid_archive", "Unexpected number of ZIP entries")
    names = {}
    for info in entries:
        if (info.is_dir() or info.flag_bits & 1 or
                stat.S_IFMT(info.external_attr >> 16) not in (0, stat.S_IFREG)):
            raise PackError("invalid_archive", "Directory, encryption or symlink rejected")
        name = info.filename
        if name != "manifest.json":
            _safe_path(name)
        if name.casefold() in names:
            raise PackError("duplicate_path", "Duplicate archive member")
        names[name.casefold()] = info
        if info.file_size > MAX_FILE_BYTES and name != "manifest.json":
            raise PackError("pack_too_large", "Resource is too large")
        if info.file_size > MAX_MANIFEST_BYTES and name == "manifest.json":
            raise PackError("pack_too_large", "Manifest too large")
    manifest_info = names.get("manifest.json")
    if manifest_info is None:
        raise PackError("missing_manifest", "manifest.json is mandatory")
    raw = archive.read(manifest_info)
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json)
    except (UnicodeError, ValueError) as exc:
        raise PackError("invalid_json", str(exc)) from exc
    checked = validate_manifest(parsed)
    declared = {entry["path"] for entry in parsed["files"]}
    if set(info.filename for info in entries) != declared | {"manifest.json"}:
        raise PackError("unlisted_file", "Archive and manifest file lists disagree")
    for entry in parsed["files"]:
        info = names[entry["path"].casefold()]
        if info.file_size != entry["size"]:
            raise PackError("size_mismatch", entry["path"])
        # Bounded input and declared-size checks precede decompression.
        with archive.open(info) as stream:
            raw_data = stream.read(entry["size"] + 1)
        if (len(raw_data) != entry["size"] or
                hashlib.sha256(raw_data).hexdigest() != entry["sha256"]):
            raise PackError("hash_mismatch", entry["path"])
    return checked


def inspect_pack(path: str | Path) -> PackInspection:
    """Verify an inert pack on disk; never unpack it or grant asset rights."""
    path = Path(path)
    try:
        if path.stat().st_size > MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES + 2 * 1024 * 1024:
            raise PackError("pack_too_large", "Compressed pack budget exceeded")
        # Read one bounded snapshot: a modified ZIP cannot borrow validation
        # from old bytes while reporting the checksum of new bytes.
        archive_bytes = path.read_bytes()
        if len(archive_bytes) > MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES + 2 * 1024 * 1024:
            raise PackError("pack_too_large", "Compressed pack budget exceeded")
        with zipfile.ZipFile(BytesIO(archive_bytes), "r") as archive:
            checked = _read_and_verify(archive)
        digest = hashlib.sha256(archive_bytes).hexdigest()
    except (OSError, zipfile.BadZipFile, RuntimeError, EOFError,
            NotImplementedError, zlib.error) as exc:
        raise PackError("invalid_archive", str(exc)) from exc
    doc = checked["manifest"]
    return PackInspection(doc["id"], doc["version"], doc["kind"],
                          tuple(item["path"] for item in doc["files"]),
                          checked["total_bytes"], digest,
                          checked["compatibility"].status)


def build_pack(source_dir: str | Path, output: str | Path, manifest: dict) -> Path:
    """Build a deterministic, verified ZIP from resources already on disk.

    Will never replace an existing output. Does not prove redistribution rights.
    """
    validate_manifest(manifest)
    source = Path(source_dir).resolve()
    output = Path(output)
    if output.exists():
        raise PackError("destination_exists", "Refusing to overwrite a pack")
    files_data = []
    for item in manifest["files"]:
        relative = _safe_path(item["path"])
        candidate = source.joinpath(*PurePosixPath(relative).parts)
        if (not candidate.is_file() or candidate.is_symlink() or
                not candidate.resolve().is_relative_to(source) or
                any((source / PurePosixPath(*PurePosixPath(relative).parts[:i])).is_symlink()
                    for i in range(1, len(PurePosixPath(relative).parts)))):
            raise PackError("unsafe_source", relative)
        if candidate.stat().st_size != item["size"]:
            raise PackError("hash_mismatch", relative)
        data = candidate.read_bytes()
        if (len(data) != item["size"] or
                hashlib.sha256(data).hexdigest() != item["sha256"]):
            raise PackError("hash_mismatch", relative)
        files_data.append((relative, data))
    manifest_bytes = (json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":")) + "\n").encode("utf-8")
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise PackError("pack_too_large", "Manifest too large")
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        # Exclusive creation: even a concurrent writer's existing pack survives.
        with output.open("xb") as sink:
            created = True
            with zipfile.ZipFile(sink, "w") as archive:
                for name, data in [("manifest.json", manifest_bytes), *sorted(files_data)]:
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data)
        inspect_pack(output)
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
    return output

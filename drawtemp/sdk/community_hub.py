"""R69 — opt-in, offline Community Creator Hub for inert R30 creator packs.

The catalogue is metadata, not a trust store. It neither downloads resources
nor executes code. Authors retain the existing pack builder and the R30.B
copy-only importer; this layer supplies immutable local distribution, explicit
acquisition, version discovery and persistent withdrawal tombstones.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
from tempfile import NamedTemporaryFile
import zipfile

from drawtemp.export.creator_packs import (
    MAX_MANIFEST_BYTES, MAX_TOTAL_BYTES, PackError, inspect_pack, validate_manifest,
)
from drawtemp.sdk.capability_contracts import CapabilityError, parse_semver

CATALOG_SCHEMA = 1
MAX_CATALOG_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES + 2 * 1024 * 1024
_ID = re.compile(r"[a-z][a-z0-9-]{2,63}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_PUBLISHER = re.compile(r"[a-z][a-z0-9-]{2,63}\Z")
_KINDS = frozenset({"template", "quest", "enemy", "terrain", "puzzle", "hud", "mixed"})
_ENTRY_KEYS = frozenset({
    "id", "version", "kind", "sha256", "size", "publisher",
    "licenses", "origins", "declaration", "legal_clearance",
    "status", "withdrawal_reason",
})


class HubError(ValueError):
    """Stable reason code for CLI and future host-owned Studio UI."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise HubError(code, message)


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("invalid_catalog", "Duplicate JSON key")
        result[key] = value
    return result


def _version(value):
    try:
        return parse_semver(value)
    except (CapabilityError, TypeError, ValueError) as exc:
        raise HubError("invalid_version", "Expected exact MAJOR.MINOR.PATCH") from exc


def _validate_entry(row):
    if type(row) is not dict or set(row) != _ENTRY_KEYS:
        _fail("invalid_catalog", "Unexpected or missing catalogue fields")
    if type(row["id"]) is not str or not _ID.fullmatch(row["id"]):
        _fail("invalid_catalog", "Invalid pack id")
    _version(row["version"])
    if type(row["kind"]) is not str or row["kind"] not in _KINDS:
        _fail("invalid_catalog", "Invalid pack kind")
    if type(row["sha256"]) is not str or not _SHA.fullmatch(row["sha256"]):
        _fail("invalid_catalog", "Invalid SHA-256")
    if type(row["size"]) is not int or not 0 < row["size"] <= MAX_ARCHIVE_BYTES:
        _fail("invalid_catalog", "Invalid compressed size")
    if type(row["publisher"]) is not str or not _PUBLISHER.fullmatch(row["publisher"]):
        _fail("invalid_catalog", "Invalid publisher label")
    for key in ("licenses", "origins"):
        values = row[key]
        if (type(values) is not list or not values or len(values) > 256 or
                any(type(s) is not str or not s or len(s) > 500 or
                    any(ord(ch) < 32 for ch in s) for s in values) or
                values != sorted(set(values))):
            _fail("invalid_catalog", "Invalid " + key)
    if (type(row["declaration"]) is not str or
            not 10 <= len(row["declaration"]) <= 500 or
            any(ord(ch) < 32 for ch in row["declaration"])):
        _fail("invalid_catalog", "A bounded rights declaration is required")
    if row["legal_clearance"] is not False:
        _fail("invalid_catalog", "Catalogue cannot assert legal clearance")
    if row["status"] not in ("available", "withdrawn"):
        _fail("invalid_catalog", "Unknown moderation state")
    reason = row["withdrawal_reason"]
    if (type(reason) is not str or len(reason) > 300 or
            any(ord(ch) < 32 for ch in reason) or
            (row["status"] == "withdrawn") != bool(reason)):
        _fail("invalid_catalog", "Withdrawal must be explained; active entries cannot have a reason")


def _catalog_document(document):
    if type(document) is not dict or set(document) != {"schema", "packs"}:
        _fail("invalid_catalog", "Catalogue must have schema and packs only")
    if type(document["schema"]) is not int or document["schema"] != CATALOG_SCHEMA:
        _fail("unsupported_schema", "Unsupported catalogue schema")
    rows = document["packs"]
    if type(rows) is not list or len(rows) > 2048:
        _fail("invalid_catalog", "Catalogue entry budget exceeded")
    seen = set()
    for row in rows:
        _validate_entry(row)
        key = (row["id"], row["version"])
        if key in seen:
            _fail("duplicate_release", "Catalogue contains duplicate release")
        seen.add(key)
    # Detached data: callers cannot alter the on-disk index through returned rows.
    return {"schema": CATALOG_SCHEMA, "packs": sorted(
        (dict(row) for row in rows), key=lambda r: (r["id"], _version(r["version"])))}


def _root(directory):
    root = Path(directory).absolute()
    if root.is_symlink():
        _fail("unsafe_path", "Catalogue root cannot be a symlink")
    return root


def read_catalog(directory):
    """Read a bounded local JSON index; never list directories or access a network."""
    root = _root(directory)
    path = root / "catalog.json"
    if path.is_symlink():
        _fail("unsafe_path", "Catalogue index cannot be a symlink")
    if not path.exists():
        return {"schema": CATALOG_SCHEMA, "packs": []}
    if not path.is_file():
        _fail("unsafe_path", "Catalogue index must be a regular file")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_CATALOG_BYTES + 1)
        if len(raw) > MAX_CATALOG_BYTES:
            _fail("size_limit", "Catalogue exceeds 1 MiB")
        document = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_no_duplicates,
            parse_constant=lambda _: _fail("invalid_catalog", "Invalid JSON constant"),
        )
        return _catalog_document(document)
    except HubError:
        raise
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise HubError("invalid_catalog", "Unreadable local catalogue") from exc


@contextmanager
def _writer(directory):
    root = _root(directory)
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        _fail("unsafe_path", "Catalogue root cannot be a symlink")
    lock = root / ".r69-writer-lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise HubError("catalogue_busy", "Another writer or stale lock exists") from exc
    try:
        yield root
    finally:
        lock.rmdir()


def _store_index(root, document):
    checked = _catalog_document(document)
    encoded = (json.dumps(checked, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    if len(encoded) > MAX_CATALOG_BYTES:
        _fail("size_limit", "Catalogue exceeds 1 MiB")
    if (root / "catalog.json").is_symlink():
        _fail("unsafe_path", "Catalogue index cannot be a symlink")
    filename = None
    try:
        with NamedTemporaryFile("wb", dir=root, prefix=".r69-index-", delete=False) as tmp:
            filename = Path(tmp.name)
            tmp.write(encoded)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(filename, root / "catalog.json")
    finally:
        if filename is not None:
            filename.unlink(missing_ok=True)


def _verified_archive(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        _fail("unsafe_path", "Require a regular non-symlink ZIP")
    try:
        inspection = inspect_pack(path)
        data = path.read_bytes()
        if len(data) > MAX_ARCHIVE_BYTES or sha256(data).hexdigest() != inspection.archive_sha256:
            _fail("archive_changed", "Pack changed after verification")
        with zipfile.ZipFile(BytesIO(data)) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        validate_manifest(manifest)
        if (manifest["id"], manifest["version"], manifest["kind"]) != (
                inspection.pack_id, inspection.version, inspection.kind):
            _fail("archive_changed", "Pack metadata changed")
        return inspection, manifest, data
    except HubError:
        raise
    except (PackError, OSError, ValueError, zipfile.BadZipFile,
            RuntimeError, UnicodeError) as exc:
        raise HubError("invalid_pack", "Inert R30 pack verification failed") from exc


def _blob_path(root, digest):
    if type(digest) is not str or not _SHA.fullmatch(digest):
        _fail("invalid_catalog", "Invalid pack digest")
    pack_dir = root / "packs"
    if pack_dir.is_symlink():
        _fail("unsafe_path", "Pack directory cannot be a symlink")
    path = pack_dir / (digest + ".zip")
    if path.is_symlink():
        _fail("unsafe_path", "Stored archive cannot be a symlink")
    return path


def _release(document, pack_id, version):
    if type(pack_id) is not str or not _ID.fullmatch(pack_id):
        _fail("invalid_id", "Invalid pack id")
    _version(version)
    match = next((row for row in document["packs"]
                  if row["id"] == pack_id and row["version"] == version), None)
    if match is None:
        _fail("unknown_release", "No such pack release")
    return match


def publish_pack(directory, archive, *, publisher, declaration, confirm=False):
    """Publish a reviewed local ZIP without altering or signing its content."""
    if confirm is not True:
        _fail("consent_required", "Publication requires explicit opt-in")
    if type(publisher) is not str or not _PUBLISHER.fullmatch(publisher):
        _fail("invalid_publisher", "Publisher must be a stable local label")
    if (type(declaration) is not str or not 10 <= len(declaration) <= 500 or
            any(ord(ch) < 32 for ch in declaration)):
        _fail("invalid_declaration", "Provide a non-empty redistribution attestation")
    report, manifest, data = _verified_archive(archive)
    entry = {
        "id": report.pack_id, "version": report.version, "kind": report.kind,
        "sha256": report.archive_sha256, "size": len(data),
        "publisher": publisher,
        "licenses": sorted({r["license"] for r in manifest["files"]}),
        "origins": sorted({r["origin"] for r in manifest["files"]}),
        "declaration": declaration, "legal_clearance": False,
        "status": "available", "withdrawal_reason": "",
    }
    _validate_entry(entry)
    with _writer(directory) as root:
        document = read_catalog(root)
        matching = [r for r in document["packs"] if r["id"] == report.pack_id]
        if any(r["version"] == report.version for r in matching):
            _fail("immutable_release", "A published version cannot be replaced or resurrected")
        if matching and _version(report.version) <= max(_version(r["version"]) for r in matching):
            _fail("non_monotonic_version", "New release must increase SemVer")
        path = _blob_path(root, report.archive_sha256)
        path.parent.mkdir(exist_ok=True)
        if path.exists():
            if not path.is_file() or sha256(path.read_bytes()).hexdigest() != report.archive_sha256:
                _fail("stored_pack_changed", "Stored archive digest does not match")
        else:
            try:
                with path.open("xb") as sink:
                    sink.write(data)
                    sink.flush()
                    os.fsync(sink.fileno())
            except Exception:
                path.unlink(missing_ok=True)
                raise
        document["packs"].append(entry)
        _store_index(root, document)
    return dict(entry)


def withdraw_pack(directory, pack_id, version, *, reason, confirm=False):
    """Revoke discovery and new acquisitions, retaining the immutable tombstone."""
    if confirm is not True:
        _fail("consent_required", "Withdrawal requires explicit confirmation")
    if (type(reason) is not str or not 1 <= len(reason) <= 300 or
            any(ord(ch) < 32 for ch in reason)):
        _fail("invalid_reason", "Give a bounded withdrawal reason")
    with _writer(directory) as root:
        document = read_catalog(root)
        item = _release(document, pack_id, version)
        if item["status"] == "withdrawn":
            _fail("already_withdrawn", "Withdrawal tombstone is permanent")
        item["status"] = "withdrawn"
        item["withdrawal_reason"] = reason
        _store_index(root, document)
        return dict(item)


def search_catalog(directory, text="", *, include_withdrawn=False):
    """Explicit read-only local search; no discovery, telemetry or network."""
    if type(text) is not str or len(text) > 120:
        _fail("invalid_query", "Query must be at most 120 characters")
    needle = text.casefold()
    return tuple(dict(row) for row in read_catalog(directory)["packs"]
                 if (include_withdrawn or row["status"] == "available") and
                 (needle in row["id"].casefold() or needle in row["kind"].casefold()
                  or needle in row["publisher"].casefold()))


def available_updates(directory, installed):
    """Discover only greater available versions; never perform an update."""
    if type(installed) is not dict or len(installed) > 2048:
        _fail("invalid_installed", "Expected map of id to pinned SemVer")
    for pack_id, version in installed.items():
        if type(pack_id) is not str or not _ID.fullmatch(pack_id):
            _fail("invalid_installed", "Invalid installed pack id")
        _version(version)
    found = {}
    for row in search_catalog(directory):
        if row["id"] not in installed or _version(row["version"]) <= _version(installed[row["id"]]):
            continue
        previous = found.get(row["id"])
        if previous is None or _version(row["version"]) > _version(previous["version"]):
            found[row["id"]] = row
    return tuple(found[key] for key in sorted(found))


def acquire_pack(directory, pack_id, version, destination, *,
                 confirm=False, expected_sha256=None):
    """Copy a locally selected pack to a NEW path, rechecking all integrity.

    Never extracts a ZIP, modifies a game project, or silently updates a pack.
    Call R30.B preview_pack_import/import_pack_to_copy independently with
    explicitly selected asset bindings and user approval.
    """
    if confirm is not True:
        _fail("consent_required", "Import requires explicit opt-in")
    document = read_catalog(directory)
    item = _release(document, pack_id, version)
    if item["status"] != "available":
        _fail("withdrawn", "Withdrawn release cannot be acquired")
    if expected_sha256 is not None and expected_sha256 != item["sha256"]:
        _fail("untrusted_digest", "Pinned digest differs from local catalogue")
    path = _blob_path(_root(directory), item["sha256"])
    report, manifest, data = _verified_archive(path)
    if (report.pack_id, report.version, report.kind, report.archive_sha256, len(data)) != (
            item["id"], item["version"], item["kind"], item["sha256"], item["size"]):
        _fail("stored_pack_changed", "Archive no longer matches catalogue")
    if (sorted({r["license"] for r in manifest["files"]}) != item["licenses"] or
            sorted({r["origin"] for r in manifest["files"]}) != item["origins"]):
        _fail("metadata_mismatch", "Asset licence or provenance changed")
    output = Path(destination)
    if output.suffix.lower() != ".zip" or output.is_symlink() or not output.parent.is_dir():
        _fail("unsafe_destination", "Select a new .zip path in an existing directory")
    if output.exists():
        _fail("destination_exists", "Never overwrite an existing local pack")
    created = False
    try:
        with output.open("xb") as sink:
            created = True
            sink.write(data)
            sink.flush()
            os.fsync(sink.fileno())
        if sha256(output.read_bytes()).hexdigest() != item["sha256"]:
            _fail("copy_changed", "Destination archive failed verification")
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
    return {"path": str(output), "id": pack_id, "version": version,
            "sha256": item["sha256"], "rights_verified": False,
            "executable": False, "project_modified": False}

"""R59.A: fail-closed release descriptors and reversible save snapshots.

A release descriptor is not an authenticated signature, a migration adapter, an
installer, or permission to publish. All destructive activation is out of scope.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from tempfile import TemporaryDirectory

from .publishing import publication_plan
from .r15 import ExportError

_SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RELEASE_FIELDS = {
    "schema", "kind", "version", "revision", "target", "family",
    "manifest_sha256", "dependencies_sha256", "save_schema",
    "readable_save_schemas", "decision", "release_certified",
}
_MAX_FILES = 20000
_MAX_FILE_SIZE = 64 * 1024 * 1024
_MAX_MANIFEST = 4 * 1024 * 1024


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _json_unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ExportError("Duplicate snapshot JSON key: " + key)
        result[key] = value
    return result


def _version(version):
    if type(version) is not str or not _SEMVER.fullmatch(version):
        raise ExportError("A strict major.minor.patch release version is required")
    return tuple(map(int, version.split(".")))


def _schema(value):
    if type(value) is not int or not 1 <= value <= 255:
        raise ExportError("Save schema must be an integer from 1 to 255")


def release_descriptor(bundle, provenance, *, version, revision, target, family, save_schema):
    """Bind an R39 validated bundle and dependency inventory to a declared version.

    A descriptor does not assert the Player can load any historical save. Only
    its current schema is declared readable until an adapter is actually tested.
    """
    _version(version)
    _schema(save_schema)
    plan = publication_plan(bundle, provenance, revision=revision, target=target, family=family)
    return {
        "schema": 1, "kind": "drawtemp-r59-release-descriptor",
        "version": version, "revision": revision, "target": target,
        "family": family, "manifest_sha256": plan["manifest_sha256"],
        "dependencies_sha256": sha256(_canonical(plan["dependencies"])).hexdigest(),
        "save_schema": save_schema, "readable_save_schemas": [save_schema],
        "decision": "NO-GO", "release_certified": False,
    }


def validate_release_descriptor(record):
    """Reject unknown shapes, stale/mismatched declarations and approval claims."""
    if type(record) is not dict or set(record) != _RELEASE_FIELDS:
        raise ExportError("Unknown R59 release descriptor fields")
    if (type(record["schema"]) is not int or record["schema"] != 1
            or record["kind"] != "drawtemp-r59-release-descriptor"
            or record["decision"] != "NO-GO" or record["release_certified"] is not False):
        raise ExportError("Untrusted R59 descriptor or release approval claim")
    _version(record["version"])
    _schema(record["save_schema"])
    if record["readable_save_schemas"] != [record["save_schema"]]:
        raise ExportError("Historical save readers require separately certified migration")
    if (not isinstance(record["revision"], str) or
            not re.fullmatch(r"[0-9a-f]{40}", record["revision"])):
        raise ExportError("Invalid release revision")
    from .publishing import PC_TARGETS, GAME_FAMILIES
    if record["target"] not in PC_TARGETS or record["family"] not in GAME_FAMILIES:
        raise ExportError("Invalid release target or family")
    for field in ("manifest_sha256", "dependencies_sha256"):
        if type(record[field]) is not str or not _SHA.fullmatch(record[field]):
            raise ExportError("Invalid descriptor digest: " + field)
    return dict(record)


def plan_update(installed, candidate, *, observed_save_schemas=()):
    """Pure assessment. A same-schema update is not thereby authorized to install.

    Schema N-1 requires a real tested adapter and compatibility fixtures; no
    caller-supplied boolean may bypass that requirement in this first lot.
    """
    old = validate_release_descriptor(installed)
    new = validate_release_descriptor(candidate)
    problems = []
    if _version(new["version"]) <= _version(old["version"]):
        problems.append("Candidate version must be greater than installed version")
    if (new["target"], new["family"]) != (old["target"], old["family"]):
        problems.append("Target/family mismatch")
    if new["manifest_sha256"] == old["manifest_sha256"]:
        problems.append("Candidate bundle is byte-identical to installed bundle")
    if (type(observed_save_schemas) not in (tuple, list) or
            len(observed_save_schemas) > 256):
        raise ExportError("Invalid save-schema inventory")
    for schema in observed_save_schemas:
        _schema(schema)
        if schema not in new["readable_save_schemas"]:
            problems.append("Save schema " + str(schema) +
                            " requires an independently tested migration adapter")
    return {
        "schema": 1, "kind": "drawtemp-r59-update-plan",
        "from_version": old["version"], "to_version": new["version"],
        "compatibility": "blocked" if problems else "candidate",
        "blockers": problems + [
            "R59.A is only a read-only plan: signatures, migrations, install/rollback "
            "transaction and clean-machine acceptance remain unverified"
        ],
        "decision": "NO-GO", "release_certified": False,
    }


def _relative(name):
    parts = name.split("/") if isinstance(name, str) else []
    reserved = {"con", "prn", "aux", "nul"} | {
        prefix + str(n) for prefix in ("com", "lpt") for n in range(1, 10)
    }
    if (type(name) is not str or not name or "\\" in name or ":" in name
            or name.startswith("/") or any(
                not part or part in (".", "..") or part[-1] in (".", " ")
                or part.split(".")[0].casefold() in reserved
                or any(ord(ch) < 32 for ch in part) for part in parts)):
        raise ExportError("Unsafe snapshot relative path")
    return name


def _walk_regular(root):
    """Enumerate *all* files; silently skipping a hidden save is forbidden."""
    entries = []
    casefolded = set()
    def fail_walk(error):
        raise ExportError("Cannot enumerate complete save tree: " + str(error))
    for directory, subdirs, filenames in os.walk(
            root, topdown=True, followlinks=False, onerror=fail_walk):
        for name in subdirs + filenames:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ExportError("Linked or special file in save tree")
        for name in filenames:
            path = Path(directory) / name
            rel = _relative(path.relative_to(root).as_posix())
            if rel.casefold() in casefolded:
                raise ExportError("Case-insensitive save path collision")
            casefolded.add(rel.casefold())
            if path.stat().st_size > _MAX_FILE_SIZE:
                raise ExportError("Oversized save file")
            entries.append((rel, path))
            if len(entries) > _MAX_FILES:
                raise ExportError("Too many save files")
    return sorted(entries)


def _copy_checked(src, dst):
    """Copy regular bytes only, refuse symlinks and concurrent source changes."""
    before = src.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > _MAX_FILE_SIZE:
        raise ExportError("Unsafe save source")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(src, flags), "rb") as stream:
        fdstat = os.fstat(stream.fileno())
        if not stat.S_ISREG(fdstat.st_mode) or (fdstat.st_dev, fdstat.st_ino) != (before.st_dev, before.st_ino):
            raise ExportError("Save source changed during inspection")
        dst.parent.mkdir(parents=True, exist_ok=True)
        h = sha256()
        size = 0
        with dst.open("wb") as output:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > _MAX_FILE_SIZE:
                    raise ExportError("Save exceeded size bound during copy")
                h.update(chunk)
                output.write(chunk)
        after = os.fstat(stream.fileno())
    final = src.lstat()
    if (after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns
            or (final.st_dev, final.st_ino) != (before.st_dev, before.st_ino)
            or final.st_size != before.st_size or final.st_mtime_ns != before.st_mtime_ns
            or size != before.st_size):
        raise ExportError("Save changed during snapshot")
    return {"size": size, "sha256": h.hexdigest()}


def _target(output, source):
    source = Path(source)
    output = Path(output)
    if source.is_symlink() or not source.is_dir():
        raise ExportError("Real source directory required")
    if output.exists() or output.is_symlink():
        raise ExportError("Snapshot/restore destination already exists")
    src = source.resolve(strict=True)
    dst = output.absolute()
    if dst == src or src in dst.parents or dst in src.parents:
        raise ExportError("Save source and destination must not overlap")
    dst.parent.mkdir(parents=True, exist_ok=True)
    return src, dst


def snapshot_saves(source, destination):
    """Create an immutable-by-contract recovery generation without touching saves."""
    root, output = _target(destination, source)
    source_files = _walk_regular(root)
    with TemporaryDirectory(prefix=".r59-snapshot-", dir=output.parent) as temporary:
        stage = Path(temporary) / "snapshot"
        (stage / "files").mkdir(parents=True)
        files = []
        for rel, path in source_files:
            meta = _copy_checked(path, stage / "files" / rel)
            files.append({"path": rel, **meta})
        if [r for r, _ in _walk_regular(root)] != [r for r, _ in source_files]:
            raise ExportError("Save tree changed during snapshot")
        record = {"schema": 1, "kind": "drawtemp-r59-save-snapshot",
                  "files": files}
        (stage / "snapshot.json").write_bytes(_canonical(record) + b"\n")
        verify_save_snapshot(stage)
        if output.exists() or output.is_symlink():
            raise ExportError("Destination appeared during snapshot")
        os.rename(stage, output)
    return record


def verify_save_snapshot(snapshot):
    root = Path(snapshot)
    if root.is_symlink() or not root.is_dir():
        raise ExportError("Snapshot must be a real directory")
    manifest = root / "snapshot.json"
    if (manifest.is_symlink() or not manifest.is_file() or
            manifest.stat().st_size > _MAX_MANIFEST):
        raise ExportError("Snapshot manifest missing or oversized")
    record = json.loads(manifest.read_text(encoding="utf-8"), object_pairs_hook=_json_unique)
    if (type(record) is not dict or set(record) != {"schema", "kind", "files"}
            or type(record["schema"]) is not int or record["schema"] != 1
            or record["kind"] != "drawtemp-r59-save-snapshot"
            or type(record["files"]) is not list or len(record["files"]) > _MAX_FILES):
        raise ExportError("Invalid snapshot manifest")
    files_root = root / "files"
    if files_root.is_symlink() or not files_root.is_dir():
        raise ExportError("Snapshot files directory missing")
    actual = _walk_regular(files_root)
    expected = []
    seen = set()
    for item in record["files"]:
        if type(item) is not dict or set(item) != {"path", "size", "sha256"}:
            raise ExportError("Invalid snapshot file record")
        rel = _relative(item["path"])
        if (rel.casefold() in seen or type(item["size"]) is not int
                or not 0 <= item["size"] <= _MAX_FILE_SIZE
                or type(item["sha256"]) is not str or not _SHA.fullmatch(item["sha256"])):
            raise ExportError("Duplicate/invalid snapshot file")
        seen.add(rel.casefold())
        expected.append(rel)
    if sorted(expected) != [r for r, _ in actual]:
        raise ExportError("Snapshot files do not match manifest")
    for rel, path in actual:
        row = next(item for item in record["files"] if item["path"] == rel)
        if path.stat().st_size != row["size"] or sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ExportError("Snapshot checksum mismatch: " + rel)
    if {r for r, _ in _walk_regular(root)} != {"snapshot.json"} | {"files/" + r for r in expected}:
        raise ExportError("Snapshot contains untracked files")
    return record


def restore_saves(snapshot, destination):
    """Restore to a NEW directory only; existing player saves are never overwritten."""
    record = verify_save_snapshot(snapshot)
    root, output = _target(destination, snapshot)
    with TemporaryDirectory(prefix=".r59-restore-", dir=output.parent) as temporary:
        stage = Path(temporary) / "restored"
        stage.mkdir()
        for item in record["files"]:
            rel = item["path"]
            actual = _copy_checked(root / "files" / rel, stage / rel)
            if actual != {"size": item["size"], "sha256": item["sha256"]}:
                raise ExportError("Snapshot changed during restore")
        if output.exists() or output.is_symlink():
            raise ExportError("Restore destination appeared")
        os.rename(stage, output)
    return output

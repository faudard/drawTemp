"""R58.B3: fail-closed write-ahead markers for interrupted version staging.

Markers never authorize deleting package files. They prevent another Studio
package edit until a user inspects the pending state and explicitly acknowledges
it. Content/GameProject remains owned by AuthoringSession and its save store.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

from drawtemp.assets.packs import _hash, _id, _path, _version, ResourcePackError

JOURNAL_NAME = ".drawtemp-r58-package-upgrade.pending.json"
MAX_JOURNAL_BYTES = 64 * 1024


class PackageRecoveryError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _refuse(code, message):
    raise PackageRecoveryError(code, message)


def _root(path):
    root = Path(path)
    if root.is_symlink() or not root.is_dir():
        _refuse("unsafe_project", "Project root is missing or symbolic")
    return root.resolve(strict=True)


def _marker(root):
    return root / JOURNAL_NAME


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _refuse("invalid_journal", "Duplicate journal key: " + key)
        result[key] = value
    return result


def _validate(journal):
    fields = {"schema_version", "kind", "id", "from_version",
              "to_version", "from_sha256", "to_sha256",
              "revision", "project_digest", "files"}
    if type(journal) is not dict or set(journal) != fields:
        _refuse("invalid_journal", "Unknown or missing journal fields")
    if type(journal["schema_version"]) is not int or journal["schema_version"] != 1 or (
            journal["kind"] != "r58-package-version-stage"):
        _refuse("invalid_journal", "Unsupported package journal schema")
    try:
        _id(journal["id"])
        _version(journal["from_version"])
        _version(journal["to_version"])
        for key in ("from_sha256", "to_sha256", "project_digest"):
            _hash(journal[key])
    except ResourcePackError as exc:
        raise PackageRecoveryError("invalid_journal", str(exc)) from exc
    if type(journal["revision"]) is not int or journal["revision"] < 0:
        _refuse("invalid_journal", "Invalid editor revision")
    if type(journal["files"]) is not list or not 1 <= len(journal["files"]) <= 128:
        _refuse("invalid_journal", "Missing or excessive file list")
    seen = set()
    prefix = "assets/packs/" + journal["id"] + "/" + journal["to_version"] + "/"
    for row in journal["files"]:
        if type(row) is not dict or set(row) != {"path", "sha256", "bytes"}:
            _refuse("invalid_journal", "Unexpected file metadata")
        try:
            path = _path(row["path"])
            _hash(row["sha256"])
        except ResourcePackError as exc:
            raise PackageRecoveryError("invalid_journal", str(exc)) from exc
        if (not path.startswith(prefix) or path.casefold() in seen or
                type(row["bytes"]) is not int or not 1 <= row["bytes"] <= 16 * 1024 * 1024):
            _refuse("invalid_journal", "Unsafe/duplicate/out-of-bounds package file")
        seen.add(path.casefold())
    return journal


def read_pending_upgrade(project_root):
    """Read-only inspection; malformed/symlinked journals fail closed."""
    root = _root(project_root)
    marker = _marker(root)
    if not marker.exists() and not marker.is_symlink():
        return None
    if marker.is_symlink() or not marker.is_file():
        _refuse("invalid_journal", "Journal is not a regular file")
    if not 1 <= marker.stat().st_size <= MAX_JOURNAL_BYTES:
        _refuse("invalid_journal", "Unbounded/missing journal")
    raw = marker.read_bytes()
    if len(raw) > MAX_JOURNAL_BYTES:
        _refuse("invalid_journal", "Journal changed size during inspection")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeError, ValueError) as exc:
        raise PackageRecoveryError("invalid_journal", str(exc)) from exc
    _validate(data)
    observed = []
    for row in data["files"]:
        node = root
        linked = False
        for part in row["path"].split("/"):
            node = node / part
            if node.is_symlink():
                linked = True
                break
        if linked:
            condition = "unsafe-link"
        elif not node.exists():
            condition = "missing"
        elif not node.is_file() or not node.resolve(strict=True).is_relative_to(root):
            condition = "unsafe-type"
        elif node.stat().st_size != row["bytes"] or sha256(node.read_bytes()).hexdigest() != row["sha256"]:
            condition = "mismatch"
        else:
            condition = "verified"
        observed.append({"path": row["path"], "state": condition})
    return {
        "journal_sha256": sha256(raw).hexdigest(),
        "id": data["id"],
        "from_version": data["from_version"],
        "to_version": data["to_version"],
        "from_sha256": data["from_sha256"],
        "to_sha256": data["to_sha256"],
        "source_revision": data["revision"],
        "source_digest": data["project_digest"],
        "files": observed,
        "requires_explicit_acknowledgement": True,
        "files_deleted": False,
    }


def require_no_pending_upgrade(project_root):
    if _marker(_root(project_root)).exists() or _marker(_root(project_root)).is_symlink():
        _refuse("recovery_required",
                "Pending R58 package staging: inspect and explicitly acknowledge first")


def begin_upgrade_journal(project_root, preview, manifest):
    """Exclusively publish the intent BEFORE creating any version bytes."""
    root = _root(project_root)
    require_no_pending_upgrade(root)
    items = [{
        "path": "assets/packs/" + manifest["id"] + "/" +
                manifest["version"] + "/" + row["path"],
        "sha256": row["sha256"], "bytes": row["bytes"],
    } for row in manifest["files"]]
    document = {
        "schema_version": 1, "kind": "r58-package-version-stage",
        "id": preview.package_id, "from_version": preview.previous_version,
        "to_version": preview.version,
        "from_sha256": preview.previous_sha256, "to_sha256": preview.sha256,
        "revision": preview.source_revision,
        "project_digest": preview.source_digest,
        "files": items,
    }
    _validate(document)
    raw = (json.dumps(document, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > MAX_JOURNAL_BYTES:
        _refuse("invalid_journal", "Journal exceeds safety limit")
    marker = _marker(root)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(marker, flags, 0o600)
    except FileExistsError as exc:
        raise PackageRecoveryError("recovery_required", "A package journal already exists") from exc
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    _fsync_dir(root)
    return sha256(raw).hexdigest()


def _fsync_dir(root):
    if os.name != "posix" or not hasattr(os, "O_DIRECTORY"):
        return
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def clear_upgrade_journal(project_root, *, expected_sha256):
    """Remove the marker, never assets, iff no other process replaced it."""
    root = _root(project_root)
    marker = _marker(root)
    if marker.is_symlink() or not marker.is_file():
        _refuse("invalid_journal", "Journal missing or unsafe")
    raw = marker.read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        _refuse("stale_journal", "Journal changed since it was inspected")
    marker.unlink()
    _fsync_dir(root)


def acknowledge_pending_upgrade(project_root, editor, *, expected_sha256):
    """Explicit recovery acknowledgement; no implicit deletion or overwrite.

    The editor must still reference the original or target pack digest. If
    it refers to the target, its installed assets must pass R24 integrity.
    The caller must inspect the read-only report and request this deliberately.
    """
    from drawtemp.assets.packs import RECEIPT_NAMESPACE, verify_installed_packs
    from drawtemp.sdk.authoring import AuthoringSession

    status = read_pending_upgrade(project_root)
    if status is None:
        _refuse("no_journal", "No package upgrade to acknowledge")
    if not isinstance(editor, AuthoringSession):
        _refuse("invalid_editor", "A canonical editor is required")
    if expected_sha256 != status["journal_sha256"]:
        _refuse("stale_journal", "Recovery view is stale")
    project = editor.snapshot().to_dict()["project"]
    record = project.get("extensions", {}).get(RECEIPT_NAMESPACE)
    rows = [] if record is None else record["data"]["packs"]
    row = next((item for item in rows if item["id"] == status["id"]), None)
    if row is None:
        _refuse("state_conflict", "Package was removed since interrupted upgrade")
    if (row["version"], row["sha256"]) not in (
            (status["from_version"], status["from_sha256"]),
            (status["to_version"], status["to_sha256"])):
        _refuse("state_conflict", "Editor no longer references original or target bytes")
    issues = verify_installed_packs(project_root, project)
    if issues:
        _refuse("invalid_receipts", "Installed packages failed validation: " + issues[0])
    clear_upgrade_journal(project_root, expected_sha256=expected_sha256)
    return {"acknowledged": True, "files_deleted": False, "journal_sha256": expected_sha256}

"""R48.A2 local append-only, integrity-checked *advisory* authoring audit.

Not a source of truth and never replayed into Content/GameProject. Publishing
an audit event is an explicit post-apply operation: the filesystem cannot
atomically commit an editor transaction and append to an independent log.
A crash between them may leave an unlogged edit; certification must reconcile
audit entries against canonical snapshots rather than assuming completeness.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

from sporebound.session_lock import session_writer_lock

SCHEMA = 1
MAX_BYTES = 8 * 1024 * 1024
MAX_ENTRY = 4096
FIELDS = frozenset((
    "schema", "sequence", "previous", "actor", "operation", "resource",
    "before", "after", "digest",
))


class AuditError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _hash(data):
    return sha256(json.dumps(
        data, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuditError("invalid_entry", "Duplicate audit field")
        result[key] = value
    return result


def _check_record(entry, number, previous):
    if (not isinstance(entry, dict) or set(entry) != FIELDS or
            type(entry["schema"]) is not int or entry["schema"] != SCHEMA or
            type(entry["sequence"]) is not int or entry["sequence"] != number or
            entry["previous"] != previous or
            any(not isinstance(entry[field], str) or
                not (1 <= len(entry[field]) <= 128)
                for field in ("actor", "operation", "resource")) or
            any(not isinstance(entry[field], str) or
                len(entry[field]) != 64 or
                any(ch not in "0123456789abcdef" for ch in entry[field])
                for field in ("before", "after", "digest")) or
            entry["digest"] != _hash({
                key: value for key, value in entry.items() if key != "digest"
            })):
        raise AuditError("invalid_entry", "Audit record schema or digest mismatch")


def _read(path):
    if path.is_symlink():
        raise AuditError("unsafe_path", "Audit path must not be a symlink")
    if not path.exists():
        return b"", []
    if not path.is_file():
        raise AuditError("unsafe_path", "Audit path must be a regular file")
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise AuditError("oversized_log", "Audit log exceeds 8 MiB")
    data = path.read_bytes()
    if not data:
        return data, []
    if not data.endswith(b"\n"):
        raise AuditError("truncated_log", "Incomplete audit record; inspect manually")
    records, last = [], None
    for number, raw in enumerate(data.splitlines(), start=1):
        if not raw or len(raw) > MAX_ENTRY:
            raise AuditError("invalid_entry", "Oversized or empty audit record")
        try:
            entry = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
        except (UnicodeError, ValueError) as exc:
            raise AuditError("invalid_entry", str(exc)) from exc
        _check_record(entry, number, last)
        records.append(entry)
        last = entry["digest"]
    return data, records


class LocalAuditLog:
    """Append metadata with a hash chain, explicit optimistic HEAD and O_EXCL lock."""

    def __init__(self, path):
        self.path = Path(path).absolute()

    def inspect(self):
        _data, rows = _read(self.path)
        return {"count": len(rows), "head": rows[-1]["digest"] if rows else None}

    def entries(self):
        """Return detached records only, never mutable internal state."""
        _data, rows = _read(self.path)
        return tuple(dict(row) for row in rows)

    def append(self, *, expected_head, actor, operation, resource,
               before, after):
        if any(not isinstance(item, str) or not item.strip() or len(item) > 128
               for item in (actor, operation, resource)):
            raise AuditError("invalid_metadata", "Author, operation and resource are required")
        for digest in (before, after):
            if (not isinstance(digest, str) or len(digest) != 64 or
                    any(ch not in "0123456789abcdef" for ch in digest)):
                raise AuditError("invalid_digest", "Canonical SHA-256 required")
        if (expected_head is not None and
                (not isinstance(expected_head, str) or
                 len(expected_head) != 64 or
                 any(ch not in "0123456789abcdef" for ch in expected_head))):
            raise AuditError("invalid_head", "Invalid expected audit head")

        with session_writer_lock(self.path):
            current, rows = _read(self.path)
            last = rows[-1]["digest"] if rows else None
            if expected_head != last:
                raise AuditError("stale_head", "Audit log advanced since inspection")
            entry = {
                "schema": SCHEMA,
                "sequence": len(rows) + 1,
                "previous": last,
                "actor": actor.strip(), "operation": operation.strip(),
                "resource": resource.strip(), "before": before, "after": after,
            }
            entry["digest"] = _hash(entry)
            encoded = (json.dumps(entry, sort_keys=True, ensure_ascii=False,
                                  separators=(",", ":")) + "\n").encode("utf-8")
            if len(encoded) > MAX_ENTRY or len(current) + len(encoded) > MAX_BYTES:
                raise AuditError("oversized_log", "Audit size limit reached")
            if self.path.is_symlink():
                raise AuditError("unsafe_path", "Symlink audit targets are forbidden")
            flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(self.path, flags, 0o600)
            try:
                # Also catch external appenders bypassing our lock, pre-write.
                if os.fstat(fd).st_size != len(current):
                    raise AuditError("external_change", "Audit was modified during append")
                view = memoryview(encoded)
                while view:
                    count = os.write(fd, view)
                    if count <= 0:
                        raise OSError("No progress writing audit entry")
                    view = view[count:]
                os.fsync(fd)
            finally:
                os.close(fd)
            return dict(entry)

"""R48.A4 — bounded durable archive for the validated local revision DAG.

This optional sidecar saves ONLY history snapshots and declared ancestry, not
player saves or another Content/GameProject authority. The complete archive
is validated before publication; optimistic digest comparison, an exclusive
writer lock, same-directory temp + fsync + atomic replace guard the old copy.
No best-effort repair or recovery is performed. Interrupted staging files and
orphan locks must be inspected explicitly by the owner.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from drawtemp.sdk.collaboration import CollaborationError, make_revision
from drawtemp.sdk.project_history import MAX_NODES, RevisionGraph
from sporebound.session_lock import session_writer_lock

SCHEMA = 1
MAX_ARCHIVE = 64 * 1024 * 1024
_HEX = frozenset("0123456789abcdef")


class HistoryStoreError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(raw):
    return sha256(raw).hexdigest()


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise HistoryStoreError("duplicate_field", "Duplicate field in history archive")
        result[key] = value
    return result


def _parse(raw):
    if len(raw) > MAX_ARCHIVE:
        raise HistoryStoreError("size_limit", "History archive exceeds 64 MiB")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_object_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              HistoryStoreError("invalid_json", "Nonfinite JSON value")))
    except HistoryStoreError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise HistoryStoreError("invalid_json", str(exc)) from exc
    if not isinstance(data, dict) or set(data) != {"schema", "payload", "digest"}:
        raise HistoryStoreError("invalid_schema", "History archive envelope is invalid")
    if type(data["schema"]) is not int or data["schema"] != SCHEMA:
        raise HistoryStoreError("invalid_schema", "Unsupported history archive version")
    if (not isinstance(data["digest"], str) or len(data["digest"]) != 64 or
            any(c not in _HEX for c in data["digest"]) or
            data["digest"] != _digest(_canonical(data["payload"]))):
        raise HistoryStoreError("invalid_digest", "History archive checksum mismatch")
    payload = data["payload"]
    if (not isinstance(payload, dict) or set(payload) != {"nodes"} or
            not isinstance(payload["nodes"], list) or
            not 1 <= len(payload["nodes"]) <= MAX_NODES):
        raise HistoryStoreError("invalid_graph", "History must contain 1..2048 nodes")
    graph = RevisionGraph()
    for row in payload["nodes"]:
        if (not isinstance(row, dict) or set(row) != {"id", "label", "parents", "revision"} or
                not isinstance(row["id"], str) or
                not isinstance(row["label"], str) or
                not isinstance(row["parents"], list)):
            raise HistoryStoreError("invalid_graph", "Malformed history node")
        revision_row = row["revision"]
        if (not isinstance(revision_row, dict) or
                set(revision_row) != {
                    "schema", "author", "parents", "digest", "content", "project"
                } or
                type(revision_row["schema"]) is not int or
                revision_row["schema"] != SCHEMA or
                not isinstance(revision_row["parents"], list) or
                not isinstance(revision_row["digest"], str)):
            raise HistoryStoreError("invalid_graph", "Malformed frozen revision")
        try:
            revision = make_revision(
                revision_row["content"], revision_row["project"],
                author=revision_row["author"], parents=revision_row["parents"])
            if revision.digest != revision_row["digest"]:
                raise HistoryStoreError("invalid_revision", "Project snapshot digest mismatch")
            node = graph.add(revision, parents=row["parents"], label=row["label"])
        except HistoryStoreError:
            raise
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            raise HistoryStoreError("invalid_graph", str(exc)) from exc
        if node.node_id != row["id"]:
            raise HistoryStoreError("invalid_node", "Node identity/ancestry was altered")
    return graph


def _serialize(graph):
    if not isinstance(graph, RevisionGraph):
        raise TypeError("Expected RevisionGraph")
    nodes = []
    for node in graph.nodes():
        content, project = node.revision.documents()
        nodes.append({
            "id": node.node_id, "label": node.label,
            "parents": list(node.parents),
            "revision": {
                **node.revision.to_dict(),
                "content": content, "project": project,
            },
        })
    if not nodes:
        raise HistoryStoreError("invalid_graph", "No history nodes to save")
    payload = {"nodes": nodes}
    raw = _canonical({"schema": SCHEMA, "payload": payload,
                      "digest": _digest(_canonical(payload))})
    if len(raw) > MAX_ARCHIVE:
        raise HistoryStoreError("size_limit", "History archive exceeds 64 MiB")
    return raw


class LocalHistoryStore:
    """An explicit, CAS-protected, whole-file local snapshot (no autosave)."""

    def __init__(self, path):
        self.path = Path(path).absolute()
        if self.path.parent.resolve() != self.path.parent:
            raise HistoryStoreError("unsafe_path", "Symlinked history directory refused")
        if self.path.name in ("", ".", ".."):
            raise HistoryStoreError("unsafe_path", "Invalid archive path")

    def _read(self):
        if self.path.is_symlink():
            raise HistoryStoreError("unsafe_path", "History archive must not be a symlink")
        if not self.path.exists():
            return None
        if not self.path.is_file():
            raise HistoryStoreError("unsafe_path", "Expected a regular history archive")
        if self.path.stat().st_size > MAX_ARCHIVE:
            raise HistoryStoreError("size_limit", "History archive exceeds 64 MiB")
        with self.path.open("rb") as handle:
            raw = handle.read(MAX_ARCHIVE + 1)
        if len(raw) > MAX_ARCHIVE:
            raise HistoryStoreError("size_limit", "History archive exceeds 64 MiB")
        return raw

    def inspect(self):
        """Return fingerprint of an existing VALID archive; missing -> None."""
        raw = self._read()
        if raw is None:
            return None
        _parse(raw)
        return _digest(raw)

    def load(self):
        raw = self._read()
        if raw is None:
            raise HistoryStoreError("missing_archive", "History archive does not exist")
        graph = _parse(raw)
        return graph, _digest(raw)

    def save(self, graph: RevisionGraph, *, expected_digest=None):
        """Explicit compare-and-swap. None means create-only, never overwrite."""
        if expected_digest is not None and (
                not isinstance(expected_digest, str) or
                len(expected_digest) != 64 or
                any(c not in _HEX for c in expected_digest)):
            raise HistoryStoreError("invalid_expected", "Expected a canonical SHA256")
        candidate = _serialize(graph)
        with session_writer_lock(self.path):
            old = self._read()
            if (old is None and expected_digest is not None) or (
                    old is not None and
                    (expected_digest is None or _digest(old) != expected_digest)):
                raise HistoryStoreError("stale_archive",
                                        "History archive changed; reload explicitly")
            if old is not None:
                _parse(old)  # Never overwrite a corrupt journal.
            fd, staging = tempfile.mkstemp(
                prefix="." + self.path.name + ".stage-", dir=self.path.parent)
            try:
                with os.fdopen(fd, "wb") as out:
                    out.write(candidate)
                    out.flush()
                    os.fsync(out.fileno())
                # Check the file path after staging too. Our writer lock
                # protects this API, not an external bypassing process.
                current = self._read()
                if current != old:
                    raise HistoryStoreError("external_change",
                                            "History archive changed while staging")
                os.replace(staging, self.path)
                staging = None
                if os.name != "nt" and hasattr(os, "O_DIRECTORY"):
                    dfd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(dfd)
                    finally:
                        os.close(dfd)
            finally:
                if staging is not None and os.path.exists(staging):
                    os.unlink(staging)
        return _digest(candidate)

"""R48.B2 — optional append-only, project-scoped review notes.

Notes are metadata about a validated revision node and a typed resource anchor.
They NEVER mutate Content/GameProject or grant a merge decision. The log is an
explicit local sidecar: append+fsync and hash chaining, but no distributed
authenticity, sync, atomicity with Studio saves, or guaranteed crash recovery.
A torn final record fails closed rather than being silently truncated.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re

from drawtemp.sdk.collaboration import _checked
from drawtemp.sdk.project_history import RevisionNode, _node_identity
from sporebound.session_lock import session_writer_lock

SCHEMA = 1
MAX_LOG_BYTES = 4 * 1024 * 1024
MAX_RECORD = 4096
MAX_EVENTS = 2048
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_EVENTS = frozenset(("comment", "resolve", "reopen"))
_ANCHOR = re.compile(
    r"(?:/(?:project|content)|/content/missions/[A-Za-z0-9_-]{1,64}"
    r"|/project/story/scenes/[A-Za-z0-9_-]{1,64}"
    r"|/project/(?:campaigns|cinematics)/[A-Za-z0-9_-]{1,64})\Z"
)
_FIELDS = frozenset(("schema", "sequence", "previous", "kind", "node",
                     "document", "anchor", "author", "text", "thread", "digest"))


class ReviewNoteError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _digest(data):
    return sha256(json.dumps(
        data, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def _unique_pairs(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ReviewNoteError("duplicate_field", "Duplicate JSON field in review log")
        data[key] = value
    return data


def anchor_from_path(path: str) -> str:
    """Turn an R30 semantic diff path into a stable resource-ID anchor."""
    if not isinstance(path, str) or not path.startswith("/"):
        raise ReviewNoteError("invalid_anchor", "Expected a semantic diff path")
    parts = path.split("/")
    if parts[1:3] == ["content", "missions"] and len(parts) >= 4:
        if not _ID.fullmatch(parts[3]):
            raise ReviewNoteError("invalid_anchor", "Invalid mission ID")
        return "/content/missions/" + parts[3]
    if parts[1:4] == ["project", "story", "scenes"] and len(parts) >= 5:
        if not _ID.fullmatch(parts[4]):
            raise ReviewNoteError("invalid_anchor", "Invalid scene ID")
        return "/project/story/scenes/" + parts[4]
    if len(parts) >= 4 and parts[1] == "project" and parts[2] in (
            "campaigns", "cinematics"):
        if not _ID.fullmatch(parts[3]):
            raise ReviewNoteError("invalid_anchor", "Invalid resource ID")
        return "/project/" + parts[2] + "/" + parts[3]
    if len(parts) >= 3 and parts[1] in ("project", "content"):
        return "/" + parts[1]
    raise ReviewNoteError("invalid_anchor", "Unknown authoring document")


def validate_anchor(node: RevisionNode, anchor: str):
    """Fail closed on dangling typed anchors; no fuzzy ID/token matching."""
    if (not isinstance(node, RevisionNode) or
            not isinstance(node.node_id, str) or
            not _SHA.fullmatch(node.node_id)):
        raise ReviewNoteError("invalid_node", "A validated history node is required")
    try:
        _checked(node.revision)
        valid_id = _node_identity(node.revision, node.parents, node.label)
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise ReviewNoteError("invalid_node", "Revision node is invalid") from exc
    if node.node_id != valid_id:
        raise ReviewNoteError("invalid_node", "Revision node identity mismatch")
    if not isinstance(anchor, str):
        raise ReviewNoteError("invalid_anchor", "A canonical resource anchor is required")
    content, project = node.revision.documents()
    if anchor in ("/content", "/project"):
        return
    parts = anchor.split("/")
    rows = None
    identifier = None
    if len(parts) == 4 and parts[1:3] == ["content", "missions"]:
        rows, identifier = content.get("missions"), parts[3]
    elif len(parts) == 5 and parts[1:4] == ["project", "story", "scenes"]:
        rows, identifier = project.get("story", {}).get("scenes"), parts[4]
    elif len(parts) == 4 and parts[1:3] in (
            ["project", "campaigns"], ["project", "cinematics"]):
        rows, identifier = project.get(parts[2]), parts[3]
    if (not isinstance(rows, list) or not isinstance(identifier, str) or
            not _ID.fullmatch(identifier) or
            not any(row.get("id") == identifier for row in rows
                    if isinstance(row, dict))):
        raise ReviewNoteError("unknown_resource", "Resource is absent from the selected revision")


def _check_record(entry, number, prior):
    if (not isinstance(entry, dict) or set(entry) != _FIELDS or
            type(entry["schema"]) is not int or entry["schema"] != SCHEMA or
            type(entry["sequence"]) is not int or entry["sequence"] != number or
            entry["previous"] != prior or
            not isinstance(entry["kind"], str) or entry["kind"] not in _EVENTS or
            not all(isinstance(entry[field], str) and _SHA.fullmatch(entry[field])
                    for field in ("node", "document", "digest")) or
            not isinstance(entry["anchor"], str) or
            not _ANCHOR.fullmatch(entry["anchor"]) or
            not isinstance(entry["author"], str) or
            not 1 <= len(entry["author"].strip()) <= 80 or
            not isinstance(entry["text"], str) or
            len(entry["text"]) > 2000 or
            (entry["kind"] == "comment" and not entry["text"].strip()) or
            (entry["kind"] != "comment" and entry["text"] != "") or
            (type(entry["thread"]) is not int or
             entry["thread"] < 0 or entry["thread"] >= number) or
            entry["digest"] != _digest({
                key: value for key, value in entry.items() if key != "digest"
            })):
        raise ReviewNoteError("invalid_event", "Review note violates schema or hash chain")
    if entry["kind"] == "comment":
        if entry["thread"] != 0:
            first = entry["thread"]
            if first < 1:
                raise ReviewNoteError("invalid_thread", "Invalid reply target")
    elif entry["thread"] == 0:
        raise ReviewNoteError("invalid_thread", "State change requires a thread")


def _read(path):
    if path.is_symlink():
        raise ReviewNoteError("unsafe_path", "Review note path is a symlink")
    if not path.exists():
        return b"", []
    if not path.is_file():
        raise ReviewNoteError("unsafe_path", "Review notes require a regular file")
    if path.stat().st_size > MAX_LOG_BYTES:
        raise ReviewNoteError("size_limit", "Review note journal is too large")
    data = path.read_bytes()
    if len(data) > MAX_LOG_BYTES:
        raise ReviewNoteError("size_limit", "Review note journal is too large")
    if data and not data.endswith(b"\n"):
        raise ReviewNoteError("torn_record", "Review journal has an incomplete final record")
    rows, prior = [], None
    for raw in data.splitlines():
        if not raw or len(raw) > MAX_RECORD or len(rows) >= MAX_EVENTS:
            raise ReviewNoteError("size_limit", "Review log has too many or oversized records")
        try:
            entry = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
        except ReviewNoteError:
            raise
        except (UnicodeError, ValueError) as exc:
            raise ReviewNoteError("invalid_event", str(exc)) from exc
        _check_record(entry, len(rows) + 1, prior)
        if entry["thread"]:
            target = rows[entry["thread"] - 1]
            if (target["kind"] != "comment" or target["thread"] != 0 or
                    target["node"] != entry["node"] or
                    target["document"] != entry["document"] or
                    target["anchor"] != entry["anchor"]):
                raise ReviewNoteError("invalid_thread", "Reply/state targets a different resource")
        rows.append(entry)
        prior = entry["digest"]
    return data, rows


class ReviewNoteStore:
    """Writer uses optimistic HEAD + existing Studio lock and a single append."""

    def __init__(self, path):
        self.path = Path(path).absolute()

    def inspect(self):
        _raw, rows = _read(self.path)
        return {"head": rows[-1]["digest"] if rows else None, "count": len(rows)}

    def events(self, *, node_id=None, anchor=None):
        _raw, rows = _read(self.path)
        return tuple(dict(row) for row in rows
                     if (node_id is None or row["node"] == node_id)
                     and (anchor is None or row["anchor"] == anchor))

    def threads(self, *, node_id=None, anchor=None):
        """Materialized heads/replies/status; detached and read-only."""
        _raw, rows = _read(self.path)
        threads = {}
        for row in rows:
            if row["kind"] == "comment" and row["thread"] == 0:
                threads[row["sequence"]] = {
                    "id": row["sequence"], "node": row["node"],
                    "document": row["document"], "anchor": row["anchor"],
                    "resolved": False, "comments": [dict(row)],
                }
            else:
                thread = threads[row["thread"]]
                if row["kind"] == "comment":
                    thread["comments"].append(dict(row))
                else:
                    thread["resolved"] = row["kind"] == "resolve"
        return tuple(value for value in threads.values()
                     if (node_id is None or value["node"] == node_id)
                     and (anchor is None or value["anchor"] == anchor))

    def append(self, node: RevisionNode, *, expected_head, anchor: str,
               author: str, text: str = "", kind="comment", thread=0):
        validate_anchor(node, anchor)
        if (kind not in _EVENTS or
                not isinstance(author, str) or
                not 1 <= len(author.strip()) <= 80 or
                not isinstance(text, str) or len(text) > 2000 or
                (kind == "comment" and not text.strip()) or
                (kind != "comment" and text != "") or
                type(thread) is not int or thread < 0 or
                (kind != "comment" and not thread) or
                (expected_head is not None and
                 (not isinstance(expected_head, str) or
                  not _SHA.fullmatch(expected_head)))):
            raise ReviewNoteError("invalid_input", "Invalid note text, author, thread or HEAD")
        with session_writer_lock(self.path):
            original, rows = _read(self.path)
            prior = rows[-1]["digest"] if rows else None
            if expected_head != prior:
                raise ReviewNoteError("stale_head", "Review journal was modified externally")
            if thread:
                if thread > len(rows):
                    raise ReviewNoteError("unknown_thread", "Thread does not exist")
                head = rows[thread - 1]
                if (head["kind"] != "comment" or head["thread"] != 0 or
                        head["node"] != node.node_id or
                        head["document"] != node.revision.digest or
                        head["anchor"] != anchor):
                    raise ReviewNoteError("invalid_thread", "Thread belongs to another resource")
            if len(rows) >= MAX_EVENTS:
                raise ReviewNoteError("size_limit", "Review note limit reached")
            record = {
                "schema": SCHEMA, "sequence": len(rows) + 1,
                "previous": prior, "kind": kind, "node": node.node_id,
                "document": node.revision.digest,
                "anchor": anchor, "author": author.strip(),
                "text": text, "thread": thread,
            }
            record["digest"] = _digest(record)
            encoded = (json.dumps(record, sort_keys=True, ensure_ascii=False,
                                  separators=(",", ":")) + "\n").encode("utf-8")
            if len(encoded) > MAX_RECORD or len(original) + len(encoded) > MAX_LOG_BYTES:
                raise ReviewNoteError("size_limit", "Review note exceeds storage limit")
            if self.path.is_symlink():
                raise ReviewNoteError("unsafe_path", "Review note path changed")
            flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(self.path, flags, 0o600)
            try:
                if os.fstat(fd).st_size != len(original):
                    raise ReviewNoteError("external_change", "Review journal changed")
                os.lseek(fd, 0, os.SEEK_SET)
                actual = bytearray()
                while len(actual) < len(original):
                    portion = os.read(fd, min(65536, len(original) - len(actual)))
                    if not portion:
                        break
                    actual.extend(portion)
                if actual != original:
                    raise ReviewNoteError("external_change", "Review journal changed")
                # Single write reduces but does not eliminate crash/torn-write
                # risk. A partial final line is rejected on next open.
                if os.write(fd, encoded) != len(encoded):
                    raise ReviewNoteError("torn_record", "Partial review note append")
                os.fsync(fd)
            finally:
                os.close(fd)
            return dict(record)

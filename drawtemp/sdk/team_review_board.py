"""R78.B — permissioned local review boards on top of R48 history and notes.

Optional advisory metadata only: Content/GameProject, decisions and Undo still
belong to R1/R30/R48. Neither approval nor task completion authorizes a merge,
save, export or release. The caller authenticates actor IDs.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from drawtemp.sdk.project_history import RevisionGraph
from drawtemp.sdk.review_notes import ReviewNoteStore, anchor_from_path, validate_anchor
from drawtemp.sdk.semantic_review import semantic_diff
from drawtemp.sdk.team_workflows import TeamAccessPolicy, TeamWorkflowError
from sporebound.session_lock import session_writer_lock


SCHEMA = 1
MAX_BYTES = 4 * 1024 * 1024
MAX_EVENTS = 2048
MAX_RECORD = 4096
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RELEASE = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9._-]{0,63})?\Z")
_STATES = frozenset(("todo", "in_progress", "done"))
_VOTES = frozenset(("approved", "changes_requested"))
_KINDS = frozenset(("create", "update", "review"))
_FIELDS = frozenset((
    "schema", "sequence", "previous", "kind", "node", "document",
    "anchor", "actor", "task", "title", "assignee", "status",
    "release", "digest",
))


class TeamBoardError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def _hash(value):
    return sha256(_canonical(value)).hexdigest()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TeamBoardError("duplicate_field", "Duplicate team board field")
        result[key] = value
    return result


def _check_row(row, sequence, previous, tasks):
    if (not isinstance(row, dict) or set(row) != _FIELDS or
            type(row["schema"]) is not int or row["schema"] != SCHEMA or
            type(row["sequence"]) is not int or row["sequence"] != sequence or
            row["previous"] != previous or row["kind"] not in _KINDS or
            any(not isinstance(row[key], str) or not _SHA.fullmatch(row[key])
                for key in ("node", "document", "digest")) or
            not isinstance(row["anchor"], str) or
            len(row["anchor"]) > 180 or not row["anchor"].startswith("/") or
            not isinstance(row["actor"], str) or
            not 1 <= len(row["actor"]) <= 80 or
            row["actor"] != row["actor"].strip() or
            any(ord(ch) < 32 for ch in row["actor"]) or
            type(row["task"]) is not int or row["task"] < 0 or
            not isinstance(row["title"], str) or
            not 1 <= len(row["title"].strip()) <= 180 or
            len(row["title"]) > 180 or
            not isinstance(row["assignee"], str) or
            len(row["assignee"]) > 80 or
            not isinstance(row["release"], str) or
            not _RELEASE.fullmatch(row["release"]) or
            not isinstance(row["status"], str) or
            row["digest"] != _hash({k: v for k, v in row.items() if k != "digest"})):
        raise TeamBoardError("invalid_event", "Malformed team board event or broken hash chain")
    kind = row["kind"]
    if kind == "create":
        if row["task"] != sequence or row["status"] != "todo":
            raise TeamBoardError("invalid_task", "Task creation must start in todo")
        tasks[sequence] = dict(row)
    elif kind == "update":
        original = tasks.get(row["task"])
        if original is None:
            raise TeamBoardError("unknown_task", "Update references unknown task")
        if (row["node"], row["document"], row["anchor"]) != (
                original["node"], original["document"], original["anchor"]):
            raise TeamBoardError("retargeted_task", "Task resource cannot be changed")
        if row["status"] not in _STATES:
            raise TeamBoardError("invalid_status", "Unsupported task status")
        tasks[row["task"]] = dict(row)
    else:
        if (row["task"] != 0 or row["assignee"] != "" or
                row["release"] != "" or row["status"] not in _VOTES):
            raise TeamBoardError("invalid_review", "Review decisions are advisory and task-free")


def _read(path):
    if path.parent.resolve() != path.parent or path.is_symlink():
        raise TeamBoardError("unsafe_path", "Symlinked team board file or directory refused")
    if not path.exists():
        return b"", [], {}
    if not path.is_file():
        raise TeamBoardError("unsafe_path", "Team board is not a regular file")
    if path.stat().st_size > MAX_BYTES:
        raise TeamBoardError("size_limit", "Team board exceeds size limit")
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise TeamBoardError("size_limit", "Team board exceeds size limit")
    if data and not data.endswith(b"\n"):
        raise TeamBoardError("torn_record", "Incomplete team board event")
    rows, tasks, previous = [], {}, None
    for raw in data.splitlines():
        if not raw or len(raw) > MAX_RECORD or len(rows) >= MAX_EVENTS:
            raise TeamBoardError("size_limit", "Team board journal exhausted")
        try:
            row = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(
                                 TeamBoardError("invalid_event", "Nonfinite JSON")))
        except TeamBoardError:
            raise
        except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
            raise TeamBoardError("invalid_event", str(exc)) from exc
        _check_row(row, len(rows) + 1, previous, tasks)
        rows.append(row)
        previous = row["digest"]
    return data, rows, tasks


class TeamTaskStore:
    """Append-only, hash-chained CAS journal; never an authority for game state."""

    def __init__(self, path):
        self.path = Path(path).absolute()

    def inspect(self):
        _data, rows, _tasks = _read(self.path)
        return {"count": len(rows), "head": rows[-1]["digest"] if rows else None}

    def events(self):
        _data, rows, _tasks = _read(self.path)
        return tuple(dict(row) for row in rows)

    def tasks(self):
        _data, _rows, tasks = _read(self.path)
        return tuple(dict(tasks[key]) for key in sorted(tasks))

    def append(self, *, expected_head, kind, node, anchor, actor, title,
               assignee="", status="todo", release="", task=0):
        # Binding each event to a validated R48 history node avoids ambiguous
        # asset paths, but this detached journal does not authenticate authors.
        validate_anchor(node, anchor)
        if (kind not in _KINDS or not isinstance(actor, str) or
                not 1 <= len(actor) <= 80 or actor != actor.strip() or
                any(ord(ch) < 32 for ch in actor) or
                not isinstance(title, str) or not 1 <= len(title.strip()) <= 180 or
                len(title) > 180 or not isinstance(assignee, str) or
                len(assignee) > 80 or not isinstance(release, str) or
                not _RELEASE.fullmatch(release) or
                type(task) is not int or task < 0 or
                (kind == "create" and (task != 0 or status != "todo")) or
                (kind == "update" and (task < 1 or status not in _STATES)) or
                (kind == "review" and (task != 0 or status not in _VOTES or
                                       assignee != "" or release != "")) or
                (expected_head is not None and
                 (not isinstance(expected_head, str) or not _SHA.fullmatch(expected_head)))):
            raise TeamBoardError("invalid_input", "Invalid review/task metadata")
        with session_writer_lock(self.path):
            old, rows, tasks = _read(self.path)
            previous = rows[-1]["digest"] if rows else None
            if previous != expected_head:
                raise TeamBoardError("stale_head", "Board changed; reload before writing")
            if len(rows) >= MAX_EVENTS:
                raise TeamBoardError("size_limit", "Team board journal exhausted")
            sequence = len(rows) + 1
            record = {
                "schema": SCHEMA, "sequence": sequence, "previous": previous,
                "kind": kind, "node": node.node_id,
                "document": node.revision.digest, "anchor": anchor,
                "actor": actor, "task": sequence if kind == "create" else task,
                "title": title, "assignee": assignee, "status": status,
                "release": release,
            }
            record["digest"] = _hash(record)
            _check_row(record, sequence, previous, tasks)
            encoded = _canonical(record) + b"\n"
            if len(encoded) > MAX_RECORD or len(old) + len(encoded) > MAX_BYTES:
                raise TeamBoardError("size_limit", "Team board journal exhausted")
            if self.path.parent.resolve() != self.path.parent or self.path.is_symlink():
                raise TeamBoardError("unsafe_path", "Board destination changed")
            flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(self.path, flags, 0o600)
            try:
                if os.fstat(fd).st_size != len(old):
                    raise TeamBoardError("external_change", "Team board changed during append")
                os.lseek(fd, 0, os.SEEK_SET)
                existing = bytearray()
                while len(existing) < len(old):
                    chunk = os.read(fd, min(65536, len(old) - len(existing)))
                    if not chunk:
                        break
                    existing.extend(chunk)
                if existing != old:
                    raise TeamBoardError("external_change", "Team board bytes changed")
                if os.write(fd, encoded) != len(encoded):
                    raise TeamBoardError("torn_record", "Partial team board append")
                os.fsync(fd)
            finally:
                os.close(fd)
            return dict(record)


class TeamReviewBoard:
    """R78.B team-facing access to R48 anchored notes and separate task ledger."""

    def __init__(self, graph: RevisionGraph, policy: TeamAccessPolicy,
                 notes: ReviewNoteStore, tasks: TeamTaskStore):
        if (not isinstance(graph, RevisionGraph) or
                not isinstance(policy, TeamAccessPolicy) or
                not isinstance(notes, ReviewNoteStore) or
                not isinstance(tasks, TeamTaskStore)):
            raise TypeError("History, team policy, review notes and task store required")
        if notes.path == tasks.path:
            raise TeamBoardError("same_journal", "Notes and board must use different files")
        self.graph, self.policy, self.notes, self.tasks = graph, policy, notes, tasks

    def _role(self, actor, *, contribute=False, manage=False):
        role = self.policy.require(actor)
        if (contribute and role not in ("owner", "editor", "reviewer")) or (
                manage and role not in ("owner", "editor")):
            raise TeamWorkflowError("access_denied", "Insufficient team review rights")
        return role

    def _node(self, identity):
        return self.graph.node(identity)

    @staticmethod
    def _anchor(path):
        # The R48 helper expects a diff *field* path. The review UI can
        # also deliberately attach a note/task to a document root.
        if path in ("/content", "/project"):
            return path
        return anchor_from_path(path)

    def _verified_events(self):
        rows = self.tasks.events()
        for row in rows:
            node = self._node(row["node"])
            if node.revision.digest != row["document"]:
                raise TeamBoardError("unknown_document", "Task refers to a different document")
            validate_anchor(node, row["anchor"])
        return rows

    def differences(self, actor, local_id, incoming_id):
        self._role(actor)
        local, incoming = self._node(local_id), self._node(incoming_id)
        lc, lp = local.revision.documents()
        ic, ip = incoming.revision.documents()
        return semantic_diff(lc, lp, ic, ip, typed_sequences=True)

    def discussions(self, actor, node_id, anchor=None):
        self._role(actor)
        node = self._node(node_id)
        if anchor is not None:
            validate_anchor(node, anchor)
        return self.notes.threads(node_id=node.node_id, anchor=anchor)

    def note(self, actor, *, node_id, path, expected_head,
             text="", kind="comment", thread=0):
        self._role(actor, contribute=True)
        node = self._node(node_id)
        anchor = self._anchor(path)
        return self.notes.append(node, expected_head=expected_head, anchor=anchor,
                                 author=actor, text=text, kind=kind, thread=thread)

    def tasks_for(self, actor, *, release=None):
        self._role(actor)
        self._verified_events()
        if release is not None and (not isinstance(release, str) or
                                    not _RELEASE.fullmatch(release)):
            raise TeamBoardError("invalid_release", "Invalid release ID")
        return tuple(row for row in self.tasks.tasks()
                     if release is None or row["release"] == release)

    def create_task(self, actor, *, node_id, path, expected_head, title,
                    assignee="", release=""):
        self._role(actor, contribute=True)
        if assignee:
            self.policy.require(assignee)
        node = self._node(node_id)
        return self.tasks.append(
            expected_head=expected_head, kind="create", node=node,
            anchor=self._anchor(path), actor=actor, title=title,
            assignee=assignee, release=release)

    def change_task(self, actor, *, task_id, expected_head,
                    status=None, assignee=None, release=None, title=None):
        role = self._role(actor, contribute=True)
        tasks = {row["task"]: row for row in self.tasks_for(actor)}
        original = tasks.get(task_id)
        if original is None:
            raise TeamBoardError("unknown_task", "Unknown task")
        # Reviewer can advance only a task assigned to them; only editors
        # can alter release ownership, assignment and title.
        if role == "reviewer" and (
                original["assignee"] != actor or assignee is not None or
                release is not None or title is not None):
            raise TeamWorkflowError("access_denied", "Reviewer can update only own task status")
        chosen_assignee = original["assignee"] if assignee is None else assignee
        if chosen_assignee:
            self.policy.require(chosen_assignee)
        node = self._node(original["node"])
        return self.tasks.append(
            expected_head=expected_head, kind="update", node=node,
            anchor=original["anchor"], actor=actor, task=task_id,
            title=original["title"] if title is None else title,
            status=original["status"] if status is None else status,
            assignee=chosen_assignee,
            release=original["release"] if release is None else release)

    def review(self, actor, *, node_id, path, expected_head, decision, summary):
        self._role(actor, contribute=True)
        node = self._node(node_id)
        return self.tasks.append(
            expected_head=expected_head, kind="review", node=node,
            anchor=self._anchor(path), actor=actor, title=summary,
            status=decision)

    def decisions(self, actor, *, node_id=None):
        self._role(actor)
        rows = self._verified_events()
        if node_id is not None:
            self._node(node_id)
        # The newest vote per actor/resource supersedes that author's prior
        # advisory vote. It does not grant write permission or apply a merge.
        latest = {}
        for row in rows:
            if row["kind"] == "review" and (node_id is None or row["node"] == node_id):
                latest[(row["node"], row["anchor"], row["actor"])] = row
        return tuple(dict(row) for row in sorted(latest.values(),
                         key=lambda event: event["sequence"]))

    def release_board(self, actor):
        self._role(actor)
        grouped = defaultdict(lambda: {"todo": [], "in_progress": [], "done": []})
        for task in self.tasks_for(actor):
            grouped[task["release"] or "unassigned"][task["status"]].append(task)
        return {release: {status: tuple(dict(row) for row in tasks)
                          for status, tasks in columns.items()}
                for release, columns in sorted(grouped.items())}

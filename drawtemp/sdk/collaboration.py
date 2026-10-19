"""R48.A — offline-first project collaboration on canonical authoring documents.

This module does not own game state, save a sidecar, authenticate authors or
rewrite Git refs. Content/GameProject validation and AuthoringSession remain
the only authoring authority. Revision parents are explicit *declared*
provenance: a real Git ancestry guarantee must be checked by R30.D's Git
adapter, not inferred from these metadata alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.semantic_review import (
    fingerprint_pair, preview_merge, resolve_merge, stage_merge,
)
from sporebound.studio_transaction import validate_pair

_HEX = re.compile(r"[0-9a-f]{64}\Z")
SCHEMA = 1


class CollaborationError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ProjectRevision:
    """Detached immutable JSON revision: never a second persistence schema."""

    schema: int
    author: str
    parents: tuple[str, ...]
    digest: str
    _payload: bytes = field(repr=False)

    def documents(self):
        pair = json.loads(self._payload.decode("utf-8"))
        return pair["content"], pair["project"]

    def to_dict(self):
        """Metadata only; canonical content is never leaked into audit metadata."""
        return {"schema": self.schema, "author": self.author,
                "parents": list(self.parents), "digest": self.digest}


def make_revision(content, project, *, author: str, parents=()) -> ProjectRevision:
    """Validate and freeze a Content/GameProject pair plus declared parents."""
    if not isinstance(author, str) or not (1 <= len(author.strip()) <= 80):
        raise CollaborationError("invalid_author", "Author label must be 1..80 characters")
    if (not isinstance(parents, (tuple, list)) or len(parents) > 2 or
            len(set(parents)) != len(parents) or
            any(not isinstance(p, str) or not _HEX.fullmatch(p) for p in parents)):
        raise CollaborationError("invalid_parents", "Expected up to two unique SHA-256 parents")
    data, manifest = validate_pair(content, project)
    payload = json.dumps({"content": data, "project": manifest},
                         sort_keys=True, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    digest = sha256(payload).hexdigest()
    # A branch may contain no document edits; its content digest can equal
    # the declared parent's digest without implying a revision-graph cycle.
    return ProjectRevision(SCHEMA, author.strip(), tuple(parents), digest, payload)


def _checked(revision):
    if (not isinstance(revision, ProjectRevision) or revision.schema != SCHEMA or
            not isinstance(revision._payload, bytes) or
            sha256(revision._payload).hexdigest() != revision.digest):
        raise CollaborationError("invalid_revision", "Revision payload or schema was changed")
    content, project = revision.documents()
    if (make_revision(content, project, author=revision.author,
                      parents=revision.parents).digest != revision.digest):
        raise CollaborationError("invalid_revision", "Non-canonical project revision")
    return content, project


@dataclass(frozen=True)
class CollaborationReview:
    source_revision: int
    base_digest: str
    local_digest: str
    incoming_digest: str
    conflicts: tuple
    local_changes: tuple
    incoming_changes: tuple
    candidate_digest: str | None

    @property
    def can_apply(self):
        return not self.conflicts and self.candidate_digest is not None


class CollaborationController:
    """A single explicit three-way review followed by one Undo/Redo transaction.

    No save(), Git mutations, implicit conflict choices, network, background
    writes or Player changes. Every apply recomputes the resolved candidate
    from pinned revisions and rechecks the live authoring revision/digest.
    """

    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise TypeError("An AuthoringSession is required")
        self.session = session
        self.invalidate()

    def invalidate(self):
        self._draft = None
        self._revisions = None

    def compare(self, base: ProjectRevision, local: ProjectRevision,
                incoming: ProjectRevision) -> CollaborationReview:
        self.invalidate()
        b_content, b_project = _checked(base)
        l_content, l_project = _checked(local)
        r_content, r_project = _checked(incoming)
        if (local.parents != (base.digest,) or
                incoming.parents != (base.digest,)):
            raise CollaborationError(
                "unrelated_history",
                "Both revisions must declare the same immediate base; rebase first")
        live = self.session.snapshot()
        data = live.to_dict()
        if fingerprint_pair(data["content"], data["project"]) != local.digest:
            raise CollaborationError(
                "stale_local", "The local authoring documents differ from the reviewed revision")
        preview = preview_merge(
            b_content, b_project, l_content, l_project,
            r_content, r_project, typed_sequences=True)
        draft = CollaborationReview(
            live.revision, base.digest, local.digest, incoming.digest,
            preview.conflicts, preview.local_changes,
            preview.incoming_changes, preview.candidate_fingerprint)
        self._draft = draft
        self._revisions = (base, local, incoming)
        return draft

    def apply(self, review: CollaborationReview, decisions: dict[str, str]):
        if review is not self._draft or self._revisions is None:
            raise CollaborationError("no_review", "Compare the revisions before applying")
        live = self.session.snapshot()
        data = live.to_dict()
        if (live.revision != review.source_revision or
                fingerprint_pair(data["content"], data["project"]) != review.local_digest):
            raise CollaborationError("stale_local", "The editor changed since review")
        base, local, incoming = self._revisions
        b_content, b_project = _checked(base)
        l_content, l_project = _checked(local)
        r_content, r_project = _checked(incoming)
        candidate = resolve_merge(
            b_content, b_project, l_content, l_project,
            r_content, r_project, decisions, typed_sequences=True)
        # Reuse the canonical validator, preview/apply and one Undo step.
        plan = stage_merge(self.session, candidate, expected_revision=review.source_revision)
        transition = self.session.apply(plan)
        self.invalidate()
        return transition

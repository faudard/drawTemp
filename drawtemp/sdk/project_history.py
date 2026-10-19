"""R48.A3: bounded offline revision graph and conservative multi-generation review.

The graph is an in-memory index of validated Content/GameProject snapshots;
it is NOT a separate game persistence format, a Git replacement, a cryptographic
proof of authorship, or an authority for save/replay. It never writes to disk.
Individual node identities include ancestry, unlike document-only digests:
two branches may contain identical documents without becoming one branch.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from hashlib import sha256
import json

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import (
    CollaborationController, CollaborationError, CollaborationReview,
    ProjectRevision, _checked,
)
from drawtemp.sdk.semantic_review import fingerprint_pair, preview_merge

MAX_NODES = 2048
MAX_PARENTS = 2


def _node_identity(revision: ProjectRevision, parents: tuple[str, ...], label: str):
    data = {
        "version": 1, "document": revision.digest, "author": revision.author,
        "parents": list(parents), "label": label,
    }
    return sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RevisionNode:
    node_id: str
    revision: ProjectRevision
    parents: tuple[str, ...]
    label: str

    def to_dict(self):
        return {
            "id": self.node_id, "digest": self.revision.digest,
            "author": self.revision.author, "parents": list(self.parents),
            "label": self.label,
        }


class RevisionGraph:
    """Append-only in-memory DAG. Parents must already exist and be validated."""

    def __init__(self, *, limit=MAX_NODES):
        if type(limit) is not int or not 1 <= limit <= MAX_NODES:
            raise CollaborationError("invalid_limit", "Invalid revision history capacity")
        self._limit = limit
        self._nodes: dict[str, RevisionNode] = {}

    def add(self, revision: ProjectRevision, *, parents=(), label="") -> RevisionNode:
        _checked(revision)
        if (not isinstance(parents, (tuple, list)) or
                not 0 <= len(parents) <= MAX_PARENTS or
                len(parents) != len(set(parents)) or
                any(not isinstance(item, str) or item not in self._nodes
                    for item in parents)):
            raise CollaborationError("invalid_parents", "Expected 0..2 distinct known parent node IDs")
        if (not isinstance(label, str) or len(label) > 120):
            raise CollaborationError("invalid_label", "Revision label exceeds 120 characters")
        if len(self._nodes) >= self._limit:
            raise CollaborationError("history_limit", "Bounded history is full")
        parent_ids = tuple(parents)
        # Declared content parents and explicit graph identities are separate.
        # An unchanged child can have exactly the same content digest as a
        # parent, while its node_id remains different.
        declared = tuple(self._nodes[parent].revision.digest for parent in parent_ids)
        if revision.parents != declared:
            raise CollaborationError(
                "unrelated_history", "Declared document parents differ from graph parents")
        identity = _node_identity(revision, parent_ids, label)
        if identity in self._nodes:
            raise CollaborationError("duplicate_revision", "Revision already present")
        node = RevisionNode(identity, revision, parent_ids, label)
        self._nodes[identity] = node
        return node

    def node(self, node_id: str) -> RevisionNode:
        try:
            node = self._nodes[node_id]
        except (KeyError, TypeError) as exc:
            raise CollaborationError("unknown_revision", "Unknown revision node") from exc
        if node.node_id != _node_identity(node.revision, node.parents, node.label):
            raise CollaborationError("invalid_revision", "Revision graph node was modified")
        _checked(node.revision)
        return node

    def ancestors(self, node_id: str) -> dict[str, int]:
        """All ancestors including self, with shortest distance from node."""
        self.node(node_id)
        result = {node_id: 0}
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            for parent in self.node(current).parents:
                if parent not in result:
                    result[parent] = result[current] + 1
                    queue.append(parent)
        return result

    def common_bases(self, local_id: str, incoming_id: str) -> tuple[str, ...]:
        """Return all non-dominated common ancestors; never choose by recency."""
        left, right = self.ancestors(local_id), self.ancestors(incoming_id)
        common = set(left) & set(right)
        latest = []
        for candidate in common:
            if not any(candidate != other and
                       candidate in self.ancestors(other)
                       for other in common):
                latest.append(candidate)
        return tuple(sorted(latest))

    def choose_base(self, local_id: str, incoming_id: str, *,
                    base_id: str | None = None) -> RevisionNode:
        candidates = self.common_bases(local_id, incoming_id)
        if not candidates:
            raise CollaborationError("unrelated_history", "No shared revision ancestor")
        if base_id is not None:
            if base_id not in candidates:
                raise CollaborationError(
                    "invalid_base", "Selected base is not a maximal shared ancestor")
            return self.node(base_id)
        if len(candidates) != 1:
            raise CollaborationError(
                "ambiguous_base", "Several merge bases; choose one explicitly")
        return self.node(candidates[0])

    def __len__(self):
        return len(self._nodes)


class HistoryReviewController(CollaborationController):
    """Pin a multi-generation DAG merge against the live canonical editor."""

    def __init__(self, session: AuthoringSession, graph: RevisionGraph):
        if not isinstance(graph, RevisionGraph):
            raise TypeError("A RevisionGraph is required")
        super().__init__(session)
        self.graph = graph

    def compare_history(self, local_id: str, incoming_id: str,
                        *, base_id: str | None = None) -> CollaborationReview:
        self.invalidate()
        base = self.graph.choose_base(local_id, incoming_id, base_id=base_id)
        local = self.graph.node(local_id)
        incoming = self.graph.node(incoming_id)
        b_content, b_project = _checked(base.revision)
        l_content, l_project = _checked(local.revision)
        r_content, r_project = _checked(incoming.revision)
        live = self.session.snapshot().to_dict()
        if fingerprint_pair(live["content"], live["project"]) != local.revision.digest:
            raise CollaborationError(
                "stale_local", "Live editor differs from the selected local revision")
        review = preview_merge(
            b_content, b_project, l_content, l_project,
            r_content, r_project, typed_sequences=True)
        result = CollaborationReview(
            live["revision"], base.revision.digest, local.revision.digest,
            incoming.revision.digest, review.conflicts, review.local_changes,
            review.incoming_changes, review.candidate_fingerprint)
        # Same pinned immutable candidate and apply() path as R48.A1.
        self._draft = result
        self._revisions = (base.revision, local.revision, incoming.revision)
        return result

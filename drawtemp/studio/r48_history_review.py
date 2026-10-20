"""R48.B: Qt-independent workspace for canonical project-history reviews.

All edits remain owned by one AuthoringSession. Imports reuse the R30.C
pinned, validated two-file reader; ancestry is declared by the operator, not
verified Git history. The revision graph may be explicitly persisted in an optional verified sidecar. No autosave, checkout,
network access, audit append, or silent conflict choice is performed here.
"""
from __future__ import annotations

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import CollaborationError, make_revision
from drawtemp.sdk.project_history import HistoryReviewController, RevisionGraph
from drawtemp.sdk.project_history_store import LocalHistoryStore, HistoryStoreError
from drawtemp.sdk.semantic_review import fingerprint_pair
from drawtemp.studio.r30_creator_review import _disk_pair


class ProjectHistoryWorkspace:
    """Bridge file/snapshot inputs into the R48.A3 graph and merge authority."""

    def __init__(self, session: AuthoringSession, graph: RevisionGraph | None = None):
        if not isinstance(session, AuthoringSession):
            raise TypeError("An AuthoringSession is required")
        if graph is not None and not isinstance(graph, RevisionGraph):
            raise TypeError("Expected a RevisionGraph")
        self.session = session
        self.graph = graph if graph is not None else RevisionGraph()
        self.controller = HistoryReviewController(session, self.graph)
        if graph is None:
            snap = session.snapshot().to_dict()
            root = make_revision(snap["content"], snap["project"],
                                 author="studio")
            self.graph.add(root, label="Studio à l'ouverture")
        self.current_review = None
        self.history_path = None
        self.history_digest = None

    def revisions(self):
        """Return insertion-order, validated immutable revisions for Qt rows."""
        return self.graph.nodes()

    def invalidate(self):
        self.controller.invalidate()
        self.current_review = None

    def _add(self, content, project, *, parent_id, author, label):
        self.invalidate()
        if not isinstance(parent_id, str):
            raise CollaborationError("missing_parent", "Choose an explicit parent revision")
        parent = self.graph.node(parent_id)
        revision = make_revision(
            content, project, author=author, parents=(parent.revision.digest,))
        return self.graph.add(revision, parents=(parent_id,), label=label)

    def capture_live(self, *, parent_id, author="local", label="Studio actuel"):
        """Capture live documents as a child; never touch authoring history."""
        snap = self.session.snapshot().to_dict()
        return self._add(snap["content"], snap["project"],
                         parent_id=parent_id, author=author, label=label)

    def import_pair(self, content_path, *, parent_id, author, label):
        """Validate and pin both sibling files through the established R30 reader."""
        pair = _disk_pair(content_path)
        return self._add(pair.content, pair.project,
                         parent_id=parent_id, author=author, label=label)

    def compare(self, local_id, incoming_id, *, base_id=None):
        self.invalidate()
        if local_id == incoming_id:
            raise CollaborationError("same_revision", "Choose two distinct history nodes")
        preview = self.controller.compare_history(
            local_id, incoming_id, base_id=base_id)
        self.current_review = preview
        return preview

    def apply(self, choices):
        """Explicitly apply one complete review through R1, preserving Undo."""
        if self.current_review is None:
            raise CollaborationError("no_review", "Compare revisions first")
        transition = self.controller.apply(self.current_review, choices)
        self.current_review = None
        return transition

    def save_history(self, path=None):
        """Explicitly save a complete validated DAG; never overwrite blindly."""
        chosen = path if path is not None else self.history_path
        if chosen is None:
            raise HistoryStoreError("missing_destination", "Choose a history file first")
        target = LocalHistoryStore(chosen)
        if self.history_path is not None and target.path != self.history_path:
            raise HistoryStoreError(
                "wrong_destination", "Choose another workspace before switching history files")
        digest = target.save(self.graph, expected_digest=self.history_digest)
        self.history_path, self.history_digest = target.path, digest
        return digest

    def load_history(self, path):
        """Replace only the history INDEX after verifying it includes this editor.

        No Content/GameProject modifications occur, and the previous index is
        retained unchanged on all failures (including cross-project imports).
        """
        store = LocalHistoryStore(path)
        graph, digest = store.load()
        live = self.live_digest()
        if all(node.revision.digest != live for node in graph.nodes()):
            raise HistoryStoreError(
                "unrelated_project", "History contains no snapshot of the active Studio")
        self.invalidate()
        self.graph = graph
        self.controller = HistoryReviewController(self.session, graph)
        self.history_path, self.history_digest = store.path, digest
        return graph

    def live_digest(self):
        snap = self.session.snapshot().to_dict()
        return fingerprint_pair(snap["content"], snap["project"])

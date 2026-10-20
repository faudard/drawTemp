"""R48.A4 — explicit, squashed Content/GameProject rebase onto a known node.

This is NOT git rebase and does not replay individual commits. It performs a
conservative three-way semantic merge with the upstream ("onto") as live
AuthoringSession state, followed by an optional explicit registration of ONE
new child of that upstream DAG node. The rebase cannot silently overwrite
conflicts; the same R30 rules and one R1 Undo transaction are used.
"""
from __future__ import annotations

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import CollaborationError, make_revision
from drawtemp.sdk.project_history import HistoryReviewController, RevisionGraph
from drawtemp.sdk.semantic_review import fingerprint_pair


class SquashRebaseController:
    """Compare -> resolve/apply in Studio -> explicitly register rebased node."""

    def __init__(self, session: AuthoringSession, graph: RevisionGraph):
        self.session = session
        self.graph = graph
        self.review_controller = HistoryReviewController(session, graph)
        self.invalidate()

    def invalidate(self):
        self.review_controller.invalidate()
        self._draft = None
        self._onto = None
        self._applied = None

    def preview(self, *, topic_id: str, onto_id: str, base_id=None):
        """Review how topic changes overlay the live upstream (onto).

        The user must open the upstream in the owning Studio first. Unique
        maximal merge-base is required unless base_id is supplied explicitly.
        """
        self.invalidate()
        if topic_id == onto_id:
            raise CollaborationError("same_revision", "Topic and upstream must differ")
        review = self.review_controller.compare_history(
            onto_id, topic_id, base_id=base_id)
        self._draft = review
        self._onto = onto_id
        return review

    def apply(self, review, decisions):
        if review is not self._draft or self._onto is None:
            raise CollaborationError("no_review", "Preview the proposed rebase first")
        result = self.review_controller.apply(review, decisions)
        data = result.snapshot.to_dict()
        self._applied = (
            self._onto, data["revision"],
            fingerprint_pair(data["content"], data["project"]))
        self._draft = None
        self._onto = None
        return result

    def register(self, *, author, label="Rebased snapshot"):
        """Explicitly register ONE rebased child. No disk save or Git changes.

        If registering fails, the Studio's applied state remains intact and
        can be undone. Never assume graph publication and Studio mutation are
        one atomic operation; persistence requires an independent CAS save.
        """
        if self._applied is None:
            raise CollaborationError("no_rebase", "Apply a reviewed rebase first")
        onto_id, expected_revision, expected_digest = self._applied
        snap = self.session.snapshot().to_dict()
        if (snap["revision"] != expected_revision or
                fingerprint_pair(snap["content"], snap["project"]) != expected_digest):
            raise CollaborationError(
                "stale_rebase", "Studio changed since rebase application")
        parent = self.graph.node(onto_id)
        revision = make_revision(snap["content"], snap["project"],
                                 author=author, parents=(parent.revision.digest,))
        node = self.graph.add(revision, parents=(onto_id,), label=label)
        self._applied = None
        return node

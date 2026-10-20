"""R48.A4 — review-first squashed rebase, not a Git history rewrite."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import CollaborationError, make_revision
from drawtemp.sdk.project_history import RevisionGraph
from drawtemp.sdk.project_history_store import LocalHistoryStore
from drawtemp.sdk.project_rebase import SquashRebaseController
from drawtemp.sdk.reference import reference_project


class SquashedRebaseTests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.content, self.project = content.to_dict(), project.to_dict()
        self.graph = RevisionGraph()
        revision = make_revision(self.content, self.project, author="root")
        self.root = self.graph.add(revision, label="root")

    def node(self, project, parent, *, author="alice", label="edit"):
        rev = make_revision(self.content, project, author=author,
                            parents=(parent.revision.digest,))
        return self.graph.add(rev, parents=(parent.node_id,), label=label)

    def test_two_author_rebase_publishes_child_of_onto_without_writing_git(self):
        a = deepcopy(self.project); a["title"] = "Alice"
        topic = self.node(a, self.root, label="topic")
        b = deepcopy(self.project); b["subtitle"] = "Bob"
        upstream = self.node(b, self.root, author="bob", label="upstream")
        session = AuthoringSession.new(self.content, b)
        controller = SquashRebaseController(session, self.graph)
        result = controller.preview(topic_id=topic.node_id, onto_id=upstream.node_id)
        self.assertTrue(result.can_apply)
        self.assertEqual(result.conflicts, ())
        applied = controller.apply(result, {})
        self.assertEqual(applied.snapshot.project["title"], "Alice")
        self.assertEqual(applied.snapshot.project["subtitle"], "Bob")
        self.assertEqual(session.undo().snapshot.project["title"], self.project["title"])
        # Undo intentionally invalidates an unregistered rebase.
        with self.assertRaises(CollaborationError) as caught:
            controller.register(author="alice")
        self.assertEqual(caught.exception.code, "stale_rebase")
        session.redo()
        with self.assertRaises(CollaborationError):
            controller.register(author="alice")  # ABA revision was incremented.
        # Local live state is no longer the upstream; comparison must fail.
        with self.assertRaises(CollaborationError) as caught:
            controller.preview(topic_id=topic.node_id, onto_id=upstream.node_id)
        self.assertEqual(caught.exception.code, "stale_local")
        self.assertEqual(len(self.graph), 3)

    def test_rebase_register_roundtrip_and_undo(self):
        a = deepcopy(self.project); a["title"] = "Alice"
        topic = self.node(a, self.root, label="topic")
        b = deepcopy(self.project); b["subtitle"] = "Bob"
        upstream = self.node(b, self.root, author="bob", label="upstream")
        session = AuthoringSession.new(self.content, b)
        controller = SquashRebaseController(session, self.graph)
        result = controller.preview(topic_id=topic.node_id, onto_id=upstream.node_id)
        controller.apply(result, {})
        created = controller.register(author="alice", label="rebase branch")
        self.assertEqual(created.parents, (upstream.node_id,))
        self.assertNotEqual(created.revision.digest, topic.revision.digest)
        self.assertEqual(session.undo().snapshot.project["subtitle"], "Bob")
        with TemporaryDirectory() as tmp:
            store = LocalHistoryStore(Path(tmp) / "history.r48.json")
            store.save(self.graph)
            restored, _ = store.load()
            self.assertEqual(restored.node(created.node_id).label, "rebase branch")
            self.assertEqual(restored.node(created.node_id).parents, (upstream.node_id,))

    def test_conflicting_rebase_requires_manual_selection(self):
        a = deepcopy(self.project); a["title"] = "Alice"
        b = deepcopy(self.project); b["title"] = "Bob"
        topic = self.node(a, self.root, author="alice", label="topic")
        upstream = self.node(b, self.root, author="bob", label="upstream")
        session = AuthoringSession.new(self.content, b)
        rebase = SquashRebaseController(session, self.graph)
        review = rebase.preview(topic_id=topic.node_id, onto_id=upstream.node_id)
        self.assertEqual([c.path for c in review.conflicts], ["/project/title"])
        before = session.snapshot().to_dict()
        with self.assertRaises(ValueError):
            rebase.apply(review, {})
        self.assertEqual(session.snapshot().to_dict(), before)
        result = rebase.apply(review, {"/project/title": "incoming"})
        self.assertEqual(result.snapshot.project["title"], "Alice")
        self.assertEqual(rebase.register(author="alice").parents,
                         (upstream.node_id,))

    def test_cross_project_and_stale_editor_are_refused(self):
        a = deepcopy(self.project); a["title"] = "Alice"
        topic = self.node(a, self.root)
        upstream = self.root
        session = AuthoringSession.new(self.content, self.project)
        rebase = SquashRebaseController(session, self.graph)
        review = rebase.preview(topic_id=topic.node_id, onto_id=upstream.node_id)
        session.apply(session.preview_project(lambda p: {**p, "subtitle": "Unexpected"}))
        with self.assertRaises(CollaborationError) as caught:
            rebase.apply(review, {})
        self.assertEqual(caught.exception.code, "stale_local")
        with self.assertRaises(CollaborationError) as caught:
            rebase.register(author="alice")
        self.assertEqual(caught.exception.code, "no_rebase")


if __name__ == "__main__":
    unittest.main()

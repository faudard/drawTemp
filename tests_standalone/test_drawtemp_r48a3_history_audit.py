"""R48.A3: real multi-generation DAG and forensic audit reconciliation."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import CollaborationError, make_revision
from drawtemp.sdk.project_audit import AuditError, LocalAuditLog
from drawtemp.sdk.project_history import (
    HistoryReviewController, RevisionGraph,
)
from drawtemp.sdk.audit_reconciliation import reconcile_audit
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.semantic_review import fingerprint_pair


class HistoryTests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.content, self.project = content.to_dict(), project.to_dict()
        self.root = make_revision(self.content, self.project, author="root")
        self.graph = RevisionGraph()
        self.root_node = self.graph.add(self.root, label="root")

    def revision(self, project, parent, *, name, label):
        revision = make_revision(self.content, project, author=name,
                                 parents=(parent.revision.digest,))
        return self.graph.add(revision, parents=(parent.node_id,), label=label)

    def test_two_generations_merge_and_single_undo(self):
        a1 = deepcopy(self.project)
        a1["title"] = "Alice's RPG"
        alice1 = self.revision(a1, self.root_node, name="alice", label="A1")
        a2 = deepcopy(a1)
        a2["subtitle"] = "Local subtitle"
        alice2 = self.revision(a2, alice1, name="alice", label="A2")
        b1 = deepcopy(self.project)
        b1["story"]["scenes"][0]["title"] = "Remote intro"
        bob = self.revision(b1, self.root_node, name="bob", label="B1")
        self.assertEqual(self.graph.common_bases(alice2.node_id, bob.node_id),
                         (self.root_node.node_id,))
        session = AuthoringSession.new(self.content, a2)
        controller = HistoryReviewController(session, self.graph)
        review = controller.compare_history(alice2.node_id, bob.node_id)
        self.assertTrue(review.can_apply)
        transition = controller.apply(review, {})
        merged = transition.snapshot.project
        self.assertEqual(merged["title"], "Alice's RPG")
        self.assertEqual(merged["subtitle"], "Local subtitle")
        self.assertEqual(merged["story"]["scenes"][0]["title"], "Remote intro")
        restored = session.undo().snapshot.project
        self.assertEqual(restored["story"]["scenes"][0]["title"],
                         self.project["story"]["scenes"][0]["title"])

    def test_identical_content_different_revision_nodes(self):
        unchanged = self.revision(self.project, self.root_node,
                                  name="alice", label="no-document-edit")
        self.assertEqual(unchanged.revision.digest, self.root.digest)
        self.assertNotEqual(unchanged.node_id, self.root_node.node_id)
        next_unchanged = self.revision(self.project, unchanged,
                                       name="alice", label="next")
        self.assertEqual(self.graph.common_bases(next_unchanged.node_id,
                                                 self.root_node.node_id),
                         (self.root_node.node_id,))

    def test_unrelated_and_missing_parents_fail_without_mutation(self):
        another_root = self.graph.add(
            make_revision(self.content, {**self.project, "title": "Unrelated"},
                          author="root"), label="independent")
        with self.assertRaises(CollaborationError) as caught:
            self.graph.choose_base(self.root_node.node_id, another_root.node_id)
        self.assertEqual(caught.exception.code, "unrelated_history")
        before = len(self.graph)
        with self.assertRaises(CollaborationError) as caught:
            self.graph.add(self.root, parents=("0" * 64,))
        self.assertEqual(caught.exception.code, "invalid_parents")
        self.assertEqual(len(self.graph), before)

    def test_malformed_parents_and_altered_graph_nodes_fail_closed(self):
        with self.assertRaises(CollaborationError) as caught:
            self.graph.add(self.root, parents=([self.root_node.node_id],))
        self.assertEqual(caught.exception.code, "invalid_parents")
        original = self.graph.node(self.root_node.node_id)
        self.graph._nodes[original.node_id] = replace(original, label="tampered")
        with self.assertRaises(CollaborationError) as caught:
            self.graph.node(original.node_id)
        self.assertEqual(caught.exception.code, "invalid_revision")
        child = make_revision(self.content, self.project, author="alice",
                              parents=(self.root.digest,))
        with self.assertRaises(CollaborationError) as caught:
            self.graph.add(child, parents=(original.node_id,), label="child")
        self.assertEqual(caught.exception.code, "invalid_revision")

    def test_duplicate_nodes_and_history_limits(self):
        with self.assertRaises(CollaborationError) as caught:
            self.graph.add(self.root, label="root")
        self.assertEqual(caught.exception.code, "duplicate_revision")
        graph = RevisionGraph(limit=1)
        graph.add(self.root)
        with self.assertRaises(CollaborationError) as caught:
            graph.add(self.root, label="new")
        self.assertEqual(caught.exception.code, "history_limit")

    def test_ambiguous_criss_cross_requires_explicit_maximal_base(self):
        a = deepcopy(self.project); a["title"] = "A title"
        b = deepcopy(self.project); b["subtitle"] = "B subtitle"
        node_a = self.revision(a, self.root_node, name="alice", label="A")
        node_b = self.revision(b, self.root_node, name="bob", label="B")
        joined = deepcopy(a); joined["subtitle"] = "B subtitle"
        left_revision = make_revision(
            self.content, joined, author="alice",
            parents=(node_a.revision.digest, node_b.revision.digest))
        right_revision = make_revision(
            self.content, joined, author="bob",
            parents=(node_b.revision.digest, node_a.revision.digest))
        left = self.graph.add(left_revision, parents=(node_a.node_id, node_b.node_id),
                              label="left_merge")
        right = self.graph.add(right_revision, parents=(node_b.node_id, node_a.node_id),
                               label="right_merge")
        common = self.graph.common_bases(left.node_id, right.node_id)
        self.assertEqual(set(common), {node_a.node_id, node_b.node_id})
        with self.assertRaises(CollaborationError) as caught:
            self.graph.choose_base(left.node_id, right.node_id)
        self.assertEqual(caught.exception.code, "ambiguous_base")
        with self.assertRaises(CollaborationError) as caught:
            self.graph.choose_base(left.node_id, right.node_id,
                                   base_id=self.root_node.node_id)
        self.assertEqual(caught.exception.code, "invalid_base")
        session = AuthoringSession.new(self.content, joined)
        controller = HistoryReviewController(session, self.graph)
        review = controller.compare_history(
            left.node_id, right.node_id, base_id=node_a.node_id)
        self.assertEqual(review.base_digest, node_a.revision.digest)

    def test_stale_review_with_multigeneration_undo_aba(self):
        updated = deepcopy(self.project); updated["title"] = "Alice"
        node_a = self.revision(updated, self.root_node,
                               name="alice", label="A1")
        incoming = deepcopy(self.project); incoming["subtitle"] = "Bob"
        node_b = self.revision(incoming, self.root_node,
                               name="bob", label="B1")
        session = AuthoringSession.new(self.content, updated)
        controller = HistoryReviewController(session, self.graph)
        review = controller.compare_history(node_a.node_id, node_b.node_id)
        plan = session.preview_project(lambda p: {**p, "title": "temporary"})
        session.apply(plan); session.undo()
        before = session.snapshot().to_dict()
        with self.assertRaises(CollaborationError) as caught:
            controller.apply(review, {})
        self.assertEqual(caught.exception.code, "stale_local")
        self.assertEqual(session.snapshot().to_dict(), before)


class AuditReconciliationTests(unittest.TestCase):
    def setUp(self):
        source, project = reference_project()
        self.session = AuthoringSession.new(source, project)
        self.original = self.session.snapshot().to_dict()
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "audit.jsonl"
        self.audit = LocalAuditLog(self.path)
        self.base = make_revision(self.original["content"], self.original["project"],
                                  author="alice")

    def edit(self, title):
        self.session.apply(self.session.preview_project(
            lambda project: {**project, "title": title}))
        data = self.session.snapshot().to_dict()
        return make_revision(data["content"], data["project"], author="alice",
                             parents=(self.base.digest,))

    def test_aligned_partial_and_drift_are_not_approval(self):
        updated = self.edit("New title")
        event = self.audit.append(
            expected_head=None, actor="alice", operation="rename",
            resource="project", before=self.base.digest, after=updated.digest)
        # Without the original snapshot the forensic evidence is incomplete.
        partial = reconcile_audit(self.audit, self.session)
        self.assertEqual(partial.state, "partial_evidence")
        self.assertEqual(partial.unknown_records, (1,))
        complete = reconcile_audit(
            self.audit, self.session,
            known_revisions=(self.base, updated),
            expected_head=event["digest"])
        self.assertEqual(complete.state, "aligned")
        self.assertTrue(complete.anchored)
        self.assertEqual(complete.count, 1)
        self.edit("Changed again, not audited")
        drift = reconcile_audit(self.audit, self.session,
                                known_revisions=(self.base, updated))
        self.assertEqual(drift.state, "drift")
        self.assertNotEqual(drift.current_digest, drift.audited_after)

    def test_pinned_head_detects_removed_or_replaced_audit(self):
        event = self.audit.append(
            expected_head=None, actor="alice", operation="rename",
            resource="project", before=self.base.digest,
            after=self.base.digest)
        self.path.unlink()
        with self.assertRaises(AuditError) as caught:
            reconcile_audit(self.audit, self.session, expected_head=event["digest"])
        self.assertEqual(caught.exception.code, "audit_head_changed")
        self.assertEqual(reconcile_audit(self.audit, self.session).state, "empty")

    def test_valid_but_noncontiguous_events_are_flagged(self):
        self.audit.append(
            expected_head=None, actor="alice", operation="rename",
            resource="project", before=self.base.digest,
            after="a" * 64)
        state = self.audit.inspect()
        self.audit.append(
            expected_head=state["head"], actor="bob", operation="merge",
            resource="scene", before="b" * 64,
            after=self.base.digest)
        report = reconcile_audit(self.audit, self.session,
                                 known_revisions=(self.base,))
        self.assertEqual(report.state, "partial_evidence")
        self.assertEqual(report.discontinuities, (2,))
        self.assertEqual(report.unknown_records, (1, 2))

    def test_corrupt_history_fails_closed(self):
        self.audit.append(
            expected_head=None, actor="alice", operation="rename",
            resource="project", before=self.base.digest,
            after=self.base.digest)
        raw = self.path.read_bytes().replace(b'"actor":"alice"', b'"actor":"hacker"')
        self.path.write_bytes(raw)
        with self.assertRaises(AuditError):
            reconcile_audit(self.audit, self.session,
                            known_revisions=(self.base,))


if __name__ == "__main__":
    unittest.main()

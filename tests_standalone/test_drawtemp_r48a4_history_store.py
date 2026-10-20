"""R48.A4 — durable, conservative history archive and crash gates."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import make_revision
from drawtemp.sdk.project_history import HistoryReviewController, RevisionGraph
from drawtemp.sdk.project_history_store import (
    HistoryStoreError, LocalHistoryStore,
)
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r48_history_review import ProjectHistoryWorkspace


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "history.r48.json"
        self.store = LocalHistoryStore(self.path)
        self.content, self.project = reference_project()
        self.session = AuthoringSession.new(self.content, self.project)
        self.base = self.session.snapshot().to_dict()
        self.graph = RevisionGraph()
        root_rev = make_revision(self.base["content"], self.base["project"],
                                 author="root")
        self.root_node = self.graph.add(root_rev, label="root")

    def child(self, project, parent, *, author, label):
        rev = make_revision(self.base["content"], project, author=author,
                            parents=(parent.revision.digest,))
        return self.graph.add(rev, parents=(parent.node_id,), label=label)

    def test_roundtrip_graph_nodes_with_multigeneration_and_identical_digests(self):
        a1 = deepcopy(self.base["project"]); a1["title"] = "Alice"
        alice = self.child(a1, self.root_node, author="alice", label="A1")
        same = self.child(a1, alice, author="alice", label="no-content-change")
        b1 = deepcopy(self.base["project"]); b1["subtitle"] = "Bob"
        bob = self.child(b1, self.root_node, author="bob", label="B1")
        self.assertNotEqual(same.node_id, alice.node_id)
        digest = self.store.save(self.graph)
        self.assertEqual(self.store.inspect(), digest)
        restored, loaded_digest = self.store.load()
        self.assertEqual(digest, loaded_digest)
        self.assertEqual([n.to_dict() for n in restored.nodes()],
                         [n.to_dict() for n in self.graph.nodes()])
        self.assertEqual(restored.common_bases(same.node_id, bob.node_id),
                         (self.root_node.node_id,))
        self.assertEqual(self.session.snapshot().to_dict(), self.base)

    def test_two_parents_can_have_identical_document_digest(self):
        unchanged = self.child(self.base["project"], self.root_node,
                               author="alice", label="same-data")
        self.assertEqual(unchanged.revision.digest, self.root_node.revision.digest)
        parents = (self.root_node.node_id, unchanged.node_id)
        rev = make_revision(self.base["content"], self.base["project"],
                            author="merge", parents=(
                                self.root_node.revision.digest,
                                unchanged.revision.digest))
        joined = self.graph.add(rev, parents=parents, label="same-content-merge")
        self.store.save(self.graph)
        restored, _ = self.store.load()
        self.assertEqual(restored.node(joined.node_id).parents, parents)

    def test_optimistic_create_and_save_after_loaded_digest(self):
        initial = self.store.save(self.graph)
        before = self.path.read_bytes()
        with self.assertRaises(HistoryStoreError) as caught:
            self.store.save(self.graph)
        self.assertEqual(caught.exception.code, "stale_archive")
        self.assertEqual(self.path.read_bytes(), before)
        more = self.child(self.base["project"], self.root_node,
                          author="alice", label="next")
        latest = self.store.save(self.graph, expected_digest=initial)
        self.assertNotEqual(latest, initial)
        with self.assertRaises(HistoryStoreError):
            self.store.save(self.graph, expected_digest=initial)
        self.assertEqual(self.store.inspect(), latest)

    def test_tampered_node_or_checksum_fails_without_mutation(self):
        self.store.save(self.graph)
        original = self.path.read_bytes()
        envelope = json.loads(original)
        envelope["payload"]["nodes"][0]["label"] = "fake"
        self.path.write_text(json.dumps(envelope), encoding="utf-8")
        altered = self.path.read_bytes()
        with self.assertRaises(HistoryStoreError) as caught:
            self.store.load()
        self.assertEqual(caught.exception.code, "invalid_digest")
        with self.assertRaises(HistoryStoreError):
            self.store.save(self.graph, expected_digest="0" * 64)
        self.assertEqual(self.path.read_bytes(), altered)

    def test_rehashed_forged_node_still_refused(self):
        import hashlib
        self.store.save(self.graph)
        data = json.loads(self.path.read_text())
        data["payload"]["nodes"][0]["label"] = "forged"
        raw = json.dumps(data["payload"], sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
        data["digest"] = hashlib.sha256(raw).hexdigest()
        self.path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(HistoryStoreError) as caught:
            self.store.load()
        self.assertEqual(caught.exception.code, "invalid_node")

    def test_truncated_file_and_duplicate_json_fields_fail_closed(self):
        self.path.write_bytes(b'{"schema":')
        with self.assertRaises(HistoryStoreError):
            self.store.load()
        self.path.write_text(
            '{"schema":1,"schema":1,"payload":{"nodes":[]},"digest":"x"}')
        with self.assertRaises(HistoryStoreError) as caught:
            self.store.inspect()
        self.assertEqual(caught.exception.code, "duplicate_field")

    def test_failed_atomic_replace_preserves_old_archive(self):
        initial = self.store.save(self.graph)
        saved = self.path.read_bytes()
        self.child(self.base["project"], self.root_node,
                   author="alice", label="branch")
        with patch("drawtemp.sdk.project_history_store.os.replace",
                   side_effect=OSError("simulated filesystem crash")):
            with self.assertRaises(OSError):
                self.store.save(self.graph, expected_digest=initial)
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertEqual(self.store.inspect(), initial)
        self.assertEqual(len(self.store.load()[0]), 1)

    def test_symlink_destination_rejected(self):
        target = self.root / "external.json"
        target.write_text("protected", encoding="utf-8")
        try:
            self.path.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("No permission to create a symlink on this OS")
        with self.assertRaises(HistoryStoreError) as caught:
            self.store.save(self.graph)
        self.assertEqual(caught.exception.code, "unsafe_path")
        self.assertEqual(target.read_text(), "protected")

    def test_workspace_wrong_project_and_changed_file_fail_closed(self):
        space = ProjectHistoryWorkspace(self.session)
        node = space.capture_live(parent_id=space.revisions()[0].node_id,
                                  author="alice", label="A1")
        source = self.root / "project-history.r48.json"
        first = space.save_history(source)
        self.assertEqual(space.history_digest, first)
        self.assertEqual(len(space.revisions()), 2)
        second_session = AuthoringSession.new(
            self.base["content"], {**self.base["project"], "title": "Other project"})
        foreign = ProjectHistoryWorkspace(second_session)
        before = [row.node_id for row in foreign.revisions()]
        with self.assertRaises(HistoryStoreError) as caught:
            foreign.load_history(source)
        self.assertEqual(caught.exception.code, "unrelated_project")
        self.assertEqual([row.node_id for row in foreign.revisions()], before)
        reloaded = ProjectHistoryWorkspace(self.session)
        reloaded.load_history(source)
        self.assertEqual(len(reloaded.revisions()), 2)
        self.assertEqual(reloaded.graph.node(node.node_id).label, "A1")
        reloaded.capture_live(parent_id=node.node_id, author="alice", label="A2")
        update = reloaded.save_history()
        self.assertNotEqual(update, first)
        with self.assertRaises(HistoryStoreError) as caught:
            space.save_history()
        self.assertEqual(caught.exception.code, "stale_archive")


if __name__ == "__main__":
    unittest.main()

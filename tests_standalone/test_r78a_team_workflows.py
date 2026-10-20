"""R78.A: roles, leases, pinned semantic review and explicit audit evidence."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import make_revision
from drawtemp.sdk.project_audit import LocalAuditLog
from drawtemp.sdk.project_history import RevisionGraph
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.team_workflows import (
    TeamAccessPolicy, TeamLeaseRegistry, TeamMergeWorkspace, TeamWorkflowError,
)


class AccessAndLeaseTests(unittest.TestCase):
    def setUp(self):
        self.policy = TeamAccessPolicy({
            "owner": "owner", "alice": "editor", "bob": "editor",
            "reviewer": "reviewer", "reader": "viewer",
        })
        self.now = [100.0]
        self.leases = TeamLeaseRegistry(self.policy, clock=lambda: self.now[0])

    def assert_code(self, code, action):
        with self.assertRaises(TeamWorkflowError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def test_unknown_and_readonly_denied_without_claimed_identity(self):
        self.assert_code("access_denied", lambda: self.leases.acquire("anonymous"))
        self.assert_code("access_denied", lambda: self.leases.acquire("reviewer"))
        self.assert_code("access_denied", lambda: self.leases.acquire("reader"))
        self.assert_code("invalid_actor", lambda: self.leases.acquire(" alice "))
        self.assertEqual(self.policy.require("reader"), "viewer")

    def test_owner_manages_roles_but_cannot_remove_last_owner(self):
        self.assert_code("access_denied", lambda: self.policy.assign("alice", "reader", "editor"))
        self.assert_code("last_owner", lambda: self.policy.assign("owner", "owner", None))
        self.policy.assign("owner", "reader", "editor")
        self.assertEqual(self.policy.require("reader", write=True), "editor")
        snapshot = self.policy.members()
        snapshot["alice"] = "owner"
        self.assertEqual(self.policy.require("alice"), "editor")
        self.policy.assign("owner", "alice", None)
        self.assert_code("access_denied", lambda: self.policy.require("alice"))

    def test_contention_expiry_and_fenced_tokens(self):
        lease = self.leases.acquire("alice", ttl=5)
        self.assertNotIn(lease.token, repr(lease))
        self.assert_code("lease_busy", lambda: self.leases.acquire("bob"))
        self.assert_code("invalid_lease", lambda: self.leases.release("bob", lease.token))
        self.now[0] += 6
        self.assert_code("invalid_lease", lambda: self.leases.renew("alice", lease.token))
        other = self.leases.acquire("bob")
        self.assertNotEqual(lease.token, other.token)
        self.assert_code("invalid_lease", lambda: self.leases.release("alice", lease.token))
        self.leases.release("bob", other.token)

    def test_renew_and_revoke_permissions_fail_closed(self):
        lease = self.leases.acquire("alice", ttl=5)
        self.now[0] += 4
        self.leases.renew("alice", lease.token, ttl=5)
        self.now[0] += 4
        self.leases.require("alice", lease.token)
        self.policy.assign("owner", "alice", "viewer")
        self.assert_code("access_denied", lambda: self.leases.require("alice", lease.token))

    def test_invalid_ttl_and_unsupported_scope(self):
        for ttl in (True, 0, -1, float("nan"), float("inf"), 3601):
            with self.subTest(ttl=ttl):
                self.assert_code("invalid_ttl", lambda: self.leases.acquire("alice", ttl=ttl))
        self.assert_code("invalid_resource", lambda: self.leases.acquire("alice", resource="scene/1"))


class MergeWorkspaceTests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.content, self.project = content.to_dict(), project.to_dict()
        self.session = AuthoringSession.new(content, project)
        self.graph = RevisionGraph()
        self.root = self.graph.add(make_revision(self.content, self.project, author="root"))
        self.policy = TeamAccessPolicy({"owner": "owner", "alice": "editor",
                                        "bob": "editor", "reviewer": "reviewer"})
        self.leases = TeamLeaseRegistry(self.policy)
        self.workspace = TeamMergeWorkspace(self.session, self.graph,
                                            self.policy, self.leases)
        self.lease = self.leases.acquire("alice")
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "title": "Alice's title"}, kind="r78.test"))
        local = self.session.snapshot().to_dict()
        self.local = self.graph.add(make_revision(
            local["content"], local["project"],
            author="alice", parents=(self.root.revision.digest,)),
            parents=(self.root.node_id,), label="local title")
        incoming_project = deepcopy(self.project)
        incoming_project["subtitle"] = "Bob's subtitle"
        self.incoming = self.graph.add(make_revision(
            self.content, incoming_project, author="bob",
            parents=(self.root.revision.digest,)),
            parents=(self.root.node_id,), label="remote subtitle")

    def review(self):
        return self.workspace.preview("alice", self.lease.token,
            local_id=self.local.node_id, incoming_id=self.incoming.node_id)

    def test_reviewer_sees_history_but_cannot_write(self):
        rows = self.workspace.revisions("reviewer")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["id"], self.root.node_id)
        with self.assertRaises(TeamWorkflowError):
            self.workspace.revisions("outsider")
        with self.assertRaises(TeamWorkflowError):
            self.leases.acquire("reviewer")

    def test_review_and_explicit_checkpoint_preserve_undo_and_no_autosave(self):
        draft = self.review()
        self.assertTrue(draft.can_apply)
        result = self.workspace.apply("alice", self.lease.token, draft, {})
        self.assertEqual(result.snapshot.project["title"], "Alice's title")
        self.assertEqual(result.snapshot.project["subtitle"], "Bob's subtitle")
        self.assertEqual(len(self.graph), 3)
        self.assertFalse(self.session.storage_status()["has_destination"])
        checkpoint = self.workspace.register("alice", self.lease.token)
        self.assertEqual(len(self.graph), 4)
        self.assertEqual(checkpoint.parents, (self.local.node_id, self.incoming.node_id))
        self.assertEqual(self.workspace.register("alice", self.lease.token).node_id,
                         checkpoint.node_id)
        self.assertEqual(self.session.undo().snapshot.project["subtitle"],
                         self.project["subtitle"])

    def test_other_actor_and_foreign_preview_cannot_apply(self):
        draft = self.review()
        with self.assertRaises(TeamWorkflowError) as caught:
            self.workspace.apply("bob", self.lease.token, draft, {})
        self.assertEqual(caught.exception.code, "invalid_lease")
        with self.assertRaises(TeamWorkflowError) as caught:
            self.workspace.apply("alice", self.lease.token, object(), {})
        self.assertEqual(caught.exception.code, "no_review")

    def test_revocation_between_preview_and_apply(self):
        draft = self.review()
        self.policy.assign("owner", "alice", "reviewer")
        with self.assertRaises(TeamWorkflowError) as caught:
            self.workspace.apply("alice", self.lease.token, draft, {})
        self.assertEqual(caught.exception.code, "access_denied")
        self.assertEqual(self.session.snapshot().project["subtitle"], self.project["subtitle"])

    def test_concurrent_editor_mutation_stales_preview(self):
        draft = self.review()
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "subtitle": "other writer"}, kind="r78.concurrent"))
        with self.assertRaises(ValueError):
            self.workspace.apply("alice", self.lease.token, draft, {})
        self.assertEqual(self.session.snapshot().project["subtitle"], "other writer")

    def test_conflicting_edit_requires_explicit_resolution(self):
        incoming_project = deepcopy(self.project)
        incoming_project["title"] = "Bob's title"
        incoming = self.graph.add(make_revision(
            self.content, incoming_project, author="bob",
            parents=(self.root.revision.digest,)),
            parents=(self.root.node_id,), label="conflicting title")
        draft = self.workspace.preview("alice", self.lease.token,
            local_id=self.local.node_id, incoming_id=incoming.node_id)
        self.assertFalse(draft.can_apply)
        self.assertEqual([row.path for row in draft.conflicts], ["/project/title"])
        with self.assertRaises(ValueError):
            self.workspace.apply("alice", self.lease.token, draft, {})
        self.assertEqual(self.session.snapshot().project["title"], "Alice's title")
        transition = self.workspace.apply("alice", self.lease.token, draft,
                                          {"/project/title": "incoming"})
        self.assertEqual(transition.snapshot.project["title"], "Bob's title")
        self.assertEqual(self.session.undo().snapshot.project["title"], "Alice's title")

    def test_audit_requires_explicit_registration_and_cas(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.ndjson"
            draft = self.review()
            self.workspace.apply("alice", self.lease.token, draft, {})
            self.assertFalse(path.exists())
            with self.assertRaises(TeamWorkflowError) as caught:
                self.workspace.acknowledge_without_audit("alice", self.lease.token)
            self.assertEqual(caught.exception.code, "unregistered_merge")
            self.workspace.register("alice", self.lease.token)
            self.assertFalse(path.exists())
            log = LocalAuditLog(path)
            with self.assertRaises(ValueError):
                self.workspace.append_audit("alice", self.lease.token, log,
                                            expected_head="0" * 64)
            self.assertIsNotNone(self.workspace.pending)
            event = self.workspace.append_audit("alice", self.lease.token, log,
                                                expected_head=None)
            self.assertEqual(event["operation"], "r78_merge")
            self.assertEqual(event["actor"], "alice")
            self.assertEqual(log.inspect()["count"], 1)
            self.assertIsNone(self.workspace.pending)

    def test_pending_review_and_stale_checkpoint_fail_closed(self):
        draft = self.review()
        self.workspace.apply("alice", self.lease.token, draft, {})
        with self.assertRaises(TeamWorkflowError) as caught:
            self.review()
        self.assertEqual(caught.exception.code, "pending_checkpoint")
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "title": "after merge"}, kind="r78.concurrent"))
        with self.assertRaises(TeamWorkflowError) as caught:
            self.workspace.register("alice", self.lease.token)
        self.assertEqual(caught.exception.code, "stale_merge")


if __name__ == "__main__":
    unittest.main()

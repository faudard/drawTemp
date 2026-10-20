"""R78.C: executable two-author map/quest, undo, review, audit and R15 gates."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.project_audit import LocalAuditLog
from drawtemp.sdk.r48_vertical_gate import CONFLICT
from drawtemp.sdk.r78_vertical_gate import build_editors, run_gate, _execute
from drawtemp.sdk.team_workflows import (
    TeamAccessPolicy, TeamLeaseRegistry, TeamMergeWorkspace, TeamWorkflowError,
)
from drawtemp.export.r15 import ExportError, verify_bundle


def _team():
    return TeamAccessPolicy({
        "owner": "owner", "alice": "editor", "bob": "editor",
        "chloe": "reviewer", "guest": "viewer",
    })


class TwoAuthorR78CGateTests(unittest.TestCase):
    def test_complete_vertical_map_quest_undo_replay_save_and_r15_preview(self):
        result = run_gate()
        self.assertEqual(result["result"], "passed")
        self.assertEqual(result["conflict"], CONFLICT)
        self.assertEqual(result["choice"], "incoming")
        self.assertEqual(result["nodes"], 4)
        self.assertEqual(result["notes"], 3)
        self.assertEqual(result["board_events"], 5)
        self.assertEqual(result["audit"], "aligned")
        self.assertTrue(result["undo"]["undo_restored"])
        self.assertTrue(result["undo"]["redo_restored"])
        self.assertEqual(result["gameplay"]["result"], "victory")
        self.assertEqual(result["gameplay"]["seed"], 17)
        self.assertEqual(result["export"]["preflight"], "passed")
        self.assertEqual(result["export"]["bundle_integrity"], "passed")
        self.assertEqual(result["export"]["native_runtime"], "synthetic-not-executable")
        self.assertFalse(result["release_certified"])
        self.assertFalse(result["export"]["release_certified"])
        self.assertTrue(result["export"]["strict_release_rejected"])

    def test_repeatable_authoring_hashes_without_native_fixture(self):
        first = run_gate(run_gameplay=False, run_export=False)
        second = run_gate(run_gameplay=False, run_export=False)
        self.assertEqual(first, second)
        self.assertEqual(first["gameplay"]["result"], "not_run")
        self.assertEqual(first["export"]["preflight"], "not_run")
        self.assertNotEqual(first["alice_digest"], first["bob_digest"])
        self.assertNotEqual(first["alice_digest"], first["merged_digest"])

    def test_real_collaborators_are_independent_sessions(self):
        history = build_editors()
        self.assertIsNot(history["alice_session"], history["bob_session"])
        self.assertEqual(len(history["graph"]), 3)
        self.assertNotEqual(
            history["alice_session"].snapshot().to_dict()["content"],
            history["bob_session"].snapshot().to_dict()["content"])
        self.assertEqual(
            history["root_session"].snapshot().to_dict()["revision"], 0)

    def test_lease_contestation_unresolved_conflict_and_revoke_fail_closed(self):
        history = build_editors()
        policy = _team()
        leases = TeamLeaseRegistry(policy)
        alice = leases.acquire("alice")
        with self.assertRaises(TeamWorkflowError) as busy:
            leases.acquire("bob")
        self.assertEqual(busy.exception.code, "lease_busy")
        studio = history["alice_session"]
        controller = TeamMergeWorkspace(studio, history["graph"], policy, leases)
        review = controller.preview(
            "alice", alice.token, local_id=history["alice"].node_id,
            incoming_id=history["bob"].node_id)
        initial = studio.snapshot().to_dict()
        self.assertEqual([c.path for c in review.conflicts], [CONFLICT])
        with self.assertRaises(ValueError):
            controller.apply("alice", alice.token, review, {})
        self.assertEqual(studio.snapshot().to_dict(), initial)
        policy.assign("owner", "alice", "viewer")
        with self.assertRaises(TeamWorkflowError) as denied:
            controller.apply("alice", alice.token, review, {CONFLICT: "incoming"})
        self.assertEqual(denied.exception.code, "access_denied")
        self.assertEqual(studio.snapshot().to_dict(), initial)
        self.assertEqual(len(history["graph"]), 3)

    def test_stale_local_edit_never_overwrites_or_creates_history(self):
        history = build_editors()
        policy = _team()
        leases = TeamLeaseRegistry(policy)
        lease = leases.acquire("alice")
        session = history["alice_session"]
        controller = TeamMergeWorkspace(session, history["graph"], policy, leases)
        review = controller.preview(
            "alice", lease.token, local_id=history["alice"].node_id,
            incoming_id=history["bob"].node_id)
        session.apply(session.preview_project(
            lambda project: {**project, "subtitle": "Edited during review"},
            kind="r78c-concurrent"))
        changed = session.snapshot().to_dict()
        with self.assertRaises(ValueError):
            controller.apply("alice", lease.token, review, {CONFLICT: "incoming"})
        self.assertEqual(changed, session.snapshot().to_dict())
        self.assertEqual(len(history["graph"]), 3)

    def test_expired_lease_prevents_publish(self):
        history = build_editors()
        clock = [20]
        policy = _team()
        leases = TeamLeaseRegistry(policy, clock=lambda: clock[0])
        lease = leases.acquire("alice", ttl=2)
        controller = TeamMergeWorkspace(
            history["alice_session"], history["graph"], policy, leases)
        review = controller.preview(
            "alice", lease.token, local_id=history["alice"].node_id,
            incoming_id=history["bob"].node_id)
        clock[0] += 3
        with self.assertRaises(TeamWorkflowError) as caught:
            controller.apply("alice", lease.token, review, {CONFLICT: "incoming"})
        self.assertEqual(caught.exception.code, "invalid_lease")
        self.assertEqual(len(history["graph"]), 3)

    def test_save_failure_requires_explicit_rollforward_from_merged_pair(self):
        history = build_editors()
        policy = _team()
        leases = TeamLeaseRegistry(policy)
        lease = leases.acquire("alice")
        session = history["alice_session"]
        with TemporaryDirectory(prefix="drawtemp-r78c-recover-") as folder:
            path = Path(folder) / "jeanne-team.json"
            session.save_as(path)
            controller = TeamMergeWorkspace(session, history["graph"], policy, leases)
            review = controller.preview(
                "alice", lease.token, local_id=history["alice"].node_id,
                incoming_id=history["bob"].node_id)
            result = controller.apply(
                "alice", lease.token, review, {CONFLICT: "incoming"})
            expected = result.snapshot.to_dict()
            store = session._store
            publisher = store._publish_one

            def crash_on_project(target):
                if target == store.project_path:
                    raise OSError("Injected failure after first file publication")
                return publisher(target)

            store._publish_one = crash_on_project
            with self.assertRaises(AuthoringError):
                session.save()
            self.assertTrue(store.pending)
            with self.assertRaises(AuthoringError) as failure:
                AuthoringSession.open(path)
            self.assertEqual(failure.exception.code, "recovery_required")
            self.assertTrue(store.inspect_recovery()["choices"]["complete"]["available"])
            restored = AuthoringSession.recover(path, "complete")
            saved = restored.snapshot().to_dict()
            self.assertEqual(saved["content"], expected["content"])
            self.assertEqual(saved["project"], expected["project"])
            self.assertFalse(store.pending)
            self.assertEqual(len(history["graph"]), 3)
            self.assertFalse((Path(folder) / "reviewed.audit.jsonl").exists())

    def test_export_is_integrity_checked_and_explicitly_not_a_release(self):
        with TemporaryDirectory(prefix="drawtemp-r78c-export-") as directory:
            folder = Path(directory)
            report = _execute(folder, run_gameplay=False, run_export=True)
            self.assertFalse(report["release_certified"])
            bundle = folder / "preview-bundle"
            with self.assertRaises(ExportError):
                verify_bundle(bundle, require_release=True)
            manifest = verify_bundle(bundle)
            path = bundle / manifest["content"]
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaises(ExportError):
                verify_bundle(bundle)


if __name__ == "__main__":
    unittest.main()

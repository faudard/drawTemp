"""R48.C1 integration gates: two authors, canon saves, explicit recovery and replay.

Run with: python -m unittest tests_standalone.test_drawtemp_r48c_vertical -v
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.collaboration import CollaborationError
from drawtemp.sdk.project_history_store import HistoryStoreError, LocalHistoryStore
from drawtemp.sdk.r48_vertical_gate import run_gate, _alice_pair, _bob_pair, CONFLICT
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.review_notes import ReviewNoteStore
from drawtemp.sdk.project_audit import LocalAuditLog


class TwoAuthorVerticalGateTests(unittest.TestCase):
    def test_complete_jeanne_authoring_gameplay_save_and_replay(self):
        report = run_gate()
        self.assertEqual(report["result"], "passed")
        self.assertEqual(report["conflict"], CONFLICT)
        self.assertEqual(report["nodes"], 4)
        self.assertEqual(report["notes"], 2)
        self.assertEqual(report["audit"], "aligned")
        self.assertEqual(report["gameplay"]["result"], "victory")
        self.assertEqual(report["gameplay"]["seed"], 17)
        self.assertEqual(len(report["archive_sha256"]), 64)

    def test_two_author_fingerprints_are_reproducible_without_gameplay(self):
        first = run_gate(run_gameplay=False)
        second = run_gate(run_gameplay=False)
        self.assertEqual(first, second)
        self.assertNotEqual(first["alice_digest"], first["bob_digest"])
        self.assertNotEqual(first["merged_digest"], first["alice_digest"])
        self.assertEqual(first["gameplay"]["result"], "not_run")

    def test_interrupted_paired_studio_save_requires_explicit_rollback(self):
        content, project = reference_project()
        with TemporaryDirectory(prefix="drawtemp-r48c-crash-") as directory:
            path = Path(directory) / "jeanne.json"
            session = AuthoringSession.new(content, project)
            session.save_as(path)
            original = session.snapshot().to_dict()
            pair = session.preview_pair(_alice_pair, kind="r48c-interrupted-save")
            session.apply(pair)
            store = session._store
            original_publisher = store._publish_one

            def interrupt(target):
                if target == store.project_path:
                    raise OSError("R48.C injected interruption between file replacements")
                return original_publisher(target)

            store._publish_one = interrupt
            with self.assertRaises(AuthoringError):
                session.save()
            self.assertTrue(store.pending)
            with self.assertRaises(AuthoringError) as caught:
                AuthoringSession.open(path)
            self.assertEqual(caught.exception.code, "recovery_required")
            # No implicit repair of Content/GameProject. The operator chooses
            # rollback, after verifying that the recorded sources are usable.
            info = store.inspect_recovery()
            self.assertTrue(info["choices"]["rollback"]["available"])
            self.assertTrue(info["choices"]["complete"]["available"])
            recovered = AuthoringSession.recover(path, "rollback")
            self.assertEqual(recovered.snapshot().to_dict()["content"],
                             original["content"])
            self.assertEqual(recovered.snapshot().to_dict()["project"],
                             original["project"])
            self.assertFalse(store.pending)

    def test_explicit_rollforward_recovers_both_authoring_documents(self):
        content, project = reference_project()
        with TemporaryDirectory(prefix="drawtemp-r48c-continue-") as directory:
            path = Path(directory) / "jeanne.json"
            session = AuthoringSession.new(content, project)
            session.save_as(path)
            session.apply(session.preview_pair(_bob_pair, kind="r48c-save-failure"))
            expected = session.snapshot().to_dict()
            store = session._store
            publisher = store._publish_one

            def interrupt(target):
                if target == store.project_path:
                    raise OSError("R48.C injected crash")
                return publisher(target)

            store._publish_one = interrupt
            with self.assertRaises(AuthoringError):
                session.save()
            recovered = AuthoringSession.recover(path, "complete")
            self.assertEqual(recovered.snapshot().to_dict()["content"],
                             expected["content"])
            self.assertEqual(recovered.snapshot().to_dict()["project"],
                             expected["project"])
            self.assertFalse(store.pending)

    def test_history_archive_publication_crash_preserves_last_valid_pair(self):
        content, project = reference_project()
        studio = AuthoringSession.new(content, project)
        from drawtemp.studio.r48_history_review import ProjectHistoryWorkspace
        workspace = ProjectHistoryWorkspace(studio)
        with TemporaryDirectory(prefix="drawtemp-r48c-history-") as directory:
            path = Path(directory) / "history.r48.json"
            old = workspace.save_history(path)
            archived = path.read_bytes()
            workspace.capture_live(
                parent_id=workspace.revisions()[0].node_id, author="alice",
                label="not yet saved")
            with patch("drawtemp.sdk.project_history_store.os.replace",
                       side_effect=OSError("injected crash before atomic swap")):
                with self.assertRaises(OSError):
                    workspace.save_history()
            self.assertEqual(path.read_bytes(), archived)
            self.assertEqual(LocalHistoryStore(path).inspect(), old)
            self.assertEqual(len(LocalHistoryStore(path).load()[0]), 1)
            self.assertEqual(studio.revision, 0)

    def test_invalid_recovery_inputs_never_change_existing_sidecars(self):
        content, project = reference_project()
        studio = AuthoringSession.new(content, project)
        from drawtemp.studio.r48_history_review import ProjectHistoryWorkspace
        workspace = ProjectHistoryWorkspace(studio)
        with TemporaryDirectory(prefix="drawtemp-r48c-no-overwrite-") as directory:
            folder = Path(directory)
            path = folder / "history.r48.json"
            workspace.save_history(path)
            existing = path.read_bytes()
            path.write_bytes(existing[:-3])
            corrupted = path.read_bytes()
            with self.assertRaises(HistoryStoreError):
                workspace.save_history()
            self.assertEqual(path.read_bytes(), corrupted)
            self.assertEqual(studio.snapshot().project["title"], project.title)
            self.assertFalse((folder / "review.jsonl").exists())
            self.assertFalse((folder / "audit.jsonl").exists())
            self.assertEqual(ReviewNoteStore(folder / "review.jsonl").events(), ())
            self.assertEqual(LocalAuditLog(folder / "audit.jsonl").entries(), ())


if __name__ == "__main__":
    unittest.main()

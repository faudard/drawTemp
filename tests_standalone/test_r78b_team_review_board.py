"""R78.B: two-author review notes, task journals, release boards, Qt UI."""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import make_revision
from drawtemp.sdk.project_history import RevisionGraph
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.review_notes import ReviewNoteStore
from drawtemp.sdk.team_review_board import TeamBoardError, TeamReviewBoard, TeamTaskStore
from drawtemp.sdk.team_workflows import TeamAccessPolicy, TeamWorkflowError

try:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.r78_team_review_qt import TeamReviewDialog
except ImportError:
    QApplication = None


class TeamReviewBoardTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        content, project = reference_project()
        self.original_content, self.original_project = content.to_dict(), project.to_dict()
        self.session = AuthoringSession.new(content, project)
        self.graph = RevisionGraph()
        self.root = self.graph.add(make_revision(
            self.original_content, self.original_project, author="seed"))
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "title": "Team Alice"}, kind="r78b.test"))
        live = self.session.snapshot().to_dict()
        self.local = self.graph.add(make_revision(
            live["content"], live["project"], author="alice",
            parents=(self.root.revision.digest,)),
            parents=(self.root.node_id,), label="Alice edits")
        remote = deepcopy(self.original_project)
        remote["subtitle"] = "Team Bob"
        self.incoming = self.graph.add(make_revision(
            self.original_content, remote, author="bob",
            parents=(self.root.revision.digest,)),
            parents=(self.root.node_id,), label="Bob edits")
        self.policy = TeamAccessPolicy({
            "owner": "owner", "alice": "editor", "bob": "editor",
            "chloe": "reviewer", "guest": "viewer"})
        self.notes = ReviewNoteStore(self.folder / "reviews.jsonl")
        self.tasks = TeamTaskStore(self.folder / "team.jsonl")
        self.board = TeamReviewBoard(self.graph, self.policy, self.notes, self.tasks)
        self.before = self.session.snapshot().to_dict()

    def task(self, actor="alice", **kwargs):
        return self.board.create_task(
            actor, node_id=self.local.node_id,
            path="/project/story/scenes/arrival/title",
            expected_head=self.tasks.inspect()["head"],
            title="Review arrival quest", release="12.0", assignee="chloe",
            **kwargs)

    def test_semantic_diff_and_typed_anchor(self):
        changes = self.board.differences("chloe", self.root.node_id, self.local.node_id)
        self.assertIn("/project/title", [row.path for row in changes])
        note = self.board.note("chloe", node_id=self.local.node_id,
            path="/project/story/scenes/arrival/title",
            expected_head=None, text="Review this scene")
        self.assertEqual(note["anchor"], "/project/story/scenes/arrival")
        threads = self.board.discussions("guest", self.local.node_id,
            "/project/story/scenes/arrival")
        self.assertEqual(threads[0]["comments"][0]["author"], "chloe")

    def test_comment_reply_resolve_and_restore(self):
        one = self.board.note("bob", node_id=self.local.node_id,
            path="/project/title", expected_head=None, text="Needs work")
        two = self.board.note("alice", node_id=self.local.node_id,
            path="/project/title", expected_head=one["digest"], text="I agree",
            thread=one["sequence"])
        three = self.board.note("chloe", node_id=self.local.node_id,
            path="/project/title", expected_head=two["digest"], kind="resolve",
            thread=one["sequence"])
        self.assertTrue(self.board.discussions("alice", self.local.node_id)[0]["resolved"])
        self.board.note("chloe", node_id=self.local.node_id,
            path="/project/title", expected_head=three["digest"], kind="reopen",
            thread=one["sequence"])
        self.assertFalse(self.board.discussions("alice", self.local.node_id)[0]["resolved"])
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_todo_progress_done_release_board_and_history(self):
        created = self.task()
        self.assertEqual(created["task"], 1)
        self.assertEqual(created["status"], "todo")
        progress = self.board.change_task("chloe", task_id=1,
            expected_head=created["digest"], status="in_progress")
        final = self.board.change_task("alice", task_id=1,
            expected_head=progress["digest"], status="done")
        self.assertEqual(final["status"], "done")
        self.assertEqual(len(self.tasks.events()), 3)
        self.assertEqual(len(self.board.tasks_for("guest")), 1)
        grouped = self.board.release_board("guest")
        self.assertEqual(grouped["12.0"]["done"][0]["task"], 1)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        reopened = TeamTaskStore(self.tasks.path)
        self.assertEqual(reopened.tasks()[0]["status"], "done")

    def test_advisory_review_supersedes_prior_vote_no_merge(self):
        first = self.board.review("chloe", node_id=self.local.node_id,
            path="/project/title", expected_head=None,
            decision="changes_requested", summary="Clarify title")
        second = self.board.review("chloe", node_id=self.local.node_id,
            path="/project/title", expected_head=first["digest"],
            decision="approved", summary="Updated")
        latest = self.board.decisions("guest", node_id=self.local.node_id)
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["status"], "approved")
        self.assertEqual(latest[0]["sequence"], second["sequence"])
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        self.assertFalse(self.session.storage_status()["has_destination"])

    def test_permissions_and_revocation(self):
        with self.assertRaises(TeamWorkflowError) as caught:
            self.board.create_task("guest", node_id=self.local.node_id,
                path="/project/title", expected_head=None, title="Denied")
        self.assertEqual(caught.exception.code, "access_denied")
        with self.assertRaises(TeamWorkflowError):
            self.board.review("guest", node_id=self.local.node_id,
                path="/project/title", expected_head=None,
                decision="approved", summary="Not permitted")
        self.task()
        with self.assertRaises(TeamWorkflowError):
            self.board.change_task("chloe", task_id=1,
                expected_head=self.tasks.inspect()["head"], release="13.0")
        self.policy.assign("owner", "chloe", "viewer")
        with self.assertRaises(TeamWorkflowError):
            self.board.change_task("chloe", task_id=1,
                expected_head=self.tasks.inspect()["head"], status="done")
        self.assertEqual(self.tasks.inspect()["count"], 1)

    def test_concurrent_author_cas_requires_refresh(self):
        head = self.tasks.inspect()["head"]
        first = self.task(actor="alice")
        with self.assertRaises(TeamBoardError) as caught:
            self.board.create_task("bob", node_id=self.incoming.node_id,
                path="/project", expected_head=head, title="Concurrent")
        self.assertEqual(caught.exception.code, "stale_head")
        second = self.board.create_task("bob", node_id=self.incoming.node_id,
            path="/project", expected_head=first["digest"], title="Concurrent")
        self.assertEqual(second["task"], 2)
        self.assertEqual(len(self.board.tasks_for("owner")), 2)

    def test_anchor_refuses_missing_entities_and_invalid_assignee(self):
        with self.assertRaises(ValueError):
            self.board.create_task("alice", node_id=self.local.node_id,
                path="/project/story/scenes/missing/name",
                expected_head=None, title="Bad")
        with self.assertRaises(TeamWorkflowError):
            self.board.create_task("alice", node_id=self.local.node_id,
                path="/project", expected_head=None, title="Bad",
                assignee="unknown")
        self.assertFalse(self.tasks.path.exists())

    def test_modified_and_torn_journals_fail_closed(self):
        self.task()
        good = self.tasks.path.read_bytes()
        self.tasks.path.write_bytes(good.replace(b'"status":"todo"', b'"status":"done"'))
        with self.assertRaises(TeamBoardError) as caught:
            self.board.tasks_for("alice")
        self.assertEqual(caught.exception.code, "invalid_event")
        self.tasks.path.write_bytes(good[:-1])
        with self.assertRaises(TeamBoardError) as caught:
            self.tasks.inspect()
        self.assertEqual(caught.exception.code, "torn_record")

    def test_task_cannot_move_between_revision_entities(self):
        self.task()
        before = self.tasks.path.read_bytes()
        with self.assertRaises(TeamBoardError):
            self.tasks.append(
                expected_head=self.tasks.inspect()["head"],
                kind="update", node=self.incoming, anchor="/project",
                actor="alice", title="Move", status="done", task=1)
        self.assertEqual(self.tasks.path.read_bytes(), before)

    def test_same_file_for_notes_and_tasks_is_refused(self):
        with self.assertRaises(TeamBoardError) as caught:
            TeamReviewBoard(self.graph, self.policy,
                            ReviewNoteStore(self.tasks.path), self.tasks)
        self.assertEqual(caught.exception.code, "same_journal")


@unittest.skipIf(QApplication is None, "PySide6 optional; CI Qt matrix runs with qt6")
class TeamReviewQtTests(TeamReviewBoardTests):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["r78b-offscreen"])

    def setUp(self):
        super().setUp()
        self.dialog = TeamReviewDialog(
            self.session, graph=self.graph, actor="alice", policy=self.policy)
        self.addCleanup(self.dialog.close)

    def test_offscreen_diff_comment_task_vote_and_no_game_mutation(self):
        self.assertTrue(self.dialog.use_directory(self.folder))
        self.dialog.local_combo.setCurrentIndex(
            self.dialog.local_combo.findData(self.root.node_id))
        self.dialog.incoming_combo.setCurrentIndex(
            self.dialog.incoming_combo.findData(self.local.node_id))
        changes = self.dialog.compare()
        self.assertTrue(changes)
        self.dialog.path_edit.setText("/project/title")
        self.dialog.note_text.setPlainText("Looks good?")
        self.assertIsNotNone(self.dialog.post_note())
        self.dialog.review_summary.setText("Please improve readability")
        self.assertIsNotNone(self.dialog.post_review())
        self.dialog.task_title.setText("Adjust title")
        self.dialog.task_assignee.setText("chloe")
        self.dialog.task_release.setText("12.0")
        created = self.dialog.create_task()
        self.assertIsNotNone(created)
        self.assertEqual(self.dialog.tasks_table.rowCount(), 1)
        self.dialog.tasks_table.selectRow(0)
        self.dialog.task_state.setCurrentIndex(1)
        self.assertIsNotNone(self.dialog.update_task())
        self.assertEqual(self.dialog.tasks_table.item(0, 3).text(), "in_progress")
        self.assertEqual(self.session.snapshot().to_dict(), self.before)

    def test_readonly_reviewer_controls_and_explicit_journal(self):
        guest_dialog = TeamReviewDialog(
            self.session, graph=self.graph, actor="guest", policy=self.policy)
        self.addCleanup(guest_dialog.close)
        self.assertFalse(guest_dialog.note_button.isEnabled())
        self.assertFalse(guest_dialog.review_button.isEnabled())
        self.assertFalse(guest_dialog.task_button.isEnabled())
        self.assertFalse(guest_dialog.task_update_button.isEnabled())
        self.assertFalse(self.dialog.board)
        self.assertFalse((self.folder / "r78_team_board.jsonl").exists())


if __name__ == "__main__":
    unittest.main()

"""R48.B2: stable resource review notes, integrity gates and Qt offscreen UX."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.review_notes import (
    ReviewNoteError, ReviewNoteStore, anchor_from_path, validate_anchor,
)
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r48_history_review import ProjectHistoryWorkspace

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.r48_history_qt import ProjectHistoryDialog
except ImportError:
    QApplication = None


class ReviewNotesTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "reviews.jsonl"
        self.store = ReviewNoteStore(self.path)
        self.session = AuthoringSession.new(*reference_project())
        self.workspace = ProjectHistoryWorkspace(self.session)
        self.root = self.workspace.revisions()[0]
        self.original = self.session.snapshot().to_dict()

    def append(self, anchor="/project", text="Review project title",
               *, node=None, head=None, thread=0, kind="comment"):
        return self.store.append(
            node or self.root,
            expected_head=self.store.inspect()["head"] if head is None else head,
            anchor=anchor, author="alice", text=text, kind=kind, thread=thread)

    def test_semantic_paths_map_to_resource_ids(self):
        pairs = {
            "/project/story/scenes/arrival/title": "/project/story/scenes/arrival",
            "/project/campaigns/main/title": "/project/campaigns/main",
            "/content/missions/r0_village_forest/units": "/content/missions/r0_village_forest",
            "/project/cinematics/intro/name": "/project/cinematics/intro",
            "/project/title": "/project",
            "/content/metadata/name": "/content",
        }
        for path, anchor in pairs.items():
            self.assertEqual(anchor_from_path(path), anchor)
        for invalid in ("", "/unknown/title", "/project/story/scenes/!bad/title"):
            with self.assertRaises(ReviewNoteError):
                anchor_from_path(invalid)

    def test_validated_scene_anchor_and_unknown_id_fail_closed(self):
        anchor = "/project/story/scenes/arrival"
        validate_anchor(self.root, anchor)
        event = self.append(anchor, "Titre à revoir")
        self.assertEqual(event["anchor"], anchor)
        before = self.path.read_bytes()
        with self.assertRaises(ReviewNoteError) as caught:
            self.append("/project/story/scenes/does-not-exist", "Wrong")
        self.assertEqual(caught.exception.code, "unknown_resource")
        self.assertEqual(self.path.read_bytes(), before)

    def test_reply_resolve_reopen_and_persistence(self):
        first = self.append()
        head = first["digest"]
        second = self.append(text="Je propose un autre nom", thread=1, head=head)
        third = self.append(text="", kind="resolve", thread=1, head=second["digest"])
        self.assertEqual(third["previous"], second["digest"])
        store = ReviewNoteStore(self.path)
        threads = store.threads(node_id=self.root.node_id, anchor="/project")
        self.assertEqual(len(threads), 1)
        self.assertEqual(len(threads[0]["comments"]), 2)
        self.assertTrue(threads[0]["resolved"])
        store.append(self.root, expected_head=third["digest"], anchor="/project",
                     author="bob", kind="reopen", thread=1)
        self.assertFalse(store.threads()[0]["resolved"])
        self.assertEqual(self.store.inspect()["count"], 4)
        self.assertEqual(self.session.snapshot().to_dict(), self.original)

    def test_other_resource_thread_is_not_reusable(self):
        first = self.append(anchor="/project/story/scenes/arrival", text="Hi")
        before = self.path.read_bytes()
        with self.assertRaises(ReviewNoteError) as caught:
            self.append(anchor="/project", text="Reply elsewhere", thread=first["sequence"])
        self.assertEqual(caught.exception.code, "invalid_thread")
        self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(ReviewNoteError) as caught:
            self.append(anchor="/project", text="", kind="resolve", thread=0)
        self.assertEqual(caught.exception.code, "invalid_input")

    def test_stale_head_prevents_concurrent_overwrite(self):
        observed = self.store.inspect()["head"]
        first = self.append()
        before = self.path.read_bytes()
        with self.assertRaises(ReviewNoteError) as caught:
            self.store.append(self.root, expected_head=observed, anchor="/project",
                              author="bob", text="Stale append")
        self.assertEqual(caught.exception.code, "stale_head")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.store.inspect()["head"], first["digest"])

    def test_tamper_and_torn_record_fail_without_repair(self):
        self.append()
        changed = self.path.read_bytes().replace(b'"author":"alice"', b'"author":"admin"')
        self.path.write_bytes(changed)
        with self.assertRaises(ReviewNoteError):
            self.store.inspect()
        with self.assertRaises(ReviewNoteError):
            self.append(text="Should fail")
        self.assertEqual(self.path.read_bytes(), changed)
        self.path.write_bytes(b'{"partial":')
        with self.assertRaises(ReviewNoteError) as caught:
            self.store.inspect()
        self.assertEqual(caught.exception.code, "torn_record")

    def test_reply_cannot_cross_revision_even_if_content_identical(self):
        first = self.append()
        same = self.workspace.capture_live(
            parent_id=self.root.node_id, author="alice", label="child")
        self.assertEqual(same.revision.digest, self.root.revision.digest)
        with self.assertRaises(ReviewNoteError) as caught:
            self.store.append(same, expected_head=first["digest"],
                              anchor="/project", author="bob",
                              text="Cross-revision reply", thread=1)
        self.assertEqual(caught.exception.code, "invalid_thread")
        self.assertEqual(len(self.store.threads()), 1)

    def test_plaintext_and_invalid_ids_not_silently_migrated(self):
        self.append(anchor="/project/story/scenes/arrival", text="Old scene discussion")
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "title": "New title"}))
        child = self.workspace.capture_live(
            parent_id=self.root.node_id, author="alice", label="renamed")
        self.assertEqual(self.store.threads(node_id=child.node_id), ())
        self.assertEqual(len(self.store.threads(node_id=self.root.node_id)), 1)

    def test_forged_revision_node_and_dangling_anchor_refused(self):
        forged = replace(self.root, node_id="0" * 64)
        with self.assertRaises(ReviewNoteError) as caught:
            self.store.append(forged, expected_head=None, anchor="/project",
                              author="alice", text="Fake")
        self.assertEqual(caught.exception.code, "invalid_node")
        with self.assertRaises(ReviewNoteError) as caught:
            self.store.append(self.root, expected_head=None,
                              anchor="/project/story/scenes/unknown",
                              author="alice", text="Dangling")
        self.assertEqual(caught.exception.code, "unknown_resource")
        self.assertFalse(self.path.exists())
        self.assertEqual(self.session.snapshot().to_dict(), self.original)

    def test_reject_unsupported_or_script_like_anchor_without_writing(self):
        with self.assertRaises(ReviewNoteError):
            self.store.append(self.root, expected_head=None,
                              anchor="/project/../../another",
                              author="alice", text="Never accept a path traversal")
        self.assertFalse(self.path.exists())

    def test_untrusted_json_duplicate_keys_rejected(self):
        self.append()
        raw = self.path.read_text(encoding="utf-8")
        self.path.write_text(raw.replace('"author":"alice"', '"author":"alice","author":"bob"'),
                             encoding="utf-8")
        with self.assertRaises(ReviewNoteError) as caught:
            self.store.inspect()
        self.assertEqual(caught.exception.code, "duplicate_field")


@unittest.skipIf(QApplication is None, "PySide6 optional")
class ReviewNotesQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["r48-b2-offscreen"])

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "comments.jsonl"
        self.session = AuthoringSession.new(*reference_project())
        self.dialog = ProjectHistoryDialog(self.session)
        self.addCleanup(self.dialog.close)
        self.root = self.dialog.workspace.revisions()[0]
        self.initial = self.session.snapshot().to_dict()

    def review_title(self):
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "title": "Alice"}))
        local = self.dialog.capture_live()
        index = self.dialog.local_combo.findData(local.node_id)
        self.dialog.local_combo.setCurrentIndex(index)
        # An independent branch is captured from the original valid pair.
        content, project = reference_project()
        from drawtemp.sdk.collaboration import make_revision
        remote = make_revision(content, {**project.to_dict(), "title": "Bob"},
                               author="bob", parents=(self.root.revision.digest,))
        node = self.dialog.workspace.graph.add(
            remote, parents=(self.root.node_id,), label="B")
        self.dialog._populate_history(selected_local=local.node_id,
                                      selected_incoming=node.node_id)
        preview = self.dialog.compare_selected()
        self.assertIsNotNone(preview)
        self.dialog.review_table.selectRow(self.dialog.review_table.rowCount() - 1)
        self.assertEqual(self.dialog.note_anchor_edit.text(), "/project")
        return local, node

    def test_post_reply_resolve_no_implicit_merge(self):
        local, incoming = self.review_title()
        self.assertTrue(self.dialog.load_notes(self.path))
        self.assertEqual(self.dialog.note_revision_combo.currentData(), incoming.node_id)
        self.dialog.note_text.setPlainText("Need to clarify title")
        self.assertTrue(self.dialog.post_note_button.isEnabled())
        note = self.dialog.post_note()
        self.assertEqual(note["sequence"], 1)
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.dialog.notes_table.rowCount(), 1)
        self.dialog.note_thread_combo.setCurrentIndex(1)
        self.dialog.note_text.setPlainText("I can revise it")
        reply = self.dialog.post_note()
        self.assertEqual(reply["thread"], 1)
        self.assertTrue(self.dialog.resolve_note_button.isEnabled())
        self.assertEqual(self.dialog.toggle_note()["kind"], "resolve")
        self.assertIn("Résolu", self.dialog.notes_table.item(0, 3).text())
        self.assertEqual(self.session.snapshot().project["title"], "Alice")
        self.assertTrue(self.path.is_file())
        # Offscreen Dialog has not persisted any of the game documents.
        self.assertEqual(self.session.snapshot().revision, 1)

    def test_keyboard_shortcut_and_explicit_reload_after_external_write(self):
        _, incoming = self.review_title()
        self.assertTrue(self.dialog.load_notes(self.path))
        self.dialog.note_text.setPlainText("Review keyboard")
        self.dialog.show()
        self.dialog.note_text.setFocus()
        QTest.keyClick(self.dialog.note_text, Qt.Key_Return, Qt.ControlModifier)
        self.assertEqual(self.dialog.notes_table.rowCount(), 1)
        old_head = self.dialog._notes_head
        ReviewNoteStore(self.path).append(
            self.dialog.workspace.graph.node(incoming.node_id),
            expected_head=old_head, anchor="/project", author="bob",
            text="Written elsewhere")
        self.dialog.note_text.setPlainText("Cannot overwrite")
        self.assertIsNone(self.dialog.post_note())
        self.assertIn("Publication refusée", self.dialog.notes_status.text())
        self.dialog.refresh_notes()
        self.assertEqual(self.dialog.notes_table.rowCount(), 2)
        self.assertIsNotNone(self.dialog.post_note())

    def test_no_notes_without_an_actual_diff_selection(self):
        self.assertTrue(self.dialog.load_notes(self.path))
        self.dialog.note_text.setPlainText("Too early")
        self.assertFalse(self.dialog.post_note_button.isEnabled())
        self.assertIsNone(self.dialog.post_note())
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()

"""R48.B: headless workspace and real Qt Widgets offscreen review gates.

Offscreen exercises signals, widgets and the shared AuthoringSession only.
This is NOT on-screen/manual accessibility or GPU certification.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import CollaborationError
from drawtemp.sdk.project_audit import LocalAuditLog
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r48_history_review import ProjectHistoryWorkspace

try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.r48_history_qt import ProjectHistoryDialog
except ImportError:
    QApplication = None


class HistoryWorkspaceTests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.content, self.project = content, project
        self.session = AuthoringSession.new(content, project)
        self.original = self.session.snapshot().to_dict()
        self.workspace = ProjectHistoryWorkspace(self.session)
        self.root = self.workspace.revisions()[0]

    def test_bootstrap_is_readonly_and_requires_explicit_parent(self):
        self.assertEqual(self.session.snapshot().to_dict(), self.original)
        self.assertEqual(len(self.workspace.revisions()), 1)
        with self.assertRaises(CollaborationError) as caught:
            self.workspace.capture_live(parent_id=None)
        self.assertEqual(caught.exception.code, "missing_parent")
        self.assertEqual(len(self.workspace.revisions()), 1)
        self.assertEqual(self.session.snapshot().to_dict(), self.original)

    def test_file_import_and_review_reuse_same_r1_undo(self):
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "title": "Alice"}))
        alice = self.workspace.capture_live(
            parent_id=self.root.node_id, author="alice", label="A")
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "incoming/content.json"
            source.parent.mkdir()
            remote = AuthoringSession.new(self.content, self.project)
            remote.apply(remote.preview_project(
                lambda p: {**p, "subtitle": "Bob"}))
            remote.save_as(source)
            before_bytes = source.read_bytes()
            bob = self.workspace.import_pair(
                source, parent_id=self.root.node_id, author="bob", label="B")
            self.assertEqual(len(self.workspace.revisions()), 3)
            review = self.workspace.compare(alice.node_id, bob.node_id)
            self.assertTrue(review.can_apply)
            result = self.workspace.apply({})
            self.assertEqual(result.snapshot.project["title"], "Alice")
            self.assertEqual(result.snapshot.project["subtitle"], "Bob")
            self.assertEqual(source.read_bytes(), before_bytes)
            self.assertEqual(self.session.undo().snapshot.project["subtitle"],
                             self.original["project"]["subtitle"])

    def test_import_bad_pair_never_changes_editor_or_graph(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "content.json"
            source.write_text('{"broken":true}', encoding="utf-8")
            with self.assertRaises((ValueError, OSError)):
                self.workspace.import_pair(
                    source, parent_id=self.root.node_id,
                    author="bob", label="corrupt")
        self.assertEqual(len(self.workspace.revisions()), 1)
        self.assertEqual(self.session.snapshot().to_dict(), self.original)

    def test_stale_review_and_duplicate_history_are_fail_closed(self):
        local = self.workspace.capture_live(
            parent_id=self.root.node_id, author="alice", label="unchanged")
        with self.assertRaises(CollaborationError) as caught:
            self.workspace.capture_live(
                parent_id=self.root.node_id, author="alice", label="unchanged")
        self.assertEqual(caught.exception.code, "duplicate_revision")
        data = deepcopy(self.original["project"])
        data["title"] = "Bob"
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "copy/content.json"
            source.parent.mkdir()
            other = AuthoringSession.new(self.content, data)
            other.save_as(source)
            remote = self.workspace.import_pair(
                source, parent_id=self.root.node_id, author="bob", label="B")
            self.workspace.compare(local.node_id, remote.node_id)
            self.session.apply(self.session.preview_project(
                lambda p: {**p, "subtitle": "New live edit"}))
            before = self.session.snapshot().to_dict()
            with self.assertRaises(CollaborationError) as caught:
                self.workspace.apply({})
            self.assertEqual(caught.exception.code, "stale_local")
            self.assertEqual(self.session.snapshot().to_dict(), before)


@unittest.skipIf(QApplication is None, "PySide6 optional")
class HistoryDialogQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["r48-history-offscreen"])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.rootdir = Path(self.temp.name)
        self.content, self.project = reference_project()
        self.session = AuthoringSession.new(self.content, self.project)
        self.dialog = ProjectHistoryDialog(self.session)
        self.addCleanup(self.dialog.close)
        self.root = self.dialog.workspace.revisions()[0]

    def select(self, combo, node):
        i = combo.findData(node.node_id)
        self.assertGreaterEqual(i, 0)
        combo.setCurrentIndex(i)

    def remote_pair(self, title=None, subtitle=None):
        source = self.rootdir / "incoming" / "content.json"
        source.parent.mkdir(exist_ok=True)
        remote = AuthoringSession.new(self.content, self.project)
        def edit(p):
            result = dict(p)
            if title is not None:
                result["title"] = title
            if subtitle is not None:
                result["subtitle"] = subtitle
            return result
        remote.apply(remote.preview_project(edit))
        remote.save_as(source)
        return source

    def test_disabled_until_preview_and_disjoint_merge_undo(self):
        self.assertEqual(self.dialog.history_table.rowCount(), 1)
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "title": "Alice"}))
        local = self.dialog.capture_live()
        self.assertIsNotNone(local)
        self.select(self.dialog.parent_combo, self.root)
        remote_path = self.remote_pair(subtitle="Bob")
        before_bytes = remote_path.read_bytes()
        incoming = self.dialog.import_pair(remote_path)
        self.assertIsNotNone(incoming)
        self.select(self.dialog.local_combo, local)
        self.select(self.dialog.incoming_combo, incoming)
        preview = self.dialog.compare_selected()
        self.assertEqual(preview.conflicts, ())
        self.assertTrue(self.dialog.apply_button.isEnabled())
        transition = self.dialog.apply_review()
        self.assertEqual(transition.snapshot.project["title"], "Alice")
        self.assertEqual(transition.snapshot.project["subtitle"], "Bob")
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.session.undo().snapshot.project["subtitle"],
                         self.project.to_dict()["subtitle"])
        self.assertEqual(remote_path.read_bytes(), before_bytes)

    def test_manual_conflict_is_required_and_selection_invalidates(self):
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "title": "Alice"}))
        local = self.dialog.capture_live()
        incoming = self.dialog.import_pair(self.remote_pair(title="Bob"))
        self.select(self.dialog.local_combo, local)
        self.select(self.dialog.incoming_combo, incoming)
        preview = self.dialog.compare_selected()
        self.assertEqual([r.path for r in preview.conflicts], ["/project/title"])
        self.assertFalse(self.dialog.apply_button.isEnabled())
        selector = self.dialog.review_table.cellWidget(
            self.dialog.review_table.rowCount() - 1, 5)
        self.assertIsNone(selector.currentData())
        selector.setCurrentIndex(selector.findData("incoming"))
        self.assertTrue(self.dialog.apply_button.isEnabled())
        self.select(self.dialog.local_combo, self.root)
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.dialog.review_table.rowCount(), 0)
        self.select(self.dialog.local_combo, local)
        self.dialog.compare_selected()
        selector = self.dialog.review_table.cellWidget(
            self.dialog.review_table.rowCount() - 1, 5)
        selector.setCurrentIndex(selector.findData("incoming"))
        self.assertEqual(self.dialog.apply_review().snapshot.project["title"], "Bob")
        self.assertEqual(self.session.undo().snapshot.project["title"], "Alice")

    def test_stale_session_rejected_without_autosave(self):
        incoming = self.dialog.import_pair(self.remote_pair(subtitle="Bob"))
        self.select(self.dialog.local_combo, self.root)
        self.select(self.dialog.incoming_combo, incoming)
        self.assertIsNotNone(self.dialog.compare_selected())
        self.assertTrue(self.dialog.apply_button.isEnabled())
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "title": "Locally edited after review"}))
        before = self.session.snapshot().to_dict()
        self.assertIsNone(self.dialog.apply_review())
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_audit_is_readonly_and_head_is_pinned(self):
        path = self.rootdir / "audit.jsonl"
        log = LocalAuditLog(path)
        digest = self.root.revision.digest
        log.append(expected_head=None, actor="alice", operation="test",
                   resource="root", before=digest, after=digest)
        before = path.read_bytes()
        self.assertTrue(self.dialog.load_audit(path))
        report = self.dialog.check_audit()
        self.assertEqual(report.state, "aligned")
        self.assertEqual(path.read_bytes(), before)
        log.append(expected_head=log.inspect()["head"], actor="bob",
                   operation="test", resource="root",
                   before=digest, after=digest)
        self.assertIsNone(self.dialog.check_audit())
        self.assertIn("Audit non vérifiable", self.dialog.audit_status.text())

    def test_studio_menu_exposes_r48_action(self):
        from drawtemp.studio.qt_shell import StudioWindow
        settings = QSettings(str(self.rootdir / "settings.ini"), QSettings.IniFormat)
        window = StudioWindow(self.session, settings=settings)
        self.addCleanup(window.close)
        self.assertIn("r48_history", window.commands)
        self.assertTrue(window.commands["r48_history"].isEnabled())


if __name__ == "__main__":
    unittest.main()

"""R30.D Qt Git review with actual commits (offscreen, no GUI certification)."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from drawtemp.studio.r30_creator_qt import R30CreatorDialog
except ImportError:
    QApplication = None

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project


@unittest.skipUnless(QApplication is not None and shutil.which("git"),
                     "Qt6 + Git required")
class R30GitQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["r30-git-qt-offscreen"])

    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "repo"
        self.root.mkdir()
        self.file = self.root / "content/game.json"
        self.file.parent.mkdir()
        content, project = reference_project()
        AuthoringSession.new(content, project).save_as(self.file)
        self.git("init", "-q")
        self.git("config", "user.name", "DrawTemp R30")
        self.git("config", "user.email", "r30@example.invalid")
        self.git("add", "content/game.json", "content/game.game.json")
        self.git("commit", "-qm", "base")
        self.git("tag", "base")
        self.session = AuthoringSession.open(self.file)
        self.dialog = R30CreatorDialog(self.session, content_path=self.file)
        self.addCleanup(self.dialog.close)

    def git(self, *args):
        result = subprocess.run(["git", *args], cwd=self.root,
                                capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_git_tab_reuses_conflict_controls_and_no_git_writes(self):
        remote = AuthoringSession.open(self.file)
        remote.apply(remote.preview_project(
            lambda project: {**project, "title": "Git title"}))
        remote.save()
        self.git("add", "content/game.json", "content/game.game.json")
        self.git("commit", "-qm", "git incoming")
        # Active Studio is still the original base session, with a local edit.
        self.session.apply(self.session.preview_project(
            lambda project: {**project, "title": "Uncommitted editor title"}))
        before_git = self.git("rev-parse", "HEAD")
        before_file = self.file.read_bytes()
        preview = self.dialog.compare_git_refs("base", "HEAD")
        self.assertEqual(len(preview.conflicts), 1)
        self.assertEqual(self.dialog.tabs.currentIndex(), 1)
        self.assertFalse(self.dialog.merge_apply_button.isEnabled())
        self.assertIn(before_git[:12], self.dialog.git_status.text())
        row = self.dialog.merge_table.rowCount() - 1
        decision = self.dialog.merge_table.cellWidget(row, 5)
        decision.setCurrentIndex(2)
        self.assertTrue(self.dialog.merge_apply_button.isEnabled())
        after = self.dialog.apply_merge()
        self.assertEqual(after.snapshot.project["title"], "Git title")
        self.assertEqual(self.session.undo().snapshot.project["title"],
                         "Uncommitted editor title")
        self.assertEqual(self.git("rev-parse", "HEAD"), before_git)
        self.assertEqual(self.file.read_bytes(), before_file)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_dialog_invalid_git_ref_is_fail_closed(self):
        self.dialog.git_base_ref.setText("--bad")
        self.dialog.git_incoming_ref.setText("HEAD")
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
            self.assertIsNone(self.dialog.compare_git_refs("--bad", "HEAD"))
        self.assertFalse(self.dialog.merge_apply_button.isEnabled())
        self.assertIsNone(self.dialog.git_controller._review)


if __name__ == "__main__":
    unittest.main()

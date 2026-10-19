"""R30.C Qt offscreen interactive gates; not GPU or human UX certification."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

try:
    from PySide6.QtCore import Qt, QSettings
    from PySide6.QtWidgets import QApplication, QMessageBox
    from drawtemp.studio.r30_creator_qt import R30CreatorDialog
except ImportError:
    QApplication = None

from drawtemp.export.creator_packs import build_pack
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from tests_standalone.test_drawtemp_r30b_pack_import import _manifest, _png


@unittest.skipIf(QApplication is None, "PySide6 optional")
class R30CreatorQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["drawtemp-r30c-test"])

    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.content, self.project = reference_project()
        self.source = self.root / "game/game.json"
        self.source.parent.mkdir()
        AuthoringSession.new(self.content, self.project).save_as(self.source)
        self.session = AuthoringSession.open(self.source)
        self.dialog = R30CreatorDialog(self.session, content_path=self.source)
        self.addCleanup(self.dialog.close)

    def test_pack_review_buttons_disabled_until_explicit_preview(self):
        pack_source = self.root / "pack-source"
        (pack_source / "terrain").mkdir(parents=True)
        data = _png()
        (pack_source / "terrain/grass.png").write_bytes(data)
        pack = build_pack(pack_source, self.root / "assets.zip", _manifest(data))
        self.assertTrue(self.dialog.load_pack(pack))
        self.assertEqual(self.dialog.pack_table.rowCount(), 1)
        self.assertFalse(self.dialog.pack_publish_button.isEnabled())
        checkbox = self.dialog.pack_table.item(0, 0)
        checkbox.setCheckState(Qt.Checked)
        self.assertFalse(self.dialog.pack_publish_button.isEnabled())
        preview = self.dialog.preview_pack()
        self.assertEqual(preview.selections[0].asset_id, "art-pack.grass")
        self.assertTrue(self.dialog.pack_publish_button.isEnabled())
        self.dialog.pack_table.cellWidget(0, 3).setText("renamed")
        self.assertFalse(self.dialog.pack_publish_button.isEnabled())
        self.assertIsNone(self.dialog.publish_pack(self.root / "no-preview"))
        self.assertFalse((self.root / "no-preview").exists())
        preview = self.dialog.preview_pack()
        self.assertEqual(preview.selections[0].asset_id, "art-pack.renamed")
        published = self.dialog.publish_pack(self.root / "new-copy")
        self.assertEqual(published, self.root / "new-copy")
        self.assertTrue((published / "game.game.json").is_file())
        self.assertFalse(self.dialog.pack_publish_button.isEnabled())
        self.assertTrue(self.source.is_file())
        self.assertFalse((published / "asset-licenses.json").exists())

    def test_semantic_conflict_requires_selection_then_supports_undo(self):
        base = self.root / "base/game.json"
        incoming = self.root / "incoming/game.json"
        base.parent.mkdir()
        incoming.parent.mkdir()
        AuthoringSession.new(self.content, self.project).save_as(base)
        remote = AuthoringSession.new(self.content, self.project)
        remote.apply(remote.preview_project(
            lambda project: {**project, "title": "Incoming title"}))
        remote.save_as(incoming)
        self.session.apply(self.session.preview_project(
            lambda project: {**project, "title": "Local title"}))
        review = self.dialog.compare_paths(base, incoming)
        self.assertEqual(len(review.conflicts), 1)
        self.assertFalse(self.dialog.merge_apply_button.isEnabled())
        row = self.dialog.merge_table.rowCount() - 1
        picker = self.dialog.merge_table.cellWidget(row, 5)
        self.assertEqual(picker.currentData(), None)
        picker.setCurrentIndex(2)
        self.assertTrue(self.dialog.merge_apply_button.isEnabled())
        transition = self.dialog.apply_merge()
        self.assertEqual(transition.snapshot.project["title"], "Incoming title")
        self.assertFalse(self.dialog.merge_apply_button.isEnabled())
        self.assertEqual(self.session.undo().snapshot.project["title"], "Local title")
        # UI merge does not autosave the current Studio source.
        self.assertNotEqual(AuthoringSession.open(self.source).snapshot().project["title"],
                            "Incoming title")

    def test_external_change_and_stale_preview_block_application(self):
        base = self.root / "base/game.json"
        incoming = self.root / "incoming/game.json"
        base.parent.mkdir()
        incoming.parent.mkdir()
        AuthoringSession.new(self.content, self.project).save_as(base)
        remote = AuthoringSession.new(self.content, self.project)
        remote.apply(remote.preview_project(
            lambda project: {**project, "subtitle": "Changed remotely"}))
        remote.save_as(incoming)
        preview = self.dialog.compare_paths(base, incoming)
        self.assertTrue(preview.can_apply)
        self.assertTrue(self.dialog.merge_apply_button.isEnabled())
        incoming.write_bytes(incoming.read_bytes() + b" ")
        before = self.session.snapshot().to_dict()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
            self.assertIsNone(self.dialog.apply_merge())
        self.assertEqual(self.session.snapshot().to_dict(), before)
        self.assertFalse(self.dialog.merge_apply_button.isEnabled())

    def test_studio_has_creator_tool_on_same_editor(self):
        from drawtemp.studio.qt_shell import StudioWindow
        settings = QSettings(str(self.root / "settings.ini"), QSettings.IniFormat)
        window = StudioWindow(self.session, content_path=self.source,
                              settings=settings)
        self.addCleanup(window.close)
        self.assertIn("r30_creator", window.commands)
        self.assertTrue(window.commands["r30_creator"].isEnabled())


if __name__ == "__main__":
    unittest.main()

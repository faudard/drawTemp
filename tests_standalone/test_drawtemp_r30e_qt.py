"""R30.E Qt offscreen gallery user interactions, transaction and Undo checks."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

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


@unittest.skipIf(QApplication is None, "PySide6 is optional")
class GalleryQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["drawtemp-r30e-offscreen"])

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        content, project = reference_project()
        self.source = self.root / "game.json"
        AuthoringSession.new(content, project).save_as(self.source)
        self.session = AuthoringSession.open(self.source)
        self.dialog = R30CreatorDialog(self.session, content_path=self.source)
        self.addCleanup(self.dialog.close)

    def test_four_genres_visible_and_not_presented_as_playable(self):
        self.assertEqual(self.dialog.gallery_table.rowCount(), 4)
        self.assertEqual(self.dialog.tabs.count(), 4)
        self.assertFalse(self.dialog.gallery_apply_button.isEnabled())
        self.assertIn("narrative", self.dialog.gallery_status.text().lower())
        self.dialog.gallery_filter.setCurrentIndex(2)
        shown = [index for index in range(4)
                 if not self.dialog.gallery_table.isRowHidden(index)]
        self.assertEqual(shown, [1])
        self.assertFalse(self.dialog.gallery_preview_button.isEnabled())
        self.dialog.gallery_table.selectRow(1)
        self.assertTrue(self.dialog.gallery_preview_button.isEnabled())
        self.assertIn("narratif", self.dialog.gallery_description.text().lower())
        self.assertIn("La fontaine", self.dialog.gallery_dialogues.toPlainText())

    def test_preview_explicit_apply_undo_and_no_implicit_save(self):
        self.dialog.gallery_table.selectRow(2)
        self.dialog.gallery_namespace.setText("demo")
        before = self.source.with_name("game.game.json").read_bytes()
        review = self.dialog.preview_gallery()
        self.assertEqual(review.template_id, "inn")
        self.assertFalse(review.to_dict()["playable_genre_certified"])
        self.assertTrue(self.dialog.gallery_apply_button.isEnabled())
        self.assertEqual(before, self.source.with_name("game.game.json").read_bytes())
        self.dialog.gallery_namespace.setText("renamed")
        self.assertFalse(self.dialog.gallery_apply_button.isEnabled())
        self.assertIsNone(self.dialog.apply_gallery())
        review = self.dialog.preview_gallery()
        self.assertEqual(review.namespace, "renamed")
        after = self.dialog.apply_gallery()
        self.assertTrue(any(scene["id"] == review.scene_ids[0]
                            for scene in after.snapshot.to_dict()["project"]["story"]["scenes"]))
        self.assertFalse(self.dialog.gallery_apply_button.isEnabled())
        self.assertEqual(before, self.source.with_name("game.game.json").read_bytes())
        undone = self.session.undo()
        self.assertEqual(undone.snapshot.project["story"]["scenes"][0]["id"], "arrival")
        self.assertFalse(any(scene["id"] == review.scene_ids[0]
                             for scene in undone.snapshot.project["story"]["scenes"]))

    def test_refuse_campaign_collision_without_corrupting_session(self):
        self.dialog.gallery_table.selectRow(0)
        self.dialog.gallery_campaign.setCurrentIndex(1)
        original = self.session.snapshot().to_dict()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
            self.assertIsNone(self.dialog.preview_gallery())
        self.assertFalse(self.dialog.gallery_apply_button.isEnabled())
        self.assertEqual(self.session.snapshot().to_dict(), original)

    def test_filters_and_changed_options_invalidate_review(self):
        self.dialog.gallery_table.selectRow(0)
        self.assertIsNotNone(self.dialog.preview_gallery())
        self.assertTrue(self.dialog.gallery_apply_button.isEnabled())
        self.dialog.gallery_filter.setCurrentIndex(3)
        self.assertFalse(self.dialog.gallery_apply_button.isEnabled())
        self.assertIsNone(self.dialog.apply_gallery())


if __name__ == "__main__":
    unittest.main()

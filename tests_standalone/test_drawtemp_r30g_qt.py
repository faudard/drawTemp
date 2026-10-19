"""R30.G Qt offscreen review, explicit apply and session-level Undo."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from drawtemp.studio.r30_assist_qt import R30AssistDialog
except ImportError:
    QApplication = None

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project


@unittest.skipIf(QApplication is None, "PySide6 optional")
class AssistedGenerationQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["r30g-qt-offscreen"])

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "game.json"
        content, project = reference_project()
        AuthoringSession.new(content, project).save_as(self.source)
        self.session = AuthoringSession.open(self.source)
        self.dialog = R30AssistDialog(self.session)
        self.addCleanup(self.dialog.close)
        self.dialog.coords[2].setValue(4)
        self.dialog.coords[3].setValue(3)

    def test_terrain_grid_preview_is_read_only_until_apply(self):
        original = self.session.snapshot().to_dict()
        path_bytes = self.source.read_bytes()
        review = self.dialog.preview_generation()
        self.assertEqual(review.mode, "clearing")
        self.assertEqual(self.dialog.preview_grid.rowCount(), 3)
        self.assertEqual(self.dialog.preview_grid.columnCount(), 4)
        self.assertTrue(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.session.snapshot().to_dict(), original)
        self.assertEqual(self.source.read_bytes(), path_bytes)
        changed = self.dialog.apply_generation()
        self.assertIsNotNone(changed)
        self.assertTrue(changed.snapshot.can_undo)
        self.assertEqual(self.source.read_bytes(), path_bytes)
        self.assertEqual(self.session.undo().snapshot.to_dict()["content"],
                         original["content"])

    def test_puzzle_preview_exposes_real_gate_and_switch_cells(self):
        self.dialog.mode_box.setCurrentIndex(2)
        preview = self.dialog.preview_generation()
        self.assertEqual(preview.mode, "lever-door")
        grid_text = [
            self.dialog.preview_grid.item(y, x).text()
            for y in range(self.dialog.preview_grid.rowCount())
            for x in range(self.dialog.preview_grid.columnCount())
        ]
        self.assertIn("Porte", grid_text)
        self.assertIn("Levier", grid_text)
        self.assertTrue(self.dialog.apply_button.isEnabled())
        before = self.session.revision
        transition = self.dialog.apply_generation()
        self.assertEqual(transition.snapshot.revision, before + 1)
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.session.undo().snapshot.revision, before + 2)

    def test_changed_selection_invalidates_ready_preview(self):
        self.assertIsNotNone(self.dialog.preview_generation())
        self.dialog.seed_spin.setValue(99)
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertIsNone(self.dialog.apply_generation())
        self.assertIsNone(self.dialog.controller._preview)

    def test_out_of_bounds_selection_fails_without_modal_or_mutation(self):
        self.dialog.coords[0].setValue(127)
        before = self.session.snapshot().to_dict()
        self.assertIsNone(self.dialog.preview_generation())
        self.assertIn("refusé", self.dialog.status.text().lower())
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_studio_menu_action_available_to_command_palette(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        settings = QSettings(str(self.root / "settings.ini"), QSettings.IniFormat)
        studio = StudioWindow(self.session, settings=settings)
        self.addCleanup(studio.close)
        self.assertIn("r30_assist", studio.commands)
        self.assertTrue(studio.commands["r30_assist"].isEnabled())


if __name__ == "__main__":
    unittest.main()

"""R58.B1 optional Qt smoke tests; offscreen is not onscreen/a11y certification."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.assets.packs import publish_pack
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from tests_standalone.test_drawtemp5_r24c import make_manifest, make_source

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from drawtemp.studio.package_manager_qt import PackageManagerDialog
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "PySide6 not installed")
class QtPackageManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.session = AuthoringSession.new(*reference_project())
        self.content_path = self.root / "game.json"
        self.session.save_as(self.content_path)

    def test_unsaved_project_disables_import_and_reports_blocker(self):
        dialog = PackageManagerDialog(self.session)
        self.assertFalse(dialog.install_button.isEnabled())
        self.assertEqual(dialog.table.rowCount(), 0)
        self.assertIn("Enregistrez", dialog.status.text())

    def test_pinned_local_install_removal_and_undo(self):
        source = make_source(self.root / "source-forest", make_manifest())
        archive = self.root / "pack.rpack"
        preview = publish_pack(source, archive)
        dialog = PackageManagerDialog(
            self.session, content_path=self.content_path)
        with patch("drawtemp.studio.package_manager_qt.QFileDialog.getOpenFileName",
                   return_value=(str(archive), "")), patch(
                   "drawtemp.studio.package_manager_qt.QInputDialog.getText",
                   return_value=(preview.sha256, True)), patch(
                   "drawtemp.studio.package_manager_qt.QMessageBox.question",
                   return_value=QMessageBox.Yes):
            dialog.install_selected()
        self.assertEqual(self.session.revision, 1)
        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertTrue(dialog.remove_button.isEnabled())
        self.assertIn("forest-pack", dialog.details.toPlainText())
        with patch("drawtemp.studio.package_manager_qt.QMessageBox.question",
                   return_value=QMessageBox.Yes):
            dialog.remove_selected()
        self.assertEqual(self.session.revision, 2)
        self.assertEqual(dialog.table.rowCount(), 0)
        self.session.undo()
        dialog.refresh()
        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertTrue((self.root /
            "assets/packs/forest-pack/1.0.0/terrain/forest.png").is_file())

    def test_rejected_sha_does_not_install(self):
        source = make_source(self.root / "source-forest", make_manifest())
        archive = self.root / "pack.rpack"
        publish_pack(source, archive)
        dialog = PackageManagerDialog(
            self.session, content_path=self.content_path)
        with patch("drawtemp.studio.package_manager_qt.QFileDialog.getOpenFileName",
                   return_value=(str(archive), "")), patch(
                   "drawtemp.studio.package_manager_qt.QInputDialog.getText",
                   return_value=("0" * 64, True)), patch(
                   "drawtemp.studio.package_manager_qt.QMessageBox.warning"):
            dialog.install_selected()
        self.assertEqual(self.session.revision, 0)
        self.assertEqual(dialog.table.rowCount(), 0)
        self.assertFalse((self.root / "assets").exists())

    def test_upgrade_dialog_applies_verified_new_version_and_explicit_downgrade(self):
        from drawtemp.assets.packs import install_pack
        from drawtemp.studio.package_manager import installed_package_usage
        old_source = make_source(self.root / "source-old", make_manifest())
        old_archive = self.root / "old.rpack"
        old_pack = publish_pack(old_source, old_archive)
        install_pack(old_pack, self.session, self.root)
        newer = make_manifest()
        newer["version"] = "1.1.0"
        source = make_source(self.root / "source-new", newer)
        archive = self.root / "new.rpack"
        pack = publish_pack(source, archive)
        dialog = PackageManagerDialog(
            self.session, content_path=self.content_path)
        self.assertTrue(dialog.upgrade_button.isEnabled())
        with patch("drawtemp.studio.package_manager_qt.QFileDialog.getOpenFileName",
                   return_value=(str(archive), "")), patch(
                   "drawtemp.studio.package_manager_qt.QInputDialog.getText",
                   return_value=(pack.sha256, True)), patch(
                   "drawtemp.studio.package_manager_qt.QMessageBox.question",
                   return_value=QMessageBox.Yes):
            dialog.upgrade_selected()
        self.assertEqual(installed_package_usage(self.session, self.root)[0]["version"],
                         "1.1.0")
        with patch("drawtemp.studio.package_manager_qt.QFileDialog.getOpenFileName",
                   return_value=(str(old_archive), "")), patch(
                   "drawtemp.studio.package_manager_qt.QInputDialog.getText",
                   return_value=(old_pack.sha256, True)), patch(
                   "drawtemp.studio.package_manager_qt.QMessageBox.question",
                   return_value=QMessageBox.Yes):
            dialog.upgrade_selected()
        self.assertEqual(installed_package_usage(self.session, self.root)[0]["version"],
                         "1.0.0")
        self.assertEqual(self.session.revision, 3)



if __name__ == "__main__":
    unittest.main()

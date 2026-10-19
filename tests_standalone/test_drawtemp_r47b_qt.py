"""R47.B Qt inspector and consent workflow (offscreen is not UX/GPU proof)."""
from copy import deepcopy
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.modding import ModError, ModRegistry
from drawtemp.sdk.reference import reference_project
from tests_standalone.test_drawtemp_r47a_modding import manifest

try:
    from PySide6.QtWidgets import QApplication, QListWidget, QWidget
    from drawtemp.studio.r47_mods_qt import ModManagerDialog
except ImportError:
    QApplication = None
    ModManagerDialog = None


@unittest.skipUnless(QApplication is not None, "PySide6 not installed")
class QtModInspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        class Owner(QWidget):
            def __init__(self):
                super().__init__()
                self.mods = ModRegistry()
                self.session = AuthoringSession.new(*reference_project())
                self.problems = QListWidget()
                self.refresh_count = 0

            def refresh(self):
                self.refresh_count += 1

        self.owner = Owner()
        self.dialog = ModManagerDialog(self.owner)
        self.addCleanup(self.dialog.close)
        self.addCleanup(self.owner.close)

    def _installed(self):
        result = self.dialog.install_descriptor(manifest())
        self.assertEqual(result["id"], "quest-mod")
        return result

    def test_inspection_and_opt_in_permissions(self):
        self._installed()
        self.assertFalse(self.owner.mods.status("quest-mod")["enabled"])
        self.assertIn("Droits légalement validés : NON",
                      self.dialog.details.toPlainText())
        self.assertIn("MIT", self.dialog.details.toPlainText())
        self.assertIn("project.extensions.write", self.dialog.details.toPlainText())
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.dialog._confirm = lambda *_args: False
        self.dialog._enable_clicked()
        self.assertFalse(self.owner.mods.status("quest-mod")["enabled"])
        self.assertEqual(self.owner.mods.status("quest-mod")["grants"], [])
        self.dialog._confirm = lambda *_args: True
        self.dialog._enable_clicked()
        self.assertTrue(self.owner.mods.status("quest-mod")["enabled"])
        self.assertTrue(self.dialog.apply_button.isEnabled())
        self.dialog._disable_clicked()
        self.assertFalse(self.owner.mods.status("quest-mod")["enabled"])
        self.assertEqual(self.owner.mods.status("quest-mod")["grants"], [])
        self.assertFalse(self.dialog.apply_button.isEnabled())

    def test_apply_preview_cancel_undo_and_data_retention(self):
        self._installed()
        self.dialog._confirm = lambda *_args: True
        self.dialog._enable_clicked()
        before = self.owner.session.snapshot().to_dict()
        self.dialog._confirm = lambda *_args: False
        self.dialog._apply_clicked()
        self.assertEqual(self.owner.session.snapshot().to_dict(), before)
        self.assertEqual(self.owner.session.revision, 0)
        self.dialog._confirm = lambda *_args: True
        self.dialog._apply_clicked()
        self.assertEqual(self.owner.session.revision, 1)
        self.assertEqual(self.owner.refresh_count, 1)
        self.assertEqual(
            self.owner.session.snapshot().to_dict()
            ["project"]["extensions"]["org.example.quest"]["data"]["entry"],
            "quest-1",
        )
        caught = []
        self.dialog._error = lambda exc: caught.append(exc)
        self.dialog._remove_clicked()
        self.assertEqual(len(caught), 1)
        self.assertIsInstance(caught[0], ModError)
        self.assertEqual(caught[0].code, "data_in_use")
        self.assertTrue(self.owner.mods.status("quest-mod")["enabled"])
        self.owner.session.undo()
        self.dialog._remove_clicked()
        self.assertEqual(self.owner.mods.statuses(), ())
        self.assertEqual(self.owner.session.snapshot().to_dict()["project"],
                         before["project"])

    def test_dependencies_protect_removal_even_without_project_data(self):
        self._installed()
        extension = manifest("dependent-mod", "org.example.dependent")
        extension["dependencies"] = [{"id": "quest-mod",
                                      "min_version": "1.0.0",
                                      "max_version": "2.0.0"}]
        self.dialog.install_descriptor(extension)
        self.dialog.refresh("quest-mod")
        self.dialog._confirm = lambda *_args: True
        errors = []
        self.dialog._error = lambda exc: errors.append(exc)
        self.dialog._remove_clicked()
        self.assertEqual(errors[0].code, "dependency_in_use")
        self.assertEqual(len(self.owner.mods.statuses()), 2)
        self.dialog.refresh("dependent-mod")
        self.dialog._remove_clicked()
        self.assertEqual(len(self.owner.mods.statuses()), 1)

    def test_dangerous_fields_rejected_before_mounting(self):
        data = manifest()
        data["entrypoint"] = "python:main"
        with self.assertRaises(ModError):
            self.dialog.install_descriptor(data)
        self.assertEqual(self.dialog.items.count(), 0)
        self.assertEqual(self.owner.mods.statuses(), ())

    def test_host_version_switch_revokes_consent_and_preserves_project(self):
        self._installed()
        self.dialog._confirm = lambda *_args: True
        self.dialog._enable_clicked()
        before = self.owner.session.snapshot().to_dict()
        candidate = manifest()
        candidate["version"] = "1.1.0"
        upgraded = self.dialog.replace_descriptor(candidate)
        self.assertEqual(upgraded["version"], "1.1.0")
        self.assertFalse(self.dialog.apply_button.isEnabled())
        self.assertEqual(self.owner.mods.status("quest-mod")["grants"], [])
        self.assertEqual(before, self.owner.session.snapshot().to_dict())
        with self.assertRaises(ModError) as denied:
            self.dialog.replace_descriptor(manifest())
        self.assertEqual(denied.exception.code, "downgrade_denied")
        rolled_back = self.dialog.replace_descriptor(
            manifest(), allow_downgrade=True)
        self.assertTrue(rolled_back["downgraded"])
        self.assertFalse(self.owner.mods.status("quest-mod")["enabled"])
        self.assertEqual(self.owner.session.snapshot().to_dict(), before)

    def test_no_stale_document_consent_in_main_window(self):
        from drawtemp.studio.qt_shell import StudioWindow
        from PySide6.QtCore import QSettings
        with TemporaryDirectory() as temp:
            prefs = QSettings(str(Path(temp) / "studio.ini"), QSettings.IniFormat)
            window = StudioWindow(settings=prefs)
            self.addCleanup(window.close)
            window.mods.install(manifest())
            window.mods.enable("quest-mod", grants=["project.extensions.write"])
            self.assertTrue(window.mods.status("quest-mod")["enabled"])
            fresh = AuthoringSession.new(*reference_project())
            window._install_document(fresh, Path(temp) / "other.json")
            self.assertEqual(window.mods.statuses(), ())
            self.assertIs(window.session, fresh)


if __name__ == "__main__":
    unittest.main()

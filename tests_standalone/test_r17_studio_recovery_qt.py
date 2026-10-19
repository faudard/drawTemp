"""R17.11 Qt MapWindow: real recovery dialog and external-save conflict."""
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "Qt 6 optional")
class StudioRecoveryUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def window(self, studio=None):
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.studio.map_editor import MapWindow
        w = MapWindow(studio or MapStudio.reference())
        self.addCleanup(w.deleteLater)
        self.assertIsNotNone(w.viewport.rootObject())
        self.assertIn("Récupérer projet", w.toolbar_actions)
        self.assertIn("Enregistrer une copie", w.toolbar_actions)
        return w

    def click_dialog_button(self, label):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QMessageBox

        def click():
            active = QApplication.activeModalWidget()
            self.assertIsInstance(active, QMessageBox)
            candidates = [button for button in active.buttons()
                          if button.text() == label]
            self.assertEqual(len(candidates), 1)
            self.assertTrue(candidates[0].isEnabled())
            candidates[0].click()
        QTimer.singleShot(0, click)

    def interrupted_pair(self, folder):
        from drawtemp.sdk.reference import reference_project
        from sporebound.studio_transaction import StudioTransactionStore
        source = Path(folder) / "jeanne.json"
        store = StudioTransactionStore(source)
        content, project = reference_project()
        original_content, original_project = content.to_dict(), project.to_dict()
        store.save(original_content, original_project)
        modified_content = content.to_dict()
        modified_project = project.to_dict()
        modified_content["missions"][0]["name"] = "R17 UI restaurée"
        modified_project["title"] = "R17 interface restaurée"
        original = store._publish_one
        counter = []

        def interrupt(path):
            counter.append(path)
            if len(counter) == 2:
                raise OSError("simulated second document crash")
            original(path)

        with patch.object(store, "_publish_one", side_effect=interrupt):
            with self.assertRaises(OSError):
                store.save(modified_content, modified_project)
        return source, store

    def test_real_modal_completes_then_opens_verified_authoring(self):
        with TemporaryDirectory() as directory:
            source, store = self.interrupted_pair(directory)
            w = self.window()
            self.click_dialog_button("Terminer l'enregistrement")
            w.recover_project(str(source))
            self.assertFalse(store.pending)
            snapshot = w.studio.snapshot()
            self.assertEqual(snapshot["project"]["title"], "R17 interface restaurée")
            self.assertEqual(snapshot["content"]["missions"][0]["name"],
                             "R17 UI restaurée")
            self.assertFalse(snapshot["dirty"])

    def test_modal_cancel_preserves_both_documents_and_journal(self):
        with TemporaryDirectory() as directory:
            source, store = self.interrupted_pair(directory)
            w = self.window()
            before = tuple(path.read_bytes() for path in store.paths)
            journal = store.journal.read_bytes()
            self.click_dialog_button("Annuler")
            w.recover_project(str(source))
            self.assertTrue(store.pending)
            self.assertEqual(tuple(path.read_bytes() for path in store.paths), before)
            self.assertEqual(store.journal.read_bytes(), journal)

    def test_external_modifications_offer_copy_without_overwriting(self):
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.sdk.authoring import AuthoringSession
        with TemporaryDirectory() as directory:
            source = Path(directory) / "jeanne.json"
            studio = MapStudio.reference()
            studio.save_as(source)
            w = self.window(studio)
            studio.rename("Carte locale")
            # Another writer updated Content on disk (even with valid JSON).
            source.write_bytes(source.read_bytes() + b" ")
            external = source.read_bytes()
            copy = Path(directory) / "carte-copie.json"
            self.click_dialog_button("Enregistrer une copie")
            with patch("drawtemp.studio.map_editor.QFileDialog.getSaveFileName",
                       return_value=(str(copy), "Content JSON (*.json)")):
                w.save_map()
            self.assertEqual(source.read_bytes(), external)
            self.assertTrue(copy.is_file())
            reopened = AuthoringSession.open(copy)
            self.assertEqual(reopened.snapshot().content["missions"][0]["name"],
                             "Carte locale")
            self.assertFalse(w.studio.snapshot()["dirty"])


if __name__ == "__main__":
    unittest.main()

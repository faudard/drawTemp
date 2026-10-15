"""R8.C Qt regression: variable references and group edits in the same window."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
except ModuleNotFoundError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "Optional PySide6 is unavailable")
class IntegrityQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        self.content, self.project = reference_project()
        self.session = AuthoringSession.new(self.content, self.project)

    def test_variable_family_reports_actual_references(self):
        from drawtemp.studio.rpg_database_qt import DatabaseWindow
        def put_flag(project):
            project["story"]["scenes"][0]["choices"][0]["effects"] = [
                {"kind": "set_flag", "flag": "courage", "value": 1}]
            return project
        self.session.apply(self.session.preview_project(put_flag))
        window = DatabaseWindow(self.session)
        try:
            window.tree.setCurrentItem(window.tree.topLevelItem(5))
            self.assertEqual(window.family, "flags")
            self.assertTrue(any("courage" in window.listing.item(i).text()
                                for i in range(window.listing.count())))
            self.assertIn("GameProject.story", window.references.toPlainText())
            with patch("PySide6.QtWidgets.QDialog.exec", return_value=0):
                window._show_variables()
        finally:
            window.close()

    def test_bulk_edit_two_actors_one_undo(self):
        from drawtemp.studio.rpg_database_qt import DatabaseWindow
        window = DatabaseWindow(self.session)
        try:
            window.tree.setCurrentItem(window.tree.topLevelItem(1))
            self.assertGreaterEqual(window.listing.count(), 2)
            window.listing.item(0).setSelected(True)
            window.listing.item(1).setSelected(True)
            selected = window._selected_resources()
            self.assertGreaterEqual(len(selected), 2)
            baseline = self.session.snapshot()
            with patch("PySide6.QtWidgets.QInputDialog.getItem",
                       return_value=("Vitesse", True)), patch(
                       "PySide6.QtWidgets.QInputDialog.getInt",
                       return_value=(13, True)), patch(
                       "PySide6.QtWidgets.QMessageBox.question",
                       return_value=QMessageBox.Yes):
                window._bulk_edit()
            self.assertEqual(self.session.snapshot().revision,
                             baseline.revision + 1)
            self.session.undo()
            self.assertEqual(self.session.snapshot().content, baseline.content)
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

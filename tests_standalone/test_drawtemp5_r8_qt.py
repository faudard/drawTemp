"""R8 Qt view test; skips without the optional Python 3.12 Qt dependency."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "PySide6 extra is not installed")
class RPGDatabaseQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_navigation_edit_undo_refresh(self):
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        from drawtemp.studio.rpg_database_qt import DatabaseWindow

        content, project = reference_project()
        window = DatabaseWindow(AuthoringSession.new(content, project))
        try:
            self.assertGreater(window.listing.count(), 0)
            window.tree.setCurrentItem(window.tree.topLevelItem(3))  # Skills
            self.assertEqual(window.family, "skills")
            self.assertGreater(window.listing.count(), 0)
            window.editor.create("skills", "r8_qt_smoke", name="Essai UI")
            window._reload(("skills", "r8_qt_smoke", ""))
            self.assertEqual(window.selected[1], "r8_qt_smoke")
            self.assertIn("Essai UI", window.header.text())
            window.editor.undo()
            window._reload()
            self.assertNotIn("r8_qt_smoke",
                [entry.id for entry in window.editor.entries("skills")])
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

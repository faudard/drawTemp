"""Qt ADS integration smoke and graceful fallback tests.

Run on Windows with Python 3.12 and pip install -e '.[qt6-docking]':
    python -m unittest tests_standalone.test_studio_qtads -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtWidgets import QApplication, QLabel, QDockWidget, QMainWindow
    from drawtemp.studio.ads_docking import DockHost
except ImportError:
    HAS_QT = False
else:
    HAS_QT = True


@unittest.skipUnless(HAS_QT, "PySide6 is not installed")
class DockHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_native_fallback_preserves_editor_and_panels(self):
        main = QMainWindow()
        central = QLabel("Canonical editor")
        with patch.dict(sys.modules, {"PySide6QtAds": None}):
            host = DockHost(main, central)
        self.assertFalse(host.enabled)
        self.assertIs(main.centralWidget(), central)
        inspector = host.add("Inspector", "inspector", QLabel("Selection"),
                             Qt.RightDockWidgetArea, auto_hide=True)
        self.assertIsInstance(inspector, QDockWidget)
        self.assertEqual(inspector.objectName(), "inspector")
        self.assertTrue(host.restore_state(host.save_state()))
        host.remove(inspector)
        self.assertNotIn("inspector", host.panels)
        main.close()

    def test_invalid_state_is_ignored(self):
        main = QMainWindow()
        with patch.dict(sys.modules, {"PySide6QtAds": None}):
            host = DockHost(main, QLabel("Viewport"))
        self.assertFalse(host.restore_state(None))
        self.assertFalse(host.restore_state("invalid"))
        self.assertFalse(host.restore_state(QByteArray()))
        self.assertFalse(host.restore_state(QByteArray(b"x" * (1024 * 1024 + 1))))
        main.close()

    def test_ads_sidebar_and_restore_state(self):
        try:
            import PySide6QtAds
        except (ImportError, OSError):
            self.skipTest("PySide6-QtAds optional extra not installed")
        main = QMainWindow()
        central = QLabel("Same viewport")
        host = DockHost(main, central)
        self.assertTrue(host.enabled)
        self.assertIsNotNone(host.manager)
        self.assertIs(host.central_dock.widget(), central)
        inspector = host.add("Inspector", "inspector", QLabel("Selection"),
                             Qt.RightDockWidgetArea, auto_hide=True)
        resources = host.add("Project", "resources", QLabel("Explorer"),
                             Qt.LeftDockWidgetArea)
        self.assertEqual(inspector.objectName(), "inspector")
        self.assertTrue(inspector.toggleViewAction())
        self.assertTrue(resources.toggleViewAction())
        state = host.save_state()
        self.assertTrue(host.restore_state(state))
        main.close()


if __name__ == "__main__":
    unittest.main()

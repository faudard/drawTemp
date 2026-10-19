"""R30.F Qt offscreen read-only plots and Studio tools action."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from drawtemp.studio.r30_scale_qt import R30ScaleDashboard
except ImportError:
    QApplication = None

from drawtemp.quality.r30_scale import collect_profile, OPS
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project


@unittest.skipIf(QApplication is None, "PySide6 optional")
class R30ScaleQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["drawtemp-r30f-test"])
        cls.profile = collect_profile(samples=3, warmups=0)

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.file = self.path / "profile.json"
        self.file.write_text(json.dumps(self.profile), encoding="utf-8")
        self.dashboard = R30ScaleDashboard()
        self.addCleanup(self.dashboard.close)

    def test_report_load_updates_cpu_charts_and_memory_table(self):
        self.assertFalse(self.dashboard.compare_button.isEnabled())
        self.assertFalse(self.dashboard.chart.rows)
        self.assertTrue(self.dashboard.open_report(self.file))
        self.assertEqual(self.dashboard.table.rowCount(), len(OPS))
        self.assertEqual(len(self.dashboard.chart.rows), len(OPS))
        self.assertTrue(self.dashboard.compare_button.isEnabled())
        self.assertIn("p99 exploratoire", self.dashboard.status.text())
        self.assertIn("PAS", self.dashboard.banner.text())
        self.assertIn("Assets", self.dashboard.assets_label.text())
        self.dashboard.chart.resize(800, 350)
        self.dashboard.chart.repaint()  # QPainter must work offscreen.

    def test_baseline_compare_blocks_large_p95_regression_and_rejects_host(self):
        self.assertTrue(self.dashboard.open_report(self.file))
        result = self.dashboard.compare_baseline(self.file)
        self.assertFalse(result["blocked"])
        self.assertIn("Pas de dépassement", self.dashboard.status.text())
        invalid = deepcopy(self.profile)
        invalid["environment"]["hostname"] = "different-host"
        base = self.path / "different-host.json"
        base.write_text(json.dumps(invalid), encoding="utf-8")
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
            self.assertIsNone(self.dashboard.compare_baseline(base))
        self.assertIn("Comparaison refusée", self.dashboard.status.text())

    def test_report_cannot_fake_gpu_certification(self):
        forged = deepcopy(self.profile)
        forged["gate"]["gpu_certified"] = True
        file = self.path / "fake.json"
        file.write_text(json.dumps(forged), encoding="utf-8")
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
            self.assertFalse(self.dashboard.open_report(file))
        self.assertEqual(self.dashboard.table.rowCount(), 0)
        self.assertFalse(self.dashboard.compare_button.isEnabled())

    def test_studio_tool_wires_read_only_dashboard_and_keeps_revision(self):
        from drawtemp.studio.qt_shell import StudioWindow
        from PySide6.QtCore import QSettings
        content, project = reference_project()
        session = AuthoringSession.new(content, project)
        config = QSettings(str(self.path / "settings.ini"), QSettings.IniFormat)
        studio = StudioWindow(session, settings=config)
        self.addCleanup(studio.close)
        self.assertIn("r30_scale", studio.commands)
        self.assertTrue(studio.commands["r30_scale"].isEnabled())
        self.assertEqual(session.revision, 0)


if __name__ == "__main__":
    unittest.main()

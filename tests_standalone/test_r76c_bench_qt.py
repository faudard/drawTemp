"""Qt offscreen smoke for R76.C read-only report and comparable delta."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.r76_bench_qt import R76BenchmarkDialog
except ImportError:
    QApplication = None

from drawtemp.quality.r76_bench import _series
from tests_standalone.test_r76c_bench import R76CBenchTests


@unittest.skipIf(QApplication is None, "PySide6 unavailable")
class R76BenchmarkQtSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        source = R76CBenchTests("test_measured_inventory_and_percentile_contracts")
        source.setUp()
        self.addCleanup(source.doCleanups)
        self.report = source._collect()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.baseline = self.root / "base.json"
        self.candidate = self.root / "candidate.json"

    def test_load_reports_informational_comparison(self):
        changed = json.loads(json.dumps(self.report))
        changed["measurements"]["project_load_process_ms"] = _series([18] * 5)
        self.baseline.write_text(json.dumps(self.report), encoding="utf-8")
        self.candidate.write_text(json.dumps(changed), encoding="utf-8")
        dialog = R76BenchmarkDialog()
        self.addCleanup(dialog.close)
        self.assertFalse(dialog.comparison.isEnabled())
        dialog.load_report("baseline", self.baseline)
        dialog.load_report("candidate", self.candidate)
        self.assertTrue(dialog.comparison.isEnabled())
        self.assertTrue(dialog.compare_loaded())
        self.assertIn("NO-GO", dialog.summary.text())
        self.assertIn("NON MESURÉ", dialog._fields(self.report)["GPU physique"])

    def test_refuse_incomparable_reports(self):
        changed = json.loads(json.dumps(self.report))
        changed["environment"]["os"] = "DIFFERENT"
        self.baseline.write_text(json.dumps(self.report), encoding="utf-8")
        self.candidate.write_text(json.dumps(changed), encoding="utf-8")
        dialog = R76BenchmarkDialog()
        self.addCleanup(dialog.close)
        dialog.load_report("baseline", self.baseline)
        dialog.load_report("candidate", self.candidate)
        self.assertFalse(dialog.compare_loaded())
        self.assertIn("Comparaison refusée", dialog.summary.text())


if __name__ == "__main__":
    unittest.main()

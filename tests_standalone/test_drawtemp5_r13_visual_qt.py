"""Offscreen native Qt smoke and bar-chart drilldown for R13.8."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Qt6 optional dependency not installed")
class R13VisualQtTests(unittest.TestCase):
    def test_comparative_bars_render_and_choose_a_seed(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        from drawtemp.sdk.r13_visual_metrics import build_visual_comparison
        from drawtemp.studio.r13_charts import R13ComparisonCharts
        from sporebound.battle_lab import run_lab
        from sporebound.model import Board, Content, Mission, Unit

        app = QApplication.instance() or QApplication([])
        content = Content({}, {"visual": Mission(
            "visual", "Visual", Board(5, 5),
            [Unit("hero", "Hero", "player", (0, 1)),
             Unit("enemy", "Enemy", "enemy", (4, 1))],
        )})
        reference = run_lab(content, "visual", seeds=(19, 4),
                            max_commands=12)
        report = build_visual_comparison(reference, reference)
        panel = R13ComparisonCharts()
        panel.resize(1050, 740)
        panel.show()
        app.processEvents()
        selected = []
        panel.seedSelected.connect(selected.append)
        panel.set_report(report)
        app.processEvents()
        self.assertEqual(panel.report["seed_order"], [19, 4])
        self.assertEqual(panel.seed_plot._rows()[0][0], "19")
        self.assertEqual(panel.seed_plot._row_index(70), 0)
        self.assertFalse(panel.aggregate_plot.grab().isNull())
        self.assertFalse(panel.seed_plot.grab().isNull())
        QTest.mouseClick(panel.seed_plot, Qt.MouseButton.LeftButton,
                         pos=QPoint(200, 80))
        self.assertEqual(selected, [19])
        self.assertEqual(panel.seed_plot._selected, 19)
        panel.metric_selector.setCurrentIndex(1)
        self.assertEqual(panel.seed_plot.metric, "commands")
        self.assertEqual(panel.seed_plot._rows()[1][2],
                         [reference["samples"][1]["commands"]] * 2)
        panel.set_report(build_visual_comparison(
            reference, reference, objective_changed=True))
        self.assertIn("contrôle requis", panel.notice.text())
        with TemporaryDirectory() as folder:
            filename = Path(folder) / "r13-visual.png"
            saved = panel.export_png(filename)
            self.assertEqual(saved, filename)
            self.assertTrue(filename.read_bytes().startswith(
                b"\\x89PNG\\r\\n\\x1a\\n"))
            with self.assertRaises(FileExistsError):
                panel.export_png(filename)
            with self.assertRaises(ValueError):
                panel.export_png(Path(folder) / "report.json")
        panel.clear()
        with TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                panel.export_png(Path(folder) / "empty.png")
        self.assertIsNone(panel.report)
        panel.close()


if __name__ == "__main__":
    unittest.main()

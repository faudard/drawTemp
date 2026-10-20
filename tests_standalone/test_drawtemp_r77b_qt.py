"""R77.B Studio/QTest offscreen: explicit scene, selection, comparison, nonmutation."""
import json
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from drawtemp.studio.qt_shell import StudioWindow
    from drawtemp.studio.r77_exploration_qt import ExplorationLabDialog
except ImportError:
    QApplication = None

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project


def scene(*, wall=False):
    return {"id": "r77_ui_scene", "width": 5, "height": 5,
            "walls": [[3, 2]] if wall else [],
            "hero": {"pos": [1, 2], "hp": 12}, "enemies": [], "objects": []}


@unittest.skipIf(QApplication is None, "PySide6 Qt optional")
class ExplorationLabQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["r77b-qt-offscreen"])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.author = AuthoringSession.new(*reference_project())
        settings = QSettings(str(self.root / "studio.ini"), QSettings.IniFormat)
        self.studio = StudioWindow(self.author, settings=settings)
        self.addCleanup(self.studio.close)
        self.dialog = ExplorationLabDialog(self.studio, scene=scene())
        self.addCleanup(self.dialog.close)
        self.dialog.seeds.setText("0")
        self.dialog.ticks.setValue(20)

    def test_command_palette_analysis_open_and_verified_heatmap(self):
        self.assertIn("r77_lab", self.studio.commands)
        self.assertTrue(self.studio.commands["r77_lab"].isEnabled())
        self.studio.navigate("analysis")
        page = self.studio.pages["analysis"]
        self.assertIsNotNone(page.findChild(type(self.dialog.analyze_button),
                                            "r77-lab-open-analysis"))
        before = self.author.snapshot().to_dict()
        self.dialog.show()
        QTest.mouseClick(self.dialog.analyze_button, Qt.LeftButton)
        self.assertIsNotNone(self.dialog.view, self.dialog.status.text())
        self.assertTrue(self.dialog.view["source_verified"])
        self.assertEqual(self.dialog.heatmap.rowCount(), 5)
        self.assertEqual(self.dialog.heatmap.columnCount(), 5)
        self.assertGreater(self.dialog.runs.count(), 0)
        self.assertGreater(self.dialog.steps.count(), 0)
        self.dialog.select_heat_cell(2, 1)
        self.assertIn("Cellule (1, 2)", self.dialog.cell_info.text())
        self.assertEqual(before, self.author.snapshot().to_dict())
        self.assertFalse(self.dialog.map_button.isEnabled())
        self.assertFalse(self.dialog.graph_button.isEnabled())

    def test_reference_comparison_and_no_implicit_edits(self):
        before = self.author.snapshot().to_dict()
        self.assertIsNotNone(self.dialog.analyze())
        self.assertTrue(self.dialog.pin_reference())
        initial = deepcopy(self.dialog.reference)
        self.dialog.set_scene(scene(wall=True))
        self.dialog.seeds.setText("0")
        self.dialog.ticks.setValue(20)
        second = self.dialog.analyze()
        self.assertIsNotNone(second, self.dialog.status.text())
        self.assertTrue(self.dialog.comparison["source_changed"])
        self.assertFalse(self.dialog.comparison["release_certified"])
        self.assertEqual(self.dialog.reference, initial)
        self.assertIn("source_changed", self.dialog.compare_details.toPlainText())
        self.assertEqual(before, self.author.snapshot().to_dict())

    def test_finding_human_review_does_not_certify_runtime(self):
        locked = scene()
        locked["walls"] = [[2, y] for y in range(5)]
        self.dialog.set_scene(locked)
        self.dialog.seeds.setText("1")
        self.dialog.ticks.setValue(10)
        original = self.author.snapshot().to_dict()
        report = self.dialog.analyze()
        self.assertIsNotNone(report, self.dialog.status.text())
        self.assertGreater(self.dialog.findings.count(), 0)
        self.dialog.findings.setCurrentRow(0)
        self.dialog.reason.setPlainText("Vérifier manuellement cette impasse.")
        review = self.dialog.annotate()
        self.assertEqual(review["human_review_only"], True)
        self.assertFalse(report["release_certified"])
        self.assertEqual(self.author.snapshot().to_dict(), original)

    def test_explicit_file_import_bound_and_invalid_goals(self):
        path = self.root / "tiny.json"
        raw = json.dumps(scene()).encode("utf-8")
        path.write_bytes(raw)
        self.dialog.load_scene(path)
        self.assertEqual(path.read_bytes(), raw)
        self.dialog.goals.setText("invalid")
        self.assertIsNone(self.dialog.analyze())
        self.assertIn("refusée", self.dialog.status.text())
        self.assertEqual(path.read_bytes(), raw)
        huge = self.root / "too_big.json"
        huge.write_bytes(b"x" * (256 * 1024 + 1))
        with self.assertRaises(ValueError):
            self.dialog.load_scene(huge)


if __name__ == "__main__":
    unittest.main()

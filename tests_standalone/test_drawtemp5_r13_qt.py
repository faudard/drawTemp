"""R13 Qt smoke: real Widgets composition, independent of the legacy Tk UI."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.model import Board, Content, Mission, Unit


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Qt6 optional dependency not installed")
class R13QtSmoke(unittest.TestCase):
    def test_encounter_window_opens_and_shows_authored_roster(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QGraphicsView, QTableWidget

        from drawtemp.studio.r13_workbench import launch

        content = Content({}, {"smoke": Mission(
            "smoke", "Smoke mission", Board(5, 5), [
                Unit("jeanne", "Jeanne", "player", (0, 1)),
                Unit("wolf", "Wolf", "enemy", (4, 1)),
            ])})
        with TemporaryDirectory() as folder:
            file = Path(folder) / "smoke.json"
            file.write_text(__import__("json").dumps(content.to_dict()),
                            encoding="utf-8")
            app = QApplication.instance() or QApplication([])
            captured = []

            def inspect():
                try:
                    window = app.r13_workbench
                    self.assertEqual(window.mission.currentText(), "smoke")
                    self.assertEqual(window.units.rowCount(), 2)
                    self.assertIsInstance(window.map, QGraphicsView)
                    self.assertIsInstance(window.outcomes, QTableWidget)
                    self.assertTrue(window.scene.items())
                    self.assertEqual(window.units.columnCount(), 6)
                    self.assertEqual(window.objective.currentText(), "eliminate")
                    self.assertFalse(window.apply_button.isEnabled())
                    # The map click is a real Qt signal into the UI editing
                    # path, not a direct mutation of the canonical Content.
                    window.units.selectRow(0)
                    window.map.tileChosen.emit(1, 1)
                    self.assertEqual(window.units.item(0, 2).text(), "1")
                    self.assertEqual(window.units.item(0, 3).text(), "1")
                    window.objective.setCurrentText("extract")
                    window.goal_cells.setText("3,3")
                    edits = window._read_editor_changes()
                    self.assertEqual(edits["unit_positions"], {"jeanne": [1, 1]})
                    self.assertEqual(edits["objective"], "extract")
                    self.assertEqual(edits["goal_cells"], [[3, 3]])
                    self.assertEqual(content.missions["smoke"].objective, "eliminate")
                    from sporebound.battle_lab import run_lab
                    report = run_lab(window.content, "smoke",
                                     seeds=(2, 5), max_commands=12)
                    window._show_simulation_charts(report)
                    self.assertEqual(window.charts.report["mode"], "single")
                    self.assertEqual(window.charts.report["runs"], 2)
                    window.reference = report
                    window._show_simulation_charts(report)
                    self.assertEqual(window.charts.report["mode"], "comparison")
                    self.assertTrue(window.charts.report["comparison"]["passed"])
                    from drawtemp.sdk.r13_combat_lab import simulate_encounter
                    result = simulate_encounter(
                        window.content, "smoke", seeds=(2, 5),
                        max_commands=12, trace_seed_id=2)
                    window._complete(window._sequence, ("simulation", result))
                    self.assertEqual(window.combat_analytics.model["seed"], 2)
                    self.assertEqual(window.combat_analytics.model["digest"],
                                     result["trace"]["digest"])
                    self.assertEqual(window.timeline.rowCount(),
                                     len(result["trace"]["steps"]))
                    self.assertTrue(window.timeline.rowCount())
                    window.combat_analytics.curve.stepSelected.emit(1)
                    self.assertEqual(window.timeline.currentRow(), 0)
                    self.assertEqual(window.transport.step, 1)
                    self.assertEqual(window.heatmap_panel.report["digest"],
                                     result["trace"]["digest"])
                    self.assertEqual(window.heatmap_panel.canvas.step, 1)
                    window.transport.play()
                    window.transport._advance()
                    if window.transport.maximum > 1:
                        self.assertEqual(window.transport.step, 2)
                        self.assertEqual(window.timeline.currentRow(), 1)
                        self.assertEqual(window.heatmap_panel.canvas.step, 2)
                    window.transport.pause()
                    window.transport.seek(0)
                    self.assertEqual(window.transport.step, 0)
                    self.assertEqual(window.heatmap_panel.canvas.step, 0)
                    window._refresh("smoke")
                    self.assertEqual(window.transport.maximum, 0)
                    self.assertFalse(window.transport.timer.isActive())
                    self.assertIsNone(window.heatmap_panel.report)
                    captured.append(True)
                except Exception as exc:
                    captured.append(exc)
                finally:
                    app.quit()

            QTimer.singleShot(0, inspect)
            self.assertEqual(launch(file), 0)
            self.assertEqual(captured, [True])


if __name__ == "__main__":
    unittest.main()

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

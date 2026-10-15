"""R13.8 GUI visual/functional certification gate (Qt offscreen).

Tests replay transport control and real widget pixel differences. Captures
cross-platform screenshots for optional human review in GitHub artifacts.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import unittest


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Qt6 optional dependency not installed")
class R13ReplayQtTests(unittest.TestCase):
    def test_transport_play_pause_step_seek_rate_and_reset(self):
        from PySide6.QtWidgets import QApplication
        from drawtemp.studio.r13_replay_heatmap import ReplayTransport

        app = QApplication.instance() or QApplication([])
        controls = ReplayTransport()
        events, playing = [], []
        controls.stepChanged.connect(events.append)
        controls.playingChanged.connect(playing.append)
        controls.set_frames(5)
        self.assertFalse(controls.playing)
        self.assertEqual(controls.step, 0)
        self.assertEqual(controls.maximum, 5)
        controls.play()
        self.assertTrue(controls.timer.isActive())
        controls._advance()
        self.assertEqual(controls.step, 1)
        self.assertEqual(events, [1])
        controls.pause()
        self.assertFalse(controls.timer.isActive())
        controls._advance()
        self.assertEqual(controls.step, 1)
        controls.speed.setCurrentIndex(3)
        self.assertEqual(controls.timer.interval(), 112)
        controls.seek(4)
        self.assertEqual(controls.slider.value(), 4)
        controls.seek(999)
        self.assertEqual(controls.step, 5)
        controls.play()  # Restart from frame zero after end-of-replay.
        self.assertEqual(controls.step, 0)
        for _ in range(5):
            controls._advance()
        self.assertFalse(controls.playing)
        self.assertEqual(controls.step, 5)
        controls.set_frames(0)
        self.assertEqual(controls.step, 0)
        self.assertFalse(controls.play_button.isEnabled())
        self.assertFalse(controls.timer.isActive())
        self.assertIn(True, playing)
        self.assertIn(False, playing)
        controls.close()

    def test_heatmap_render_filters_navigation_and_certification_images(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from drawtemp.sdk.r13_movement_heatmap import build_movement_heatmap
        from drawtemp.studio.r13_replay_heatmap import MovementHeatmapPanel
        from tests_standalone.test_drawtemp5_r13_heatmap import observed_trace

        app = QApplication.instance() or QApplication([])
        model = build_movement_heatmap(observed_trace())
        panel = MovementHeatmapPanel()
        panel.resize(900, 620)
        panel.show()
        panel.set_report(model)
        app.processEvents()
        self.assertEqual(panel.report["levels"], [0, 1])
        self.assertFalse(panel.canvas.grab().isNull())
        panel.mode.setCurrentIndex(1)
        self.assertEqual(panel.canvas.mode, "visits")
        at_start = panel.canvas.grab().toImage()

        panel.set_step(4)
        self.assertEqual(panel.canvas.step, 4)
        at_end = panel.canvas.grab().toImage()
        self.assertNotEqual(at_start, at_end)
        self.assertEqual(panel.canvas._counts[(1, 1)], 1)
        self.assertEqual(panel.canvas._counts[(2, 1)], 1)
        panel.mode.setCurrentIndex(0)
        self.assertEqual(panel.canvas._counts[(2, 1)], 1)
        self.assertEqual(panel.canvas._counts[(1, 1)], 0)
        panel.floor.setCurrentIndex(1)
        self.assertEqual(panel.canvas.level, 1)
        self.assertEqual(panel.canvas._counts[(2, 1)], 1)
        panel.floor.setCurrentIndex(0)
        panel.mode.setCurrentIndex(1)
        selected = []
        panel.stepSelected.connect(selected.append)
        left, top, size = panel.canvas._geometry()
        pos = QPoint(int(left+2.5*size), int(top+1.5*size))
        QTest.mouseClick(panel.canvas, Qt.MouseButton.LeftButton, pos=pos)
        self.assertEqual(selected, [2])
        panel.team.setCurrentIndex(panel.team.findData("enemy"))
        self.assertEqual(panel.canvas._counts[(2, 1)], 0)
        panel.team.setCurrentIndex(0)

        evidence = os.environ.get("R13_VISUAL_EVIDENCE_DIR")
        if evidence:
            folder = Path(evidence)
            folder.mkdir(parents=True, exist_ok=True)
            panel.floor.setCurrentIndex(0)
            panel.mode.setCurrentIndex(1)
            panel.set_step(0)
            self.assertTrue(panel.grab().save(str(folder / "heatmap-initial.png"), "PNG"))
            panel.set_step(4)
            self.assertTrue(panel.grab().save(str(folder / "heatmap-final.png"), "PNG"))
            (folder / "r13_visual_certification.json").write_text(json.dumps({
                "kind": "r13_qt_visual_automated_evidence",
                "source": "deterministic synthetic 2-floor fixture",
                "screenshots": ["heatmap-initial.png", "heatmap-final.png"],
                "assertions": [
                    "Distinct pixels for initial and final replay heatmap",
                    "No idle occupancy counted as movement",
                    "Multi-floor isolation",
                    "Cell click selects observed canonical frame index",
                    "Transport play/pause/seek/rate/end/reset functional",
                ],
                "human_visual_signoff": False,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        panel.clear()
        self.assertIsNone(panel.report)
        panel.close()


if __name__ == "__main__":
    unittest.main()

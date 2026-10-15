"""Qt 6 offscreen smoke for R13.8 executed AI actions and PV flow charts."""
from __future__ import annotations

import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "PySide6 Qt6 is an optional dependency")
class R13AICombatQtTests(unittest.TestCase):
    def test_true_replay_charts_filters_and_command_navigation(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication

        from drawtemp.sdk.r13_ai_combat_visuals import build_combat_visuals
        from drawtemp.studio.r13_ai_combat_panel import R13AICombatPanel
        from sporebound.battle_diagnostics import trace_seed
        from sporebound.model import Board, Content, Mission, Unit

        app = QApplication.instance() or QApplication([])
        content = Content({}, {"visual": Mission(
            "visual", "Visual combat", Board(6, 5), [
                Unit("hero", "Hero", "player", (0, 1)),
                Unit("foe", "Foe", "enemy", (4, 1)),
            ])})
        trace = trace_seed(content, "visual", seed=3, max_commands=36)
        visual = build_combat_visuals(trace)
        panel = R13AICombatPanel()
        panel.resize(1200, 690)
        panel.show()
        panel.set_report(visual)
        app.processEvents()
        self.assertEqual(panel.model["seed"], 3)
        self.assertTrue(panel.decisions.rows)
        self.assertEqual(len(panel.curve.series), len(trace["steps"]) + 1)
        self.assertFalse(panel.decisions.grab().isNull())
        self.assertFalse(panel.curve.grab().isNull())
        selected = []
        panel.stepSelected.connect(selected.append)

        panel.team.setCurrentIndex(2)
        self.assertEqual(panel.decisions.filter_team, "enemy")
        self.assertTrue(all("enemy" in grouped
                            for _, grouped in panel.decisions.rows))
        panel.team.setCurrentIndex(0)
        panel.focus.setCurrentIndex(3)
        self.assertEqual(panel.curve.actor_id,
                         sorted(visual["unit_teams"])[0])

        panel.focus.setCurrentIndex(0)
        self.assertEqual(panel.curve.actor_id, None)
        panel.curve.select_step(4)
        self.assertEqual(panel.curve.selected_step, 4)
        panel.curve.stepSelected.emit(4)
        self.assertEqual(selected, [4])
        QTest.mouseMove(panel.curve, QPoint(170, 100))
        self.assertIn("PV", panel.curve.toolTip())

        panel.clear()
        self.assertIsNone(panel.model)
        self.assertEqual(panel.decisions.rows, [])
        self.assertEqual(panel.curve.series, [])
        panel.close()


if __name__ == "__main__":
    unittest.main()

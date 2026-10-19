"""Optional R36.A Qt smoke: widget edits a real canonical animation graph."""
from __future__ import annotations

import importlib.util
import os
import unittest

from tests_standalone.test_r36_animation_graph import authored
from drawtemp.studio.animation_graph_authoring import AnimationControllerAuthoring

HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "Qt6 not installed")
class AnimationControllerQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_visual_states_transitions_preview_apply_undo(self):
        from drawtemp.studio.animation_graph_qt import AnimationControllerPanel

        session = authored()
        widget = AnimationControllerPanel(session)
        self.assertEqual(widget.objectName(), "r36-animation-controller")
        self.assertEqual(widget.animation.count(), 2)
        widget.identifier.setText("hero_controller")
        widget.state_id.setText("idle")
        widget.animation.setCurrentIndex(widget.animation.findData("idle_anim"))
        widget.add_state()
        widget.state_id.setText("attack")
        widget.animation.setCurrentIndex(widget.animation.findData("attack_anim"))
        widget.add_state()
        self.assertEqual(widget.states.count(), 2)
        widget.source.setCurrentIndex(widget.source.findData("idle"))
        widget.target.setCurrentIndex(widget.target.findData("attack"))
        widget.event.setText("attack")
        widget.priority.setValue(10)
        widget.add_transition()
        widget.source.setCurrentIndex(widget.source.findData("attack"))
        widget.target.setCurrentIndex(widget.target.findData("idle"))
        widget.event.setText("finished")
        widget.priority.setValue(9)
        widget.add_transition()
        before = session.revision
        widget.preview()
        self.assertTrue(widget.apply_button.isEnabled())
        self.assertEqual(session.revision, before)
        widget.apply()
        self.assertEqual(session.revision, before + 1)
        rows = AnimationControllerAuthoring(session).controllers()
        self.assertEqual(rows[0]["initial"], "idle")
        self.assertEqual(len(rows[0]["transitions"]), 2)
        widget.tick.setValue(3)
        widget.sample()
        self.assertIn("s_idle", widget.report.toPlainText())
        session.undo()
        widget.refresh()
        self.assertEqual(AnimationControllerAuthoring(session).controllers(), [])
        widget.close()


if __name__ == "__main__":
    unittest.main()

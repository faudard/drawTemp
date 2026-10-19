"""R36.B2 Qt offscreen: marker authoring and preview via R1 revisions."""
from __future__ import annotations

import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "PySide6 optional")
class TimelineQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_visual_marker_edit_preview_apply_undo(self):
        from tests_standalone.test_r36_animation_graph import authored, graph
        from drawtemp.studio.animation_graph_authoring import AnimationControllerAuthoring
        from drawtemp.studio.animation_timeline_qt import AnimationTimelinePanel
        from drawtemp.studio.animation_timeline_authoring import AnimationTimelineAuthoring

        session = authored()
        controller = AnimationControllerAuthoring(session)
        controller.apply(controller.preview(graph()))
        widget = AnimationTimelinePanel(session)
        self.assertEqual(widget.objectName(), "r36-visual-timeline")
        self.assertEqual(widget.controllers.currentText(), "hero_animation")
        widget.states.setCurrentIndex(widget.states.findData("attack"))
        widget.marker_id.setText("trail_first")
        widget.at_ms.setValue(40)
        widget.cue.setCurrentIndex(widget.cue.findData("trail"))
        widget.add_marker()
        self.assertEqual(widget.markers.count(), 1)
        widget.sample()
        self.assertIn("trail_first", widget.report.toPlainText())
        before = session.revision
        widget.preview()
        self.assertTrue(widget.apply_button.isEnabled())
        self.assertEqual(session.revision, before)
        widget.apply()
        self.assertEqual(session.revision, before + 1)
        authored_rows = AnimationTimelineAuthoring(session).timelines()
        self.assertEqual(authored_rows[0]["tracks"][-1]["markers"][0]["cue"],
                         "trail")
        session.undo()
        widget.refresh()
        self.assertEqual(AnimationTimelineAuthoring(session).timelines(), [])
        session.redo()
        widget.refresh()
        widget.delete_timeline()
        self.assertEqual(AnimationTimelineAuthoring(session).timelines(), [])
        session.undo()
        self.assertEqual(len(AnimationTimelineAuthoring(session).timelines()), 1)
        widget.close()


if __name__ == "__main__":
    unittest.main()

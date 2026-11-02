"""R5 Editor/Events mode uses the same QML viewport and R1 session."""
import importlib.util
import os
import unittest

QT_AVAILABLE = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(QT_AVAILABLE, "PySide6 Qt 6 is optional")
class MapEventsQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_switch_modes_and_create_event_on_same_map(self):
        from drawtemp.studio.map_authoring import MapStudio
        from drawtemp.studio.map_editor import MapWindow

        studio = MapStudio.reference()
        window = MapWindow(studio)
        try:
            viewport = window.viewport
            renderer = window.renderer
            camera = dict(renderer.cameraState)
            baseline = studio.snapshot()
            window.editor_mode.setCurrentText("Events")
            self.assertIs(window.viewport, viewport)
            self.assertIs(window.renderer, renderer)
            self.assertEqual(window.viewport.rootObject().property("interactionMode"), "select")
            self.assertTrue(window.viewport.rootObject().property("showEventMarkers"))
            self.assertEqual(studio.snapshot(), baseline)
            window.select_event_cell(1, 1)
            window.events.create_at_focus("r5_mode_gui_event", "Hello")
            window.refresh()
            self.assertEqual(window.events.selected_id, "r5_mode_gui_event")
            self.assertEqual(window.events_list.count(), len(window.events.events()))
            self.assertTrue(any(marker["event_id"] == "r5_mode_gui_event"
                                for marker in window.events.markers()))
            self.assertEqual(dict(renderer.cameraState), camera)
            window.editor_mode.setCurrentText("Editor")
            self.assertEqual(window.viewport.rootObject().property("interactionMode"), "edit")
            self.assertFalse(window.viewport.rootObject().property("showEventMarkers"))
            self.assertEqual(dict(renderer.cameraState), camera)
        finally:
            # Restore the pristine session to avoid a modal unsaved-document prompt.
            if any(e["id"] == "r5_mode_gui_event" for e in window.events.events()):
                studio.authoring.undo()
            window.close()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()

"""R14.4 Qt input journeys on the actual Studio/Player UIs.

CI uses a software/offscreen Qt backend. These are UI-input regression tests,
not a full onscreen accessibility or real-GPU certification.
"""
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "Qt 6 optional; R14 matrix installs pinned PySide6")
class QtUserJourneys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["drawtemp-r14-e2e"])

    def test_map_mouse_paint_undo_redo_and_save_reload(self):
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QToolButton
        from drawtemp.studio.map_editor import MapWindow
        from drawtemp.studio.map_authoring import MapStudio

        with TemporaryDirectory() as folder:
            saved = Path(folder) / "map.json"
            studio = MapStudio.reference()
            studio.save_as(saved)
            window = MapWindow(studio)
            window.show()
            try:
                QTest.qWait(200)
                self.assertIsNotNone(window.viewport.rootObject())
                self.assertEqual(window.viewport.rootObject().property("interactionMode"), "edit")
                # Set tool through its actual ComboBox; paint through a real Qt mouse event.
                window.tools.setCurrentText("Pinceau")
                window.material.setCurrentText("stone")
                x, y = 2, 2
                p = window.renderer.projection.project(x, y)
                sx, sy = window.renderer.camera.screen(*p)
                point = QPoint(round(sx), round(sy))
                self.assertGreater(point.x(), 0)
                self.assertLess(point.x(), window.viewport.width())
                self.assertGreater(point.y(), 0)
                self.assertLess(point.y(), window.viewport.height())
                before = studio.snapshot()["revision"]
                QTest.mouseClick(window.viewport, Qt.LeftButton, pos=point)
                QTest.qWait(80)
                self.assertEqual(studio.sample((x, y)), "stone")
                self.assertEqual(studio.snapshot()["revision"], before + 1)
                self.assertEqual(window.renderer.scene["mission"], studio.mission_id)

                def press_tool(label):
                    button = next((b for b in window.findChildren(QToolButton)
                                   if b.defaultAction() is not None and
                                   b.defaultAction().text() == label), None)
                    self.assertIsNotNone(button, "Missing toolbar action: " + label)
                    self.assertTrue(button.isVisible(), "Toolbar action is hidden: " + label)
                    QTest.mouseClick(button, Qt.LeftButton)
                    QTest.qWait(50)

                press_tool("Annuler")
                self.assertNotEqual(studio.sample((x, y)), "stone")
                press_tool("Rétablir")
                self.assertEqual(studio.sample((x, y)), "stone")
                press_tool("Enregistrer")
                reloaded = MapStudio.open(saved)
                self.assertEqual(reloaded.sample((x, y)), "stone")
                self.assertFalse(studio.snapshot()["dirty"])

                # R14.5: submit the real rendered frame for external golden review.
                # The capture is NOT considered an approved baseline.
                folder_env = os.environ.get("DRAWTEMP_R14_ARTIFACT_DIR")
                if folder_env:
                    from drawtemp.quality.visual import capture_widget
                    capture_widget(window.viewport, Path(folder_env) / "r14-studio.png")
            finally:
                # If assertion fails after edit, do not trigger offscreen modal
                # confirmation during tearDown.
                window.hide()
                window.deleteLater()

    def test_player_qml_clicks_new_choice_mission_save_resume(self):
        from PySide6.QtCore import QObject, QPoint, QPointF, QUrl, Qt
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtTest import QTest
        from drawtemp.player.qt_app import build_controller, create_bridge, scene_for_player
        from drawtemp.render.qt_viewport import make_controller
        from drawtemp.sdk.reference import MISSION

        with TemporaryDirectory() as folder:
            controller = build_controller(save_dir=folder, reference=True)
            renderer = make_controller(scene_for_player(controller))
            bridge = create_bridge(controller, renderer)
            engine = QQmlApplicationEngine()
            engine.setInitialProperties({"smokeMode": False})
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("player", bridge)
            engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] /
                                               "drawtemp/player/Main.qml")))
            self.assertTrue(engine.rootObjects(), "Real Player QML did not instantiate")
            window = engine.rootObjects()[0]
            try:
                window.show()
                QTest.qWait(180)
                self.assertEqual(controller.state()["screen"], "title")

                def click_text(label):
                    def recurse(node):
                        yield node
                        for child in node.childItems():
                            yield from recurse(child)
                    candidates = [
                        item for item in recurse(window.contentItem())
                        if item.property("text") == label and
                        item.property("down") is not None and
                        item.isVisible() and item.width() > 0 and item.height() > 0
                    ]
                    self.assertTrue(candidates, "Missing visible QML button: " + label)
                    button = candidates[0]
                    center = button.mapToScene(QPointF(button.width() / 2, button.height() / 2))
                    QTest.mouseClick(window, Qt.LeftButton,
                                     pos=QPoint(round(center.x()), round(center.y())))
                    QTest.qWait(80)

                click_text("Nouvelle partie")
                self.assertEqual(controller.state()["screen"], "dialogue")
                click_text("Entrer")
                self.assertEqual(controller.state()["screen"], "campaign")
                click_text("Commencer · " + MISSION)
                self.assertEqual(controller.state()["screen"], "battle")
                click_text("Sauvegarder · F5")
                self.assertTrue((Path(folder) / "slot_1.json").is_file())
                original = controller.session.recording()
                # Trigger a live title transition, then use the visible Continue button.
                bridge.titleScreen()
                self.assertEqual(controller.state()["screen"], "title")
                click_text("Continuer")
                self.assertEqual(controller.state()["screen"], "battle")
                self.assertEqual(controller.session.recording(), original)
                self.assertEqual(renderer.scene["mission"], MISSION)
            finally:
                window.hide()
                window.close()
                engine.deleteLater()


if __name__ == "__main__":
    unittest.main()

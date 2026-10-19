"""R17.12 Qt bridge proof on an actual cross-workshop authored project."""
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(QT, "PySide6 is optional; Qt CI installs it")
class R1712PlayerQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication(["r1712-player"])

    def test_actual_cross_workshop_player_qml_event_save_and_resume(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        from drawtemp.player.qt_app import (
            build_controller, create_bridge, scene_for_player)
        from drawtemp.render.qt_viewport import make_controller
        from drawtemp.quality.r17_cross_workshop import (
            MISSION, STORY_ID, author_project)

        with TemporaryDirectory() as folder:
            proof = author_project(Path(folder) / "authored")
            source = Path(proof["content_path"])
            game = build_controller(
                content_path=source, campaign_id="main",
                save_dir=Path(folder) / "saves")
            renderer = make_controller(scene_for_player(game))
            bridge = create_bridge(game, renderer)
            engine = QQmlApplicationEngine()
            engine.setInitialProperties({"smokeMode": True})
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("player", bridge)
            engine.load(QUrl.fromLocalFile(str(
                Path(__file__).resolve().parents[1] / "drawtemp/player/Main.qml")))
            self.assertTrue(engine.rootObjects(), "Real Player Main.qml failed to load")
            try:
                bridge.newGame()
                bridge.choose("enter")
                bridge.startMission(MISSION)
                self.assertEqual(renderer.scene["mission"], MISSION)
                self.assertFalse(next(obj for obj in renderer.scene["objects"]
                                      if obj["id"] == "gate").get("open", False))
                bridge.interactObject("lever")
                self.assertEqual(game.state()["scene"]["id"], STORY_ID)
                self.assertTrue(next(obj for obj in renderer.scene["objects"]
                                     if obj["id"] == "gate")["open"])
                bridge.saveGame(1)
                saved = game.session.recording()
                bridge.titleScreen()
                bridge.loadGame(1)
                self.assertEqual(game.session.recording(), saved)
                self.assertEqual(renderer.scene["mission"], MISSION)
                self.assertTrue(next(obj for obj in renderer.scene["objects"]
                                     if obj["id"] == "gate")["open"])
            finally:
                for window in engine.rootObjects():
                    window.close()
                engine.deleteLater()


if __name__ == "__main__":
    unittest.main()

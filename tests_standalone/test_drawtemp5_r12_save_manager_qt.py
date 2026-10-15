"""R12.10 Player Qt bridge: real title, Continue and recovery actions."""
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "PySide6 optional")
class R1210QtBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication(["r1210-qt"])

    def test_continue_autosave_restore_visible_on_real_player_bridge(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        from drawtemp.player.qt_app import (
            build_controller, create_bridge, scene_for_player)
        from drawtemp.render.qt_viewport import make_controller

        with TemporaryDirectory() as folder:
            game = build_controller(save_dir=folder, reference=True)
            renderer = make_controller(scene_for_player(game))
            bridge = create_bridge(game, renderer)
            engine = QQmlApplicationEngine()
            engine.setInitialProperties({"smokeMode": True})
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("player", bridge)
            engine.load(QUrl.fromLocalFile(str(
                Path(__file__).resolve().parents[1] / "drawtemp/player/Main.qml")))
            self.assertTrue(engine.rootObjects(), "R12 QML title failed to load")
            try:
                self.assertFalse(game.state()["save_manager"]["continue_available"])
                bridge.newGame()
                initial = game.session.recording()
                self.assertTrue((Path(folder) / "autosave.json").is_file())
                self.assertEqual(game.state()["save_manager"]["autosave"]["status"], "valid")

                bridge.choose("enter")
                advanced = game.session.recording()
                self.assertNotEqual(initial, advanced)
                bridge.titleScreen()
                self.assertEqual(game.state()["screen"], "title")
                bridge.continueGame()
                self.assertEqual(game.session.recording(), advanced)

                # Never downgrade a valid primary even if its backup exists.
                bridge.titleScreen()
                healthy = (Path(folder) / "autosave.json").read_bytes()
                bridge.restoreAutosaveBackup()
                self.assertEqual((Path(folder) / "autosave.json").read_bytes(),
                                 healthy)
                self.assertEqual(game.session.recording(), advanced)

                # Explicit recovery becomes available after genuine corruption.
                (Path(folder) / "autosave.json").write_bytes(b"broken")
                self.assertEqual(game.state()["save_manager"]["autosave"]["status"],
                                 "invalid")
                bridge.restoreAutosaveBackup()
                self.assertEqual(game.session.recording(), initial)
                self.assertEqual(bridge.view["save_manager"]["autosave"]["status"],
                                 "valid")
                self.assertEqual((Path(folder) / "autosave.json.damaged").read_bytes(),
                                 b"broken")
            finally:
                for item in engine.rootObjects():
                    item.close()
                engine.deleteLater()


if __name__ == "__main__":
    unittest.main()

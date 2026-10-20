"""R41.B3 — actual Qt Quick Player and routed RPG smoke (software only).

Requires a real PySide6 installation. This is NOT a hardware GPU/gamepad gate.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "PySide6 optional; dedicated CI installs Qt")
class R41RoutedQtSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_real_qml_load_routed_encounter_and_resume(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        from drawtemp.player.controller import PlayerController
        from drawtemp.player.qt_app import create_bridge, scene_for_player
        from drawtemp.render.qt_viewport import make_controller
        from tests_standalone.test_r41_routed_encounter import routed_rpg_fixture

        with TemporaryDirectory() as directory:
            content, project = routed_rpg_fixture()
            controller = PlayerController(
                content, project, "main", Path(directory), seed=17)
            controller.new_game()
            renderer = make_controller(scene_for_player(controller))
            bridge = create_bridge(controller, renderer)
            engine = QQmlApplicationEngine()
            renderer.attach_engine(engine)
            engine.setInitialProperties({"smokeMode": True})
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("player", bridge)
            engine.load(QUrl.fromLocalFile(str(
                Path(__file__).resolve().parents[1] /
                "drawtemp/player/Main.qml")))
            self.assertTrue(engine.rootObjects(), "R41 Player QML failed to load")
            self.assertEqual(bridge.view["screen"], "exploration")
            self.assertEqual(bridge.view["rpg_available"], ["sparring"])
            bridge.startRpgEncounter("sparring")
            self.app.processEvents()
            self.assertEqual(bridge.view["screen"], "rpg_battle")
            self.assertEqual(bridge.view["rpg"]["scene"], "inn")
            bridge.rpgAction("guard", "", "")
            self.app.processEvents()
            self.assertEqual(bridge.view["screen"], "rpg_battle")
            bridge.rpgAction("flee", "", "")
            bridge.finishRpgEncounter()
            self.app.processEvents()
            self.assertEqual(bridge.view["screen"], "exploration")
            self.assertEqual(bridge.view["rpg_available"], ["sparring"])
            del engine


if __name__ == "__main__":
    unittest.main()

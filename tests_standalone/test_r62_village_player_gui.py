"""R62.C native Qt Player QML/PlayerBridge smoke on authored farm-village."""
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from tests_standalone.test_r62_village_player import village_fixture
from drawtemp.player.controller import PlayerController


@unittest.skipUnless(find_spec("PySide6"), "PySide6 not installed")
class R62VillagePlayerQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_real_player_qml_farm_harvest_social_and_checkpoint(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        from drawtemp.player.qt_app import create_bridge, scene_for_player
        from drawtemp.render.qt_viewport import make_controller

        content, project = village_fixture()
        with TemporaryDirectory() as folder:
            controller = PlayerController(content, project, "main",
                                          Path(folder), seed=62)
            renderer = make_controller(scene_for_player(controller))
            bridge = create_bridge(controller, renderer)
            engine = QQmlApplicationEngine()
            engine.setInitialProperties({"smokeMode": True})
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("player", bridge)
            engine.load(QUrl.fromLocalFile(str(
                Path(__file__).resolve().parents[1] / "drawtemp/player/Main.qml")))
            self.assertTrue(engine.rootObjects(),
                            "R62 real QML Player failed to construct")
            window = engine.rootObjects()[0]
            try:
                def items(item):
                    if item is None:
                        return
                    yield item
                    for child in item.childItems():
                        yield from items(child)

                def controls():
                    return {item.objectName() for item
                            in items(window.property("contentItem"))
                            if item.objectName()}

                bridge.newGame()
                self.app.processEvents()
                self.assertTrue(controller.state()["village"]["enabled"])
                self.assertIn("r62-village-hud", controls())
                self.assertIn("r62WaitNextDay", controls())
                # These real QML controls call the real bridge slots, never
                # an editor-owned or JavaScript-side simulation.
                controller.session._session.progress.inventory["epee_de_jacques"] = 2
                bridge.stateChanged.emit()
                self.app.processEvents()
                self.assertIn("r62Plant-field-herb_crop", controls())
                bridge.farmPlant("field", "herb_crop")
                bridge.farmWaitDay(1)
                self.assertTrue(controller.state()["village"]["plots"][0]
                                ["can_harvest"])
                bridge.farmHarvest("field")
                self.assertEqual(controller.session.snapshot().progress
                                 ["inventory"]["cape_de_route"], 2)
                bridge.relationshipTalk("traveler")
                self.assertEqual(next(p for p in controller.state()["village"]["people"]
                                      if p["id"] == "traveler")["score"], -1)
                bridge.saveGame(1)
                first = controller.session.recording()
                bridge.titleScreen()
                bridge.loadGame(1)
                self.assertEqual(controller.session.recording(), first)
                self.assertIn("r62Harvest-field", controls())
                self.assertIn("r62Talk-traveler", controls())
            finally:
                window.close()
                engine.deleteLater()


if __name__ == "__main__":
    unittest.main()

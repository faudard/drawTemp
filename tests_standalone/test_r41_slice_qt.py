"""R41.C real original village Qt Quick Player smoke (software/offscreen only).

This verifies the actual QML bridge end-to-end: create, recruit, equipment,
portals, battle, return and quest claim. It does not certify physical GPU,
keyboard layout, gamepads, accessibility or clean-machine distributables.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "Requires optional PySide6 Qt runtime")
class VillageRpgQtSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_genuine_qml_bridge_recruits_travels_fights_and_claims(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        from drawtemp.creator_examples.classic_rpg import build_relais_du_village
        from drawtemp.player.controller import PlayerController
        from drawtemp.player.qt_app import create_bridge, scene_for_player
        from drawtemp.render.qt_viewport import make_controller

        with TemporaryDirectory() as directory:
            content, project = build_relais_du_village()
            controller = PlayerController(
                content, project, "main", Path(directory), seed=37)
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
            self.assertTrue(engine.rootObjects(), "R41.C Player QML failed to load")
            self.assertEqual(bridge.view["title"], "Le relais du village")
            self.assertEqual(bridge.view["screen"], "exploration")
            self.assertEqual(len(bridge.view["party"]["recruitable"]), 2)
            bridge.recruitPartyMember("oren")
            bridge.recruitPartyMember("mira")
            self.app.processEvents()
            self.assertEqual(len(bridge.view["party"]["recruitable"]), 0)
            bridge.togglePartyMember("oren")
            bridge.togglePartyMember("mira")
            self.assertEqual(len(bridge.view["party"]["active"]), 3)
            bridge.equipHero("elya", "lame_relais")
            self.assertEqual(bridge.view["party"]["equipment"]["elya"][
                "weapon"], "lame_relais")
            bridge.travelRoute("village_to_woods")
            self.app.processEvents()
            self.assertEqual(bridge.view["exploration"]["scene_id"], "woods")
            bridge.startRpgEncounter("woods")
            self.app.processEvents()
            self.assertEqual(bridge.view["screen"], "rpg_battle")
            for _ in range(24):
                if bridge.view["rpg"]["result"]:
                    break
                bridge.rpgAction("attack", "loup", "")
            self.assertEqual(bridge.view["rpg"]["result"], "victory")
            bridge.finishRpgEncounter()
            bridge.travelRoute("woods_to_crypt")
            bridge.startRpgEncounter("crypt")
            for _ in range(24):
                if bridge.view["rpg"]["result"]:
                    break
                bridge.rpgAction("attack", "gardien", "")
            self.assertEqual(bridge.view["rpg"]["result"], "victory")
            bridge.finishRpgEncounter()
            bridge.travelRoute("crypt_to_village")
            self.app.processEvents()
            self.assertTrue(bridge.view["rpg_quest"]["ready"])
            bridge.claimRpgQuest()
            self.app.processEvents()
            self.assertTrue(bridge.view["rpg_quest"]["completed"])
            self.assertEqual(bridge.view["screen"], "exploration")
            del engine


if __name__ == "__main__":
    unittest.main()

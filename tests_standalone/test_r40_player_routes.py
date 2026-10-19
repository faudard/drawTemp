"""R40.B.2 real Studio -> Player R25 route -> verified slot -> Qt QML smoke.

This exercises the existing CreatorWizard/AuthoringSession, Simulation,
PlayerController and Qt bridge; it does NOT certify GPU, installed exports,
metroidvania physical double-jump, or four complete game loops.
"""
from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from drawtemp.player.qt_app import build_controller, scene_for_player
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.simulation import SimulationError
from drawtemp.studio.project_wizard import ProjectSpec, create_project


def _project(root, kind):
    content = create_project(ProjectSpec(kind, Path(root) / kind))
    snapshot = AuthoringSession.open(content).snapshot().to_dict()
    assert snapshot["project"]["title"]
    assert snapshot["project"]["scene_routes"]["start"] == "arrival"
    return content


def _player(content, root):
    return build_controller(content_path=content,
                            save_dir=Path(root) / "saves", campaign_id="main")


class R40PlayerRoutesTests(unittest.TestCase):
    def test_real_studio_to_player_three_scenes_with_save_load(self):
        for kind in ("r40-adventure", "r40-metroidvania"):
            with self.subTest(kind=kind), TemporaryDirectory() as folder:
                content = _project(folder, kind)
                player = _player(content, folder)
                view = player.new_game()
                self.assertEqual(view["screen"], "exploration")
                self.assertEqual(view["exploration"]["scene_id"], "arrival")
                self.assertEqual([row["id"] for row in view["routes"]],
                                 ["to_ruins"])
                self.assertFalse(view["routes"][0]["available"])
                self.assertEqual(scene_for_player(player)["width"], 6)
                before = player.session.recording()
                for _ in range(3):
                    self.assertEqual(player.state()["routes"], view["routes"])
                self.assertEqual(player.session.recording(), before)
                with self.assertRaises(SimulationError):
                    player.route_transition("to_ruins")
                self.assertEqual(player.session.recording(), before)
                player.explore_move(1, 0)
                player.explore_interact("waystone")
                self.assertTrue(player.state()["routes"][0]["available"])
                player.route_transition("to_ruins")
                self.assertEqual(player.state()["exploration"]["scene_id"],
                                 "r40_ruins")
                player.save(1)
                restored = _player(content, folder)
                loaded = restored.load(1)
                self.assertEqual(loaded["screen"], "exploration")
                self.assertEqual(loaded["exploration"]["scene_id"], "r40_ruins")
                self.assertEqual([row["id"] for row in loaded["routes"]],
                                 ["back_to_village", "to_citadel"])
                self.assertFalse(loaded["routes"][1]["available"])
                restored.explore_move(1, 0)
                restored.explore_interact("waystone")
                self.assertTrue(restored.state()["routes"][1]["available"])
                restored.route_transition("to_citadel")
                self.assertEqual(restored.state()["exploration"]["scene_id"],
                                 "r40_citadel")
                self.assertEqual(
                    restored.session.recording()["scene_route"]["history"],
                    ["to_ruins", "to_citadel"])
                restored.save(1)
                third = _player(content, folder)
                self.assertEqual(third.load(1)["exploration"]["scene_id"],
                                 "r40_citadel")

    def test_stale_revision_and_route_rejection_are_atomic(self):
        with TemporaryDirectory() as folder:
            path = _project(folder, "r40-adventure")
            player = _player(path, folder)
            player.new_game()
            old_revision = player.state()["revision"]
            player.explore_move(1, 0)
            with self.assertRaises(SimulationError) as error:
                player.session.route_options(expected_revision=old_revision)
            self.assertEqual(error.exception.code, "stale_revision")
            before = player.session.recording()
            with self.assertRaises(SimulationError):
                player.route_transition("to_citadel")
            self.assertEqual(player.session.recording(), before)

    def test_authored_content_player_save_is_bound_to_project(self):
        with TemporaryDirectory() as folder:
            adventure = _project(folder, "r40-adventure")
            metroid = _project(folder, "r40-metroidvania")
            player = _player(adventure, folder)
            player.new_game()
            player.save(1)
            other = _player(metroid, folder)
            with self.assertRaises(Exception):
                other.load(1)
            self.assertIsNone(other.session)
            self.assertEqual(player.load(1)["exploration"]["scene_id"],
                             "arrival")


@unittest.skipUnless(find_spec("PySide6"), "PySide6 not installed")
class R40PlayerQtBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_real_main_qml_bridge_routed_buttons_and_recovery(self):
        from PySide6.QtCore import QObject, QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        from drawtemp.player.qt_app import create_bridge
        from drawtemp.render.qt_viewport import make_controller

        with TemporaryDirectory() as folder:
            path = _project(folder, "r40-adventure")
            controller = _player(path, folder)
            renderer = make_controller(scene_for_player(controller))
            bridge = create_bridge(controller, renderer)
            engine = QQmlApplicationEngine()
            engine.setInitialProperties({"smokeMode": True})
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("player", bridge)
            qml = Path(__file__).resolve().parents[1] / "drawtemp/player/Main.qml"
            engine.load(QUrl.fromLocalFile(str(qml)))
            self.assertTrue(engine.rootObjects(), "Real Qt Player QML failed to load")
            window = engine.rootObjects()[0]
            try:
                bridge.newGame()
                self.app.processEvents()
                self.assertEqual(controller.state()["screen"], "exploration")
                self.assertIsNotNone(
                    window.findChild(QObject, "r40ExploreRoute-to_ruins"))
                bridge.exploreMove(1, 0)
                bridge.exploreInteract("waystone")
                self.assertTrue(controller.state()["routes"][0]["available"])
                bridge.routeTransition("to_ruins")
                self.assertEqual(controller.state()["exploration"]["scene_id"],
                                 "r40_ruins")
                bridge.saveGame(1)
                bridge.titleScreen()
                bridge.loadGame(1)
                self.assertEqual(controller.state()["exploration"]["scene_id"],
                                 "r40_ruins")
                self.assertEqual(renderer.scene["width"], 6)
            finally:
                window.close()
                engine.deleteLater()


if __name__ == "__main__":
    unittest.main()

"""R40.B.5 main Qt Quick Player / canonical physical R32 game integration.

The tests exercise the real R22 wizard, R1 Simulation, R25 SceneRouter,
R32 physics + R33 feather, R40 boss, and existing Player slots. Qt smoke
loads the actual main Main.qml with PlatformViewport (not the R32 standalone).
"""
from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from drawtemp.player.qt_app import build_controller, scene_for_player
from drawtemp.sdk.simulation import SimulationError
from drawtemp.studio.project_wizard import ProjectSpec, create_project
from sporebound.exploration import _key


def _new_player(folder):
    path = create_project(ProjectSpec(
        "r40-metroidvania", Path(folder) / "game"))
    controller = build_controller(
        content_path=path, campaign_id="main",
        save_dir=Path(folder) / "player_saves")
    return path, controller


def _resume(path, folder):
    return build_controller(
        content_path=path, campaign_id="main",
        save_dir=Path(folder) / "player_saves")


def _walk(player, steps):
    for _ in range(steps):
        player.platform_step(move=1)


def _to_citadel(player):
    _walk(player, 8)
    assert "to_ruins" in player.state()["platform"]["state"]["available_routes"]
    player.platform_travel("to_ruins")
    player.platform_step(move=1)
    assert player.session.snapshot().progress["story_flags"]["r33_pickup_feather"]
    _walk(player, 8)
    player.platform_travel("back_to_village")
    assert player.state()["platform"]["state"]["air_jumps_left"] == 1
    _walk(player, 8)
    player.platform_step(move=1, jump=True)
    _walk(player, 4)
    player.platform_step(move=1, jump=True)
    _walk(player, 6)
    assert "high_gate" in player.state()["platform"]["state"]["available_routes"]
    player.platform_travel("high_gate")
    assert player.state()["platform"]["state"]["scene"] == "r40_citadel"


def _fight(player, *, attack=True, max_steps=260):
    _walk(player, 9)
    seen_phases = set()
    for _ in range(max_steps):
        boss = player.state()["platform"]["state"]["boss"]
        seen_phases.add(boss["phase"])
        if boss["defeated"] or boss["player_defeated"]:
            break
        ready = boss["window"] == "recover" and boss["cooldown"] == 0
        player.platform_step(attack=attack and ready)
    else:
        raise AssertionError("Boss did not reach victory/death in deterministic budget")
    return seen_phases, player.state()["platform"]["state"]["boss"]


class MainPlayerPlatformTests(unittest.TestCase):
    def test_pure_view_no_initial_replay_and_physical_travel(self):
        with TemporaryDirectory() as folder:
            path, player = _new_player(folder)
            state = player.new_game()
            self.assertEqual(state["screen"], "platform")
            self.assertEqual(state["platform"]["world"]["id"], "arrival")
            self.assertEqual(state["platform"]["state"]["tick"], 0)
            first = player.session.recording()
            self.assertNotIn("scene_platform", first)
            for _ in range(4):
                self.assertEqual(player.state()["platform"]["state"]["tick"], 0)
            self.assertEqual(player.session.recording(), first)
            with self.assertRaises((SimulationError, ValueError)):
                player.platform_travel("to_ruins")
            with self.assertRaises(ValueError):
                player.explore_move(1, 0)
            with self.assertRaises(ValueError):
                player.explore_interact("waystone")
            self.assertEqual(player.session.recording(), first)
            _walk(player, 8)
            self.assertEqual(player.state()["platform"]["state"]["tick"], 8)
            player.route_transition("to_ruins")
            state = player.state()
            self.assertEqual(state["screen"], "platform")
            self.assertEqual(state["platform"]["state"]["scene"], "r40_ruins")
            player.save(1)
            resumed = _resume(path, folder)
            self.assertEqual(resumed.load(1)["platform"]["state"]["scene"],
                             "r40_ruins")
            self.assertEqual(resumed.session.recording(), player.session.recording())

    def test_main_player_completed_physical_journey_boss_and_verified_slot(self):
        with TemporaryDirectory() as folder:
            path, player = _new_player(folder)
            player.new_game()
            _to_citadel(player)
            player.save(1)
            start = player.state()["platform"]["state"]["boss"]
            self.assertEqual(start["hp"], 4)
            self.assertEqual(start["phase"], 1)
            phases, final = _fight(player)
            self.assertEqual(phases, {1, 2})
            self.assertTrue(final["defeated"])
            self.assertGreater(final["hero_hp"], 0)
            self.assertTrue(player.session.snapshot().progress["story_flags"][
                _key("r40_citadel", "boss_defeated")])
            player.save(1)
            checkpoint = player.session.recording()
            loaded = _resume(path, folder)
            state = loaded.load(1)
            self.assertEqual(state["screen"], "platform")
            self.assertTrue(state["platform"]["state"]["boss"]["defeated"])
            self.assertEqual(loaded.session.recording(), checkpoint)

    def test_boss_loss_and_manual_checkpoint_recovery(self):
        with TemporaryDirectory() as folder:
            path, player = _new_player(folder)
            player.new_game()
            _to_citadel(player)
            player.save(1)
            _, final = _fight(player, attack=False, max_steps=500)
            self.assertTrue(final["player_defeated"])
            self.assertFalse(final["defeated"])
            self.assertNotIn(_key("r40_citadel", "boss_defeated"),
                             player.session.snapshot().progress["story_flags"])
            # PlayerSlotStore load verifies a real pre-fight checkpoint.
            restored = _resume(path, folder)
            checkpoint = restored.load(1)
            self.assertEqual(checkpoint["screen"], "platform")
            self.assertFalse(checkpoint["platform"]["state"]["boss"]["player_defeated"])
            self.assertEqual(checkpoint["platform"]["state"]["boss"]["hero_hp"], 6)

    def test_revision_checked_platform_commands_and_physical_route(self):
        from drawtemp.sdk.simulation import SimulationError
        with TemporaryDirectory() as folder:
            _, player = _new_player(folder)
            player.new_game()
            revision = player.session.snapshot().revision
            original = player.session.recording()
            with self.assertRaises(SimulationError) as bad:
                player.session.platform_step(1, False, False,
                                             expected_revision=revision + 1)
            self.assertEqual(bad.exception.code, "stale_revision")
            self.assertEqual(player.session.recording(), original)
            with self.assertRaises(SimulationError):
                player.session.route_transition("to_ruins",
                                                 expected_revision=revision)
            self.assertEqual(player.session.recording(), original)
            player.platform_step(move=1)
            with self.assertRaises(SimulationError) as stale:
                player.session.platform_travel("to_ruins",
                                                expected_revision=revision)
            self.assertEqual(stale.exception.code, "stale_revision")
            self.assertEqual(player.state()["platform"]["state"]["tick"], 1)

    def test_fixed_tick_game_state_is_independent_of_render_polling(self):
        with TemporaryDirectory() as folder:
            _, player = _new_player(folder)
            player.new_game()
            for _ in range(8):
                player.platform_step(move=1)
            target = player.session.recording()
            _, other = _new_player(Path(folder) / "independent")
            other.new_game()
            for _ in range(8):
                other.platform_step(move=1)
                for _ in range(5):
                    other.state()
            self.assertEqual(other.session.recording(), target)


@unittest.skipUnless(find_spec("PySide6"), "PySide6 not installed")
class MainPlayerPlatformQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_main_qml_embeds_real_platform_viewport_and_bridge(self):
        from PySide6.QtCore import QObject, QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        from drawtemp.player.qt_app import create_bridge
        from drawtemp.render.qt_viewport import make_controller

        with TemporaryDirectory() as folder:
            _, controller = _new_player(folder)
            renderer = make_controller(scene_for_player(controller))
            bridge = create_bridge(controller, renderer)
            engine = QQmlApplicationEngine()
            engine.setInitialProperties({"smokeMode": True})
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("player", bridge)
            qml = Path(__file__).resolve().parents[1] / "drawtemp/player/Main.qml"
            engine.load(QUrl.fromLocalFile(str(qml)))
            self.assertTrue(engine.rootObjects(), "Actual Player Main.qml did not load")
            window = engine.rootObjects()[0]
            try:
                bridge.newGame()
                self.app.processEvents()
                self.assertEqual(controller.state()["screen"], "platform")
                self.assertIsNotNone(
                    window.findChild(QObject, "r40PlatformViewport"))
                self.assertIsNotNone(
                    window.findChild(QObject, "r40PlatformCanvas"))
                self.assertIsNotNone(
                    window.findChild(QObject, "r40PlatformStatus"))
                self.assertIsNotNone(
                    window.findChild(QObject, "r40PlatformAttack"))
                bridge.platformStep(1, False, False)
                self.app.processEvents()
                self.assertEqual(
                    controller.state()["platform"]["state"]["tick"], 1)
                bridge.saveGame(1)
                bridge.titleScreen()
                bridge.loadGame(1)
                self.assertEqual(
                    controller.state()["platform"]["state"]["tick"], 1)
            finally:
                window.close()
                engine.deleteLater()


if __name__ == "__main__":
    unittest.main()

"""R27.C full Qt Player QML smoke with authored puzzle and real bridge.

Software offscreen verifies instantiation/bindings/action routing; it does NOT
certify GPU output, human accessibility or action-adventure scene transfers.
"""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests_standalone.test_drawtemp5_r27c_player import (
    authored_puzzle, playing_player,
)


@unittest.skipUnless(os.environ.get("DRAWTEMP_R27C_QT_SMOKE") == "1",
                     "Explicit offscreen QML smoke only")
class PuzzleQtPlayerSmoke(unittest.TestCase):
    def test_actual_qml_renders_puzzle_and_bridge_commits_key(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
        from drawtemp.player.qt_app import create_bridge, scene_for_player
        from drawtemp.render.qt_viewport import make_controller

        app = QGuiApplication.instance() or QGuiApplication([])
        with TemporaryDirectory() as directory:
            content, project = authored_puzzle()
            controller = playing_player(content, project, directory)
            scene = scene_for_player(controller)
            renderer = make_controller(scene)
            bridge = create_bridge(controller, renderer)
            engine = QQmlApplicationEngine()
            renderer.attach_engine(engine)
            engine.setInitialProperties({"smokeMode": True})
            engine.rootContext().setContextProperty("renderer", renderer)
            engine.rootContext().setContextProperty("player", bridge)
            engine.load(QUrl.fromLocalFile(str(
                Path(__file__).resolve().parents[1] /
                "drawtemp/player/Main.qml")))
            self.assertTrue(engine.rootObjects(), "Player Main.qml failed")
            self.assertEqual(bridge.view["screen"], "battle")
            self.assertTrue(bridge.view["puzzle"]["enabled"])
            self.assertTrue(any(row["enabled"] for row
                                in bridge.view["puzzle"]["actions"]))
            bridge.puzzleAction("amber_key")
            app.processEvents()
            self.assertTrue(next(o for o in renderer.scene["objects"]
                                 if o["id"] == "amber_key")["used"])
            self.assertTrue(next(o for o in bridge.view["battle"]["objects"]
                                 if o["id"] == "amber_key")["used"])
            self.assertFalse(controller.autosave_warning,
                             controller.autosave_warning)
            del engine


if __name__ == "__main__":
    unittest.main()

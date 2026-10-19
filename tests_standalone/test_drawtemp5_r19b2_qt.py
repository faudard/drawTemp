"""R19.B2: real Qt renderer / TacticalBoard with canonical R7 art (optional)."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import os
import unittest

HAS_QT = importlib.util.find_spec("PySide6") is not None
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_QT, "Optional PySide6 Qt6 integration")
class R19QtVisualClipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["drawtemp-r19b2"])

    def test_real_r7_pack_and_qml_single_actor_clip(self):
        from PySide6.QtCore import QUrl, QObject
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtTest import QTest
        from drawtemp.assets.characters import export_pack, starter_library
        from drawtemp.render.qt_viewport import make_controller

        with TemporaryDirectory() as folder:
            pack = Path(folder) / "r7"
            export_pack(starter_library()["jeanne"], ROOT, pack)
            scene = {
                "mission": "r19b2", "revision": 0, "width": 4, "height": 4,
                "tiles": [
                    {"x": x, "y": y, "height": 0, "surface": "grass",
                     "feature": "", "blocked": False, "cover": 0,
                     "hazard": 0, "goal": False}
                    for x in range(4) for y in range(4)
                ],
                "actors": [
                    {"id": "jeanne", "name": "Jeanne", "x": 1, "y": 1,
                     "level": 0, "team": "player", "alive": True,
                     "direction": "west"}
                ],
                "objects": [],
            }
            renderer = make_controller(scene, character_pack=pack)
            renderer._sprite_timer.stop()
            attack = {"actor": "jeanne", "kind": "attack",
                      "team": "player", "start": [1, 1], "end": [2, 1],
                      "duration_ms": 430}
            first = renderer.visualClipFrame(attack, 0)
            last = renderer.visualClipFrame(attack, 1)
            self.assertEqual(first["source"], "character_pack")
            self.assertEqual(first["direction"], "east")
            self.assertEqual(first["pose"], "attack")
            self.assertEqual(first["pivotY"], 63)
            self.assertNotEqual(first["atlasY"], last["atlasY"])
            self.assertFalse(renderer.visualClipFrame(
                {**attack, "kind": "cast"}, 0))
            self.assertFalse(renderer.visualClipFrame(
                {**attack, "actor": "unknown"}, 0))

            board = QQuickWidget()
            try:
                board.setResizeMode(QQuickWidget.SizeRootObjectToView)
                board.rootContext().setContextProperty("renderer", renderer)
                board.resize(800, 600)
                board.setSource(QUrl.fromLocalFile(str(
                    ROOT / "drawtemp/render/TacticalBoard.qml")))
                self.assertNotEqual(board.status(), QQuickWidget.Error,
                                    "\n".join(str(e) for e in board.errors()))
                root = board.rootObject()
                self.assertIsNotNone(root)
                board.show()

                def variant(value):
                    return value.toVariant() if hasattr(value, "toVariant") else value

                root.setProperty("animationPlan", {
                    "serial": 1, "revision": 1, "scene": "r19b2",
                    "clips": [attack],
                })
                QTest.qWait(50)
                ghost = root.findChild(QObject, "r12-motion-ghost")
                sprite = root.findChild(QObject, "r12-action-sprite")
                self.assertIsNotNone(ghost)
                self.assertIsNotNone(sprite)
                self.assertTrue(ghost.property("visible"))
                self.assertTrue(ghost.property("hasArt"))
                self.assertEqual(variant(ghost.property("sprite"))["source"],
                                 "character_pack")
                self.assertIn("jeanne", variant(root.property("concealedActorIds")))
                self.assertTrue(sprite.property("visible"))

                # A newly committed plan invalidates an old transition
                # immediately and cannot conceal the actor without a clip.
                root.setProperty("animationPlan", {
                    "serial": 2, "revision": 2, "scene": "r19b2",
                    "clips": [],
                })
                QTest.qWait(25)
                self.assertFalse(root.property("playing"))
                self.assertEqual(variant(root.property("concealedActorIds")), [])
            finally:
                board.close()

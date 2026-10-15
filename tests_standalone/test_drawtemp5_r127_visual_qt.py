"""R12.7 real Qt Quick screenshot/pose certification, no generated golden.

Art screenshots are CI *candidates* for human review, not auto-approved
baselines. The runtime must render the packaged Jeanne sheet without fake
sprites or a parallel renderer.
"""
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "Qt extra not installed")
class R127VisualQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["r127-visual"])

    def test_actual_sprite_motion_attack_hit_and_cancellation(self):
        from PySide6.QtCore import QObject, QUrl
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtTest import QTest
        from drawtemp.assets.runtime import PresentationAssets
        from drawtemp.player.qt_app import build_controller, scene_for_player
        from drawtemp.render.qt_viewport import make_controller

        with TemporaryDirectory() as directory:
            game = build_controller(save_dir=directory)
            game.new_game()
            recording = game.session.recording()
            assets = PresentationAssets.for_project(game.project,
                                                    game.asset_project_path)
            renderer = make_controller(scene_for_player(game), assets=assets)
            self.assertTrue(renderer.animatedAssets)
            jeanne = next(row for row in renderer.items
                          if row["kind"] == "actor" and row["id"] == "jeanne")
            self.assertEqual(jeanne["assetId"], "jeanne_south_idle_0")
            self.assertIn("jeanne_atlas.png", jeanne["imageUrl"])

            board = QQuickWidget()
            board.setResizeMode(QQuickWidget.SizeRootObjectToView)
            board.rootContext().setContextProperty("renderer", renderer)
            board.resize(960, 640)
            board.setSource(QUrl.fromLocalFile(str(
                Path(__file__).resolve().parents[1] /
                "drawtemp/render/TacticalBoard.qml")))
            self.assertNotEqual(board.status(), QQuickWidget.Error,
                                "\n".join(str(e) for e in board.errors()))
            root = board.rootObject()
            self.assertIsNotNone(root)
            root.setProperty("battle", {})
            board.show()
            captures = {}
            artifact_dir = os.environ.get("DRAWTEMP_R127_ARTIFACT_DIR")
            out = Path(artifact_dir) if artifact_dir else None

            def snapshot(label):
                QTest.qWait(90)
                frame = board.grabFramebuffer()
                self.assertFalse(frame.isNull(), "Empty R12.7 visual frame: " + label)
                self.assertEqual((frame.width(), frame.height()), (960, 640))
                if out:
                    out.mkdir(parents=True, exist_ok=True)
                    path = out / ("r127-" + label + ".png")
                    self.assertTrue(frame.save(str(path), "PNG"))
                    captures[label] = path.name

            def plan(serial, kind, start, end, duration=600):
                root.setProperty("animationPlan", {
                    "serial": serial,
                    "revision": serial,
                    "scene": "exploration:jeanne",
                    "clips": [{
                        "kind": kind, "actor": "jeanne", "team": "player",
                        "start": start, "end": end, "duration_ms": duration,
                        "amount": 7 if kind == "impact" else None,
                        "skill": "attack" if kind == "attack" else "",
                    }],
                })
                QTest.qWait(25)
                self.assertTrue(root.property("playing"))
                self.assertEqual(root.property("currentClip")["kind"], kind)
                ghost = root.findChild(QObject, "r12-motion-ghost")
                sprite = root.findChild(QObject, "r12-action-sprite")
                self.assertIsNotNone(ghost)
                self.assertIsNotNone(sprite)
                self.assertTrue(ghost.property("hasArt"))
                frame = ghost.property("sprite")
                self.assertIn("jeanne_atlas.png", frame["imageUrl"])
                self.assertTrue(sprite.property("visible"))
                self.assertIn("jeanne", root.property("concealedActorIds"))
                return frame

            try:
                snapshot("idle")
                frame = plan(1, "move", [1, 5], [2, 5])
                self.assertEqual(frame["assetId"], "jeanne_east_move_0")
                snapshot("move")
                frame = plan(2, "attack", [1, 5], [2, 5])
                self.assertEqual(frame["assetId"], "jeanne_east_attack_0")
                snapshot("attack")
                frame = plan(3, "impact", [1, 5], [1, 5])
                self.assertEqual(frame["assetId"], "jeanne_south_hit_0")
                snapshot("impact")

                root.setProperty("animationPlan", {
                    "serial": 4, "revision": 0, "scene": "", "clips": []})
                QTest.qWait(35)
                self.assertFalse(root.property("playing"))
                self.assertEqual(root.property("concealedActorIds"), [])
                snapshot("restored")
                self.assertEqual(recording, game.session.recording())
                self.assertEqual(renderer.scene["actors"][0]["id"], "jeanne")
                if out:
                    (out / "r127-capture-manifest.json").write_text(
                        json.dumps({"art_source": jeanne["imageUrl"],
                                    "frames": captures, "review": "pending",
                                    "baseline_approved": False},
                                   indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
            finally:
                board.hide()
                board.deleteLater()


if __name__ == "__main__":
    unittest.main()

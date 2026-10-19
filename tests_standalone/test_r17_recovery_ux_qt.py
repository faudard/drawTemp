"""R17.11 real Qt Quick Player recovery UI and error actions (software smoke)."""
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "PySide6 optional")
class RecoveryQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        cls.app = QGuiApplication.instance() or QGuiApplication(["r17-recovery"])

    def setup_player(self, folder):
        from PySide6.QtCore import QObject, QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        from drawtemp.player.qt_app import (
            build_controller, create_bridge, scene_for_player)
        from drawtemp.render.qt_viewport import make_controller
        game = build_controller(save_dir=folder, reference=True)
        bridge = create_bridge(game, make_controller(scene_for_player(game)))
        engine = QQmlApplicationEngine()
        engine.setInitialProperties({"smokeMode": True})
        engine.rootContext().setContextProperty("renderer", bridge.renderer)
        engine.rootContext().setContextProperty("player", bridge)
        engine.load(QUrl.fromLocalFile(str(
            Path(__file__).resolve().parents[1] / "drawtemp/player/Main.qml")))
        self.assertTrue(engine.rootObjects(), "Real Player QML failed to load")
        root = engine.rootObjects()[0]
        self.assertIsNotNone(root.findChild(QObject, "r17RecoveryDialog"))
        self.assertIsNotNone(root.findChild(QObject, "r17ConfirmRecovery"))
        self.assertIsNotNone(root.findChild(QObject, "r17CancelRecovery"))
        self.assertIsNotNone(root.findChild(QObject, "r17RecoveryError"))
        self.assertIsNotNone(root.findChild(QObject, "r17RequestManualRecovery"))
        self.assertIsNotNone(root.findChild(QObject, "r17RequestAutosaveRecovery"))
        return game, bridge, engine

    def test_cancel_stale_then_explicit_autosave_restore(self):
        with TemporaryDirectory() as folder:
            game, bridge, engine = self.setup_player(folder)
            try:
                bridge.newGame()
                old = game.session.recording()
                bridge.choose("enter")
                live = game.session.recording()
                auto = Path(folder) / "autosave.json"
                backup = Path(folder) / "autosave.json.bak"
                auto.write_bytes(b"invalid primary 1")
                old_backup = backup.read_bytes()
                bridge.titleScreen()

                bridge.requestRecovery(0)
                self.assertTrue(bridge.recoveryOffer["pending"])
                self.assertEqual(bridge.recoveryOffer["source"], 0)
                self.assertEqual(auto.read_bytes(), b"invalid primary 1")
                bridge.cancelRecovery()
                self.assertFalse(bridge.recoveryOffer["pending"])
                self.assertEqual(game.session.recording(), live)

                bridge.requestRecovery(0)
                auto.write_bytes(b"externally changed primary")
                bridge.confirmRecovery()
                self.assertFalse(bridge.recoveryOffer["pending"])
                self.assertEqual(bridge.recoveryNotice["code"], "stale_recovery")
                self.assertEqual(auto.read_bytes(), b"externally changed primary")
                self.assertEqual(backup.read_bytes(), old_backup)
                self.assertEqual(game.session.recording(), live)
                self.assertFalse(auto.with_suffix(".json.damaged").exists())

                bridge.dismissRecoveryNotice()
                bridge.requestRecovery(0)
                self.assertTrue(bridge.recoveryOffer["pending"])
                bridge.confirmRecovery()
                self.assertFalse(bridge.recoveryOffer["pending"])
                self.assertFalse(bridge.recoveryNotice.get("active", False))
                self.assertEqual(game.session.recording(), old)
                self.assertEqual(auto.read_bytes(), old_backup)
                self.assertEqual(auto.with_suffix(".json.damaged").read_bytes(),
                                 b"externally changed primary")
            finally:
                for window in engine.rootObjects():
                    window.close()
                engine.deleteLater()

    def test_write_failure_displays_disk_action_without_changing_live_game(self):
        with TemporaryDirectory() as folder:
            game, bridge, engine = self.setup_player(folder)
            try:
                bridge.newGame()
                expected = game.session.recording()
                with patch.object(game, "save", side_effect=OSError("disk full")):
                    bridge.saveGame(1)
                self.assertTrue(bridge.recoveryNotice["active"])
                self.assertEqual(bridge.recoveryNotice["code"], "io_error")
                self.assertIn("espace", bridge.recoveryNotice["advice"].lower())
                self.assertEqual(game.session.recording(), expected)
                self.assertFalse((Path(folder) / "slot_1.json").exists())
            finally:
                for window in engine.rootObjects():
                    window.close()
                engine.deleteLater()

    def test_manual_valid_save_cannot_be_downgraded_and_failure_shows_action(self):
        with TemporaryDirectory() as folder:
            game, bridge, engine = self.setup_player(folder)
            try:
                bridge.newGame()
                bridge.saveGame(1)
                bridge.choose("enter")
                bridge.saveGame(1)
                slot = Path(folder) / "slot_1.json"
                before = slot.read_bytes()
                live = game.session.recording()
                bridge.titleScreen()
                bridge.requestRecovery(1)
                self.assertFalse(bridge.recoveryOffer["pending"])
                self.assertEqual(bridge.recoveryNotice["code"], "primary_valid")
                self.assertIn("sauvegarde", bridge.recoveryNotice["advice"].lower())
                self.assertEqual(slot.read_bytes(), before)
                self.assertEqual(game.session.recording(), live)
                bridge.dismissRecoveryNotice()
                self.assertFalse(bridge.recoveryNotice.get("active", False))
            finally:
                for window in engine.rootObjects():
                    window.close()
                engine.deleteLater()


if __name__ == "__main__":
    unittest.main()

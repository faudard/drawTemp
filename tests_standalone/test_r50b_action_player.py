"""R50.B graphical Player: same R26 rules and canonical GameSession slot."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.player.r50b_action_controller import (
    R50BActionController, load_authored_action_pair,
)
from drawtemp.studio.r50b_action import author_action_prototype
from sporebound.model import RuleError


class R50BActionPlayerTests(unittest.TestCase):
    def setUp(self):
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.content_path = author_action_prototype(self.root / "project")
        self.content, self.project = load_authored_action_pair(self.content_path)
        self.profile = self.root / "profile.json"

    def _new(self):
        return R50BActionController(
            self.content, self.project, self.profile, new=True)

    def _defeat(self, ui):
        ui.step(1, 0, attack=True)
        for _ in range(11):
            ui.step(0, 0, guard=True)
        ui.step(0, 0, attack=True)
        self.assertEqual(ui.state()["enemies"]["guard_wolf"]["hp"], 0)

    def test_view_is_read_only_and_commands_use_canonical_slot(self):
        ui = self._new()
        baseline = ui.player.session.recording()
        state = ui.state()
        self.assertEqual(state["mode"], "campaign")
        self.assertEqual(state["tick"], 0)
        self.assertFalse(state["can_settle"])
        self.assertEqual(state["campaign_gold"],
                         ui.player.session.progress.gold)
        detached = ui.state()
        detached["hero"]["hp"] = 0
        detached["campaign_gold"] = -1
        self.assertEqual(ui.player.session.recording(), baseline)
        ui.step(1, 0, attack=True)
        committed = ui.player.session.recording()
        self.assertEqual(committed["scene_action"]["runtime"]["commands"][0]
                         ["attack"], True)
        self.assertEqual(ui.state()["tick"], 1)
        ui.save()
        self.assertEqual(ui.player.session.recording(), committed)
        resumed = R50BActionController(
            self.content, self.project, self.profile)
        self.assertEqual(resumed.player.session.recording(), committed)
        resumed.step(0, 0, guard=True)
        self.assertEqual(resumed.state()["tick"], 2)
        self.assertNotEqual(resumed.player.session.recording(), committed)
        ui.load()
        self.assertEqual(ui.player.session.recording(),
                         resumed.player.session.recording())

    def test_pause_blocked_tick_and_failed_rename_do_not_touch_slot(self):
        ui = self._new()
        before = ui.player.session.recording()
        slot = ui.player.path_for("main", 1)
        saved = slot.read_bytes()
        ui.toggle_pause()
        self.assertTrue(ui.state()["paused"])
        with self.assertRaises(RuleError):
            ui.step(1, 0, attack=True)
        ui.toggle_pause()
        with self.assertRaises(RuleError):
            ui.step(2, 0, attack=True)
        self.assertEqual(ui.player.session.recording(), before)
        self.assertEqual(slot.read_bytes(), saved)
        with self.assertRaises(RuleError):
            ui.respawn()
        self.assertEqual(slot.read_bytes(), saved)
        with self.assertRaises(RuleError):
            R50BActionController(
                self.content, self.project, self.profile, new=True)
        self.assertEqual(slot.read_bytes(), saved)

    def test_action_victory_ct_handoff_and_return_survive_qt_facade_reload(self):
        ui = self._new()
        with self.assertRaises(RuleError):
            ui.settle()
        start_gold = ui.state()["campaign_gold"]
        self._defeat(ui)
        self.assertTrue(ui.state()["can_settle"])
        ui.settle()
        self.assertEqual(ui.state()["mode"], "battle")
        self.assertEqual(ui.state()["campaign_gold"], start_gold + 1)
        after_settlement = ui.player.session.recording()
        self.assertEqual(len(after_settlement["scene_action_history"]), 1)
        reader = R50BActionController(self.content, self.project, self.profile)
        self.assertEqual(reader.player.session.recording(), after_settlement)
        with self.assertRaises(RuleError):
            reader.step(0, 0, attack=True)
        reader.return_from_ct()
        self.assertTrue(reader.state()["settled"])
        self.assertEqual(reader.state()["mode"], "campaign")
        self.assertFalse(reader.state()["can_settle"])
        self.assertEqual(reader.state()["campaign_gold"], start_gold + 1)
        after_return = reader.player.session.recording()
        reader.load()
        self.assertEqual(reader.player.session.recording(), after_return)
        with self.assertRaises(RuleError):
            reader.step(0, 0, attack=True)
        with self.assertRaises(RuleError):
            reader.settle()
        self.assertEqual(reader.player.session.recording(), after_return)

    def test_rejected_ct_return_keeps_combat_and_checkpoint(self):
        ui = self._new()
        before = ui.player.session.recording()
        with self.assertRaises(RuleError):
            ui.return_from_ct()
        self.assertEqual(ui.player.session.recording(), before)
        self._defeat(ui)
        ui.settle()
        old = ui.player.session.recording()
        slot = ui.player.path_for("main", 1)
        bytes_before = slot.read_bytes()
        with self.assertRaises(RuleError):
            ui.player.route_abandon_ct("does_not_exist")
        self.assertEqual(ui.player.session.recording(), old)
        self.assertEqual(slot.read_bytes(), bytes_before)

    def test_renderer_source_is_game_session_runtime(self):
        from drawtemp.render.iso_scene import scene_from_action
        ui = self._new()
        ui.step(1, 0, attack=True)
        self.assertIs(ui.runtime, ui.player.session._action)
        projected = scene_from_action(ui.runtime)
        self.assertEqual(projected["revision"], 1)
        self.assertIn("hero", [a["id"] for a in projected["actors"]])
        self.assertEqual(ui.player.session.recording()["scene_action"]
                         ["runtime"]["commands"][0]["dx"], 1)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class R50BQtPlayerSmokeTests(unittest.TestCase):
    def test_studio_only_launches_action_prototype_and_preserves_slots(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from drawtemp.studio.r50b_catalog_qt import R50CatalogWidget
        from drawtemp.player.r50b_action_controller import (
            load_authored_action_pair,
        )
        application = QApplication.instance() or QApplication([])
        widget = R50CatalogWidget()
        self.addCleanup(widget.close)
        with TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "private-profile.json"
            widget.parent_folder.setText(str(root))
            widget.genre.setCurrentIndex(
                widget.genre.findData("action_adventure"))
            self.assertFalse(widget.play_button.isEnabled())
            widget.genre.setCurrentIndex(
                widget.genre.findData("action_combat_prototype"))
            self.assertFalse(widget.play_button.isEnabled())
            widget.create()
            self.assertTrue(widget.play_button.isEnabled())
            path = widget._created["action_combat_prototype"]
            with patch(
                    "drawtemp.player.r50b_action_app._default_profile",
                    return_value=profile), patch(
                    "drawtemp.studio.r50b_catalog_qt.subprocess.Popen") as launch:
                widget.play_created()
                launch.assert_called_once()
                command = launch.call_args.args[0]
                self.assertIn("--content", command)
                self.assertIn(str(path), command)
                self.assertIn("--new", command)
                content, project = load_authored_action_pair(path)
                R50BActionController(content, project, profile, new=True)
                launch.reset_mock()
                widget.play_created()
                next_command = launch.call_args.args[0]
                self.assertNotIn("--new", next_command)
            self.assertTrue(
                (profile.with_name(profile.stem + "_session_saves")
                 / "main" / "slot_1.json").is_file())

    def test_real_qml_root_loads_offscreen_with_isolated_profile(self):
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        path = author_action_prototype(Path(root.name) / "game")
        env = dict(os.environ)
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["QT_QUICK_BACKEND"] = "software"
        job = subprocess.run(
            [sys.executable, "-m", "drawtemp.player.r50b_action_app",
             "--content", str(path), "--smoke"],
            env=env, capture_output=True, text=True, timeout=35,
            check=False,
        )
        self.assertEqual(job.returncode, 0,
                         job.stdout[-1400:] + "\n" + job.stderr[-2800:])


if __name__ == "__main__":
    unittest.main()

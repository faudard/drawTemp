"""R8.14-R8.16: opt-in Player, explicit recovery and single-writer gates."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.player_app import PlayerApplication
from sporebound.player_controller import PlayerController
from sporebound.long_session import LongSessionStore
from sporebound.session_lock import session_writer_lock


class LongSessionPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)
        cls.project = GameProject.load(
            Path(DEFAULT_CONTENT).with_suffix(".game.json"), cls.content)

    def controller(self, folder):
        return PlayerController(self.content, self.project,
                                Path(folder) / "profile")

    def test_opt_in_is_distinct_from_v2_without_overwriting_original(self):
        with TemporaryDirectory() as root:
            ui = self.controller(root)
            ui.new_game("relique", 1, seed=13)
            ui.choose_story_option("guard")
            old = ui.store().path
            previous = old.read_bytes()
            ui.new_long_game("relique", 1, seed=13)
            self.assertTrue(ui.long_mode)
            self.assertNotEqual(ui.long_path_for("relique", 1), old)
            self.assertEqual(old.read_bytes(), previous)
            ui.choose_story_option("guard")
            self.assertTrue(ui.long_store().journal.is_file())
            self.assertEqual(old.read_bytes(), previous)
            reloaded = self.controller(root)
            reloaded.load_game("relique", 1)
            self.assertFalse(reloaded.long_mode)
            self.assertEqual(reloaded.session.progress, ui.session.progress)
            reloaded.load_long_game("relique", 1)
            self.assertTrue(reloaded.long_mode)
            self.assertEqual(reloaded.session.recording(), ui.session.recording())
            with self.assertRaises(RuleError):
                reloaded.new_long_game("relique", 1)

    def test_migration_retains_original_bytes_and_uses_new_slot(self):
        with TemporaryDirectory() as root:
            ui = self.controller(root)
            ui.new_game("relique", 1)
            ui.choose_story_option("guard")
            previous = ui.store().path.read_bytes()
            old_record = ui.session.recording()
            ui.migrate_to_long_game("relique", 1)
            self.assertEqual(ui.store().path.read_bytes(), previous)
            # Conversion does not silently switch the active slot.
            self.assertFalse(ui.long_mode)
            reloaded = self.controller(root)
            reloaded.load_long_game("relique", 1)
            self.assertEqual(reloaded.session.recording(), old_record)
            self.assertEqual(ui.store().path.read_bytes(), previous)
            with self.assertRaises(RuleError):
                ui.migrate_to_long_game("relique", 1)

    def test_repeated_long_actions_replay_without_duplicate_story_choice(self):
        with TemporaryDirectory() as root:
            ui = self.controller(root)
            ui.new_long_game("relique", 1, seed=7)
            ui.choose_story_option("guard")
            original = ui.session.recording()
            reloaded = self.controller(root)
            reloaded.load_long_game("relique", 1)
            self.assertEqual(reloaded.session.recording(), original)
            self.assertEqual(len(reloaded.session.progress.story_history), 1)
            reloaded.choose_story_option("provisions")
            self.assertEqual(len(reloaded.session.progress.story_history), 2)
            self.assertEqual(self.controller(root).load_long_game(
                "relique", 1).recording(), reloaded.session.recording())

    def test_partial_write_rolls_back_player_state(self):
        with TemporaryDirectory() as root:
            ui = self.controller(root)
            ui.new_long_game("relique", 1)
            before = ui.session.recording()
            journal = ui.long_store().journal
            unchanged = journal.read_bytes()
            with patch("sporebound.long_session.write_json",
                       side_effect=OSError("injected write error")):
                with self.assertRaisesRegex(OSError, "injected"):
                    ui.choose_story_option("guard")
            self.assertEqual(ui.session.recording(), before)
            self.assertEqual(journal.read_bytes(), unchanged)
            self.assertFalse(ui.long_path_for("relique", 1).with_name(
                "slot_1.long.json.lock").exists())

    def test_explicit_backup_restoration_requires_correct_digest(self):
        with TemporaryDirectory() as root:
            ui = self.controller(root)
            ui.new_long_game("relique", 1)
            before = ui.session.recording()
            ui.choose_story_option("guard")
            ui.save()  # compacts journal, retaining initial backup
            path = ui.long_path_for("relique", 1)
            path.write_bytes(b"{bad file")
            check = self.controller(root)
            candidate = check.inspect_long_game("relique", 1)
            self.assertEqual(candidate.source, "backup")
            self.assertTrue(candidate.degraded)
            self.assertEqual(candidate.session.recording(), before)
            with self.assertRaisesRegex(RuleError, "Recovery"):
                check.restore_long_game(
                    "relique", 1, expected_digest="0" * 64)
            with self.assertRaisesRegex(RuleError, "explicitly confirmed"):
                check.load_long_game("relique", 1)
            restored = check.restore_long_game(
                "relique", 1,
                expected_digest=candidate.session.recording()["digest"])
            self.assertEqual(restored.source, "primary")
            self.assertEqual(path.with_name(path.name + ".damaged").read_bytes(),
                             b"{bad file")
            check.load_long_game("relique", 1)
            self.assertEqual(check.session.recording(), before)

    def test_stale_recovery_preview_cannot_overwrite_newer_primary(self):
        with TemporaryDirectory() as root:
            ui = self.controller(root)
            ui.new_long_game("relique", 1)
            ui.choose_story_option("guard")
            ui.save()
            ui.long_path_for("relique", 1).write_bytes(b"{")
            other = self.controller(root)
            old = other.inspect_long_game("relique", 1)
            other.restore_long_game(
                "relique", 1,
                expected_digest=old.session.recording()["digest"])
            before = other.long_path_for("relique", 1).read_bytes()
            with self.assertRaisesRegex(RuleError, "stale"):
                LongSessionStore(other.long_path_for("relique", 1)).restore(
                    old, expected_digest=old.session.recording()["digest"])
            self.assertEqual(other.long_path_for("relique", 1).read_bytes(),
                             before)

    def test_lock_refuses_concurrent_writes_and_never_steals(self):
        with TemporaryDirectory() as root:
            ui = self.controller(root)
            ui.new_long_game("relique", 1)
            path = ui.long_path_for("relique", 1)
            before = ui.session.recording()
            with session_writer_lock(path):
                lock = path.with_name(path.name + ".lock")
                self.assertTrue(lock.exists())
                with self.assertRaisesRegex(RuleError, "Concurrent"):
                    ui.choose_story_option("guard")
                self.assertEqual(before, ui.session.recording())
            self.assertFalse(lock.exists())
            ui.choose_story_option("guard")
            self.assertFalse(lock.exists())
            lock.write_text('{"pid": 999999}', encoding="utf-8")
            try:
                with self.assertRaisesRegex(RuleError, "stale"):
                    ui.choose_story_option("provisions")
                self.assertTrue(lock.exists())
            finally:
                lock.unlink()

    def test_rejected_migration_does_not_create_long_slot(self):
        with TemporaryDirectory() as root:
            ui = self.controller(root)
            ui.new_game("relique", 1)
            original = ui.store().path.read_bytes()
            with self.assertRaises(RuleError):
                ui.migrate_to_long_game("main", 1)
            self.assertEqual(ui.store().path.read_bytes(), original)
            self.assertFalse(ui.long_path_for("main", 1).exists())

    def test_orphaned_damaged_evidence_blocks_reuse_of_slot(self):
        with TemporaryDirectory() as root:
            ui = self.controller(root)
            path = ui.long_path_for("relique", 1)
            path.parent.mkdir(parents=True)
            evidence = path.with_name(path.name + ".damaged")
            evidence.write_bytes(b"recover me first")
            with self.assertRaisesRegex(RuleError, "recovery evidence"):
                ui.new_long_game("relique", 1)
            self.assertEqual(evidence.read_bytes(), b"recover me first")
            self.assertFalse(path.exists())

    def test_player_ui_never_restores_or_switches_when_user_cancels(self):
        with TemporaryDirectory() as root:
            ui = self.controller(root)
            ui.new_long_game("relique", 1)
            ui.choose_story_option("guard")
            ui.save()
            ui.long_path_for("relique", 1).write_bytes(b"{")
            app = PlayerApplication.__new__(PlayerApplication)
            app.player = self.controller(root)
            app.campaign_var = SimpleNamespace(get=lambda: "relique")
            app.slot_var = SimpleNamespace(get=lambda: "1")
            app.long_save_var = SimpleNamespace(get=lambda: True)
            app.messagebox = SimpleNamespace(
                askyesno=MagicMock(return_value=False),
                showwarning=MagicMock())
            app.show = MagicMock()
            app._acknowledge_loaded_tactical_cinematics = MagicMock()
            app._load_game()
            app.messagebox.askyesno.assert_called_once()
            self.assertIsNone(app.player.session)
            app.show.assert_not_called()
            self.assertEqual(app.player.long_path_for(
                "relique", 1).read_bytes(), b"{")


if __name__ == "__main__":
    unittest.main()

"""R8.19: Player Save Manager end-to-end contracts, without a GUI display."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.reliability_gate import fixture
from sporebound.game_session import GameSession
from sporebound.long_session import LongSessionStore
from sporebound.model import RuleError
from sporebound.persistence import SessionStore
from sporebound.player_controller import PlayerController
from sporebound.save_manager import SaveManagerModel, compare_recordings
from sporebound.save_maintenance import LongSessionMaintenance
from sporebound.session_lock import session_writer_lock


class SaveManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content, cls.project = fixture()
        cls.project.save_slots = 4

    def make(self, root):
        player = PlayerController(self.content, self.project,
                                  Path(root) / "profile")
        return player, SaveManagerModel(player)

    def test_browse_all_slots_v2_and_long_without_mutating_files(self):
        with TemporaryDirectory() as root:
            player, manager = self.make(root)
            player.new_game("main", 1, seed=17)
            old_path = player.path_for("main", 1)
            old_bytes = old_path.read_bytes()
            player.new_long_game("main", 2, seed=19)
            long_path = player.long_path_for("main", 2)
            long_bytes = long_path.read_bytes()
            rows = manager.list_slots("main")
            self.assertEqual(len(rows), 8)
            self.assertEqual(next(v for v in rows if v["slot"] == 1
                                  and v["kind"] == "v2")["status"], "healthy")
            self.assertEqual(next(v for v in rows if v["slot"] == 2
                                  and v["kind"] == "long")["status"], "healthy")
            self.assertEqual(next(v for v in rows if v["slot"] == 3
                                  and v["kind"] == "long")["status"], "missing")
            self.assertEqual(manager.history("main", 1, "v2")[0]["type"], "current")
            self.assertEqual(old_path.read_bytes(), old_bytes)
            self.assertEqual(long_path.read_bytes(), long_bytes)
            self.assertFalse(long_path.with_name(long_path.name + ".lock").exists())

    def test_archive_history_diff_and_exact_non_destructive_restoration(self):
        with TemporaryDirectory() as root:
            player, manager = self.make(root)
            player.new_long_game("main", 1, seed=17)
            maintenance = manager._maintenance("main", 1)
            first = maintenance.archive_verified()
            old_record = player.session.recording()
            player.choose_story_option("assault")
            second = maintenance.archive_verified()
            current = player.session.recording()
            self.assertNotEqual(first["name"], second["name"])
            versions = manager.history("main", 1)
            self.assertEqual(len(versions), 3)
            self.assertEqual(versions[0]["id"], "current")
            self.assertTrue(all(entry["verified"] for entry in versions))
            different = manager.compare_archive("main", 1, first["name"])
            self.assertFalse(different["same"])
            self.assertEqual(different["selected"]["digest"], old_record["digest"])
            self.assertTrue(different["fields"])
            equal = manager.compare_archive("main", 1, second["name"])
            self.assertTrue(equal["same"])
            preview = manager.restoration_plan("main", 1, first["name"], 3)
            self.assertIn("diff", "differences")
            self.assertEqual(preview["digest"], old_record["digest"])
            self.assertFalse(player.long_path_for("main", 3).exists())
            before_primary = player.long_path_for("main", 1).read_bytes()
            before_journal = player.long_store().journal.read_bytes()
            before_session = player.session.recording()
            result = manager.restore_to_free_slot(
                "main", 1, first["name"], 3, expected_token=preview["token"])
            self.assertTrue(result["verified"])
            restored = self.make(root)[0]
            restored.load_long_game("main", 3)
            self.assertEqual(restored.session.recording(), old_record)
            self.assertEqual(player.long_path_for("main", 1).read_bytes(),
                             before_primary)
            self.assertEqual(player.long_store().journal.read_bytes(),
                             before_journal)
            self.assertEqual(player.session.recording(), before_session)
            self.assertEqual(manager._maintenance("main", 1)
                             .verify_archive(maintenance.history / first["name"]),
                             first)

    def test_preview_does_not_create_slot_and_cancel_requires_no_action(self):
        with TemporaryDirectory() as root:
            player, manager = self.make(root)
            player.new_long_game("main", 1)
            generation = manager._maintenance("main", 1).archive_verified()["name"]
            preview = manager.restoration_plan("main", 1, generation, 2)
            self.assertIn("token", preview)
            self.assertFalse(player.long_path_for("main", 2).exists())
            self.assertFalse(player.long_path_for("main", 2)
                             .with_name("slot_2.long.json.journal").exists())
            self.assertFalse(player.long_path_for("main", 1)
                             .with_name("slot_1.long.json.lock").exists())
            # Reject a wrong token; the destination remains empty.
            with self.assertRaisesRegex(RuleError, "changed"):
                manager.restore_to_free_slot(
                    "main", 1, generation, 2, expected_token="0" * 64)
            self.assertFalse(player.long_path_for("main", 2).exists())

    def test_restore_rejects_occupied_or_evidenced_slot(self):
        with TemporaryDirectory() as root:
            player, manager = self.make(root)
            player.new_long_game("main", 1)
            archive = manager._maintenance("main", 1).archive_verified()["name"]
            with self.assertRaisesRegex(RuleError, "different"):
                manager.restoration_plan("main", 1, archive, 1)
            player.new_long_game("main", 2)
            primary = player.long_path_for("main", 2)
            original = primary.read_bytes()
            with self.assertRaisesRegex(RuleError, "empty slot"):
                manager.restoration_plan("main", 1, archive, 2)
            self.assertEqual(primary.read_bytes(), original)
            orphan = player.long_path_for("main", 3)
            orphan.parent.mkdir(parents=True, exist_ok=True)
            orphan.with_name(orphan.name + ".damaged").write_bytes(b"forensic")
            with self.assertRaisesRegex(RuleError, "evidence"):
                manager.restoration_plan("main", 1, archive, 3)
            self.assertFalse(orphan.exists())

    def test_invalid_archive_is_visible_but_not_selectable_or_restorable(self):
        with TemporaryDirectory() as root:
            player, manager = self.make(root)
            player.new_long_game("main", 1)
            maintenance = manager._maintenance("main", 1)
            saved = maintenance.archive_verified()
            archive = maintenance.history / saved["name"]
            original = (archive / "manifest.json").read_bytes()
            (archive / "manifest.json").write_bytes(b"{}")
            versions = manager.history("main", 1)
            bad = next(v for v in versions if v["id"] == saved["name"])
            self.assertFalse(bad["verified"])
            self.assertTrue(bad["reason"])
            with self.assertRaises(RuleError):
                manager.restoration_plan("main", 1, saved["name"], 2)
            with self.assertRaises(RuleError):
                manager.restoration_plan("main", 1, "../escape", 2)
            self.assertFalse(player.long_path_for("main", 2).exists())
            self.assertNotEqual(original, (archive / "manifest.json").read_bytes())

    def test_source_change_requires_fresh_verified_preview(self):
        with TemporaryDirectory() as root:
            player, manager = self.make(root)
            player.new_long_game("main", 1)
            archive = manager._maintenance("main", 1).archive_verified()
            approval = manager.restoration_plan("main", 1, archive["name"], 3)
            manager._maintenance("main", 1).history.joinpath(
                archive["name"], "manifest.json").write_text(
                    '{"invalid":"changed"}', encoding="utf-8")
            with self.assertRaises(RuleError):
                manager.restore_to_free_slot(
                    "main", 1, archive["name"], 3,
                    expected_token=approval["token"])
            self.assertFalse(player.long_path_for("main", 3).exists())

    def test_existing_writer_lock_blocks_guided_restore_and_no_ui_session_switch(self):
        with TemporaryDirectory() as root:
            player, manager = self.make(root)
            player.new_long_game("main", 1)
            archive = manager._maintenance("main", 1).archive_verified()
            preview = manager.restoration_plan("main", 1, archive["name"], 4)
            old = player.session
            with session_writer_lock(player.long_path_for("main", 1)):
                with self.assertRaisesRegex(RuleError, "lock"):
                    manager.restore_to_free_slot(
                        "main", 1, archive["name"], 4,
                        expected_token=preview["token"])
            self.assertFalse(player.long_path_for("main", 4).exists())
            self.assertIs(player.session, old)
            self.assertEqual(player.slot, 1)
            self.assertTrue(player.long_mode)

    def test_corrupted_current_save_can_still_compare_verified_archive(self):
        with TemporaryDirectory() as root:
            player, manager = self.make(root)
            player.new_long_game("main", 1)
            archive = manager._maintenance("main", 1).archive_verified()
            player.long_path_for("main", 1).write_bytes(b"{")
            state = manager.inspect_slot("main", 1, "long")
            self.assertIn(state["status"], ("degraded", "invalid"))
            comparison = manager.compare_archive("main", 1, archive["name"])
            self.assertIsNone(comparison["current"])
            self.assertIn("illisible", comparison["warning"])
            self.assertTrue(manager.history("main", 1)[-1]["verified"])

    def test_recording_diff_reports_multifront_and_campaign_changes(self):
        with TemporaryDirectory() as root:
            player, _ = self.make(root)
            player.new_long_game("main", 1)
            initial = player.session.recording()
            changed = GameSession.from_recording(initial,
                                                self.content, self.project)
            changed.choose_story_option("assault")
            comparison = compare_recordings(initial, changed.recording())
            self.assertFalse(comparison["same"])
            self.assertTrue(comparison["fields"])
            self.assertIn("warning", comparison)
            with self.assertRaisesRegex(RuleError, "different campaigns"):
                other = dict(changed.recording(), campaign_id="other")
                compare_recordings(initial, other)


if __name__ == "__main__":
    unittest.main()

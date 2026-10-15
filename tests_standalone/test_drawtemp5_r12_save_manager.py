"""R12.10 crash-safe autosave, recovery and zero-silent-fallback gates."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.player.controller import PlayerController
from drawtemp.player.qt_app import build_controller
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.slots import SlotError


class SaveManagerR1210Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.content, self.project = reference_project()
        self.player = PlayerController(
            self.content, self.project, "main", self.directory)
        self.auto = self.directory / "autosave.json"

    def _new(self):
        self.player.new_game()
        return self.player.session.recording()

    def test_new_story_mission_and_combat_changes_checkpoint_atomically(self):
        initial = self._new()
        self.assertTrue(self.auto.exists())
        self.assertEqual(self.player.state()["save_manager"]["autosave"]["status"], "valid")
        self.assertEqual(self.player.saves.load_autosave().recording(), initial)

        self.player.choose("enter")
        narrative = self.player.session.recording()
        self.assertNotEqual(initial, narrative)
        self.assertEqual(self.player.saves.load_autosave().recording(), narrative)
        self.assertTrue(self.auto.with_suffix(".json.bak").exists())

        self.player.start_mission(MISSION)
        battle = self.player.session.recording()
        self.assertEqual(self.player.saves.load_autosave().recording(), battle)
        self.player.interact_object("lever")
        self.assertEqual(self.player.saves.load_autosave().recording(),
                         self.player.session.recording())
        self.assertTrue(self.player.state()["save_manager"]["continue_available"])

    def test_manual_slot_unmodified_while_autosave_advances(self):
        self._new()
        self.player.save(1)
        manual = self.directory / "slot_1.json"
        preserved = manual.read_bytes()
        # Even when filesystems have coarse timestamp precision, manual save
        # is provably older than the latest checkpoint.
        os.utime(manual, ns=(1_000_000_000, 1_000_000_000))
        self.player.choose("enter")
        latest_record = self.player.session.recording()
        self.assertEqual(manual.read_bytes(), preserved)
        self.assertEqual(self.player.saves.catalog()["continue_source"], "auto")
        resumed = PlayerController(self.content, self.project, "main", self.directory)
        self.assertEqual(resumed.continue_game()["screen"], "campaign")
        self.assertEqual(resumed.session.recording(), latest_record)
        self.assertEqual(manual.read_bytes(), preserved)

    def test_corrupt_primary_requires_explicit_restore_not_silent_backup(self):
        self._new()
        original_record = self.player.session.recording()
        self.player.choose("enter")
        self.auto.write_bytes(b"damaged-autosave-bytes")
        broken = self.auto.read_bytes()
        catalog = self.player.saves.catalog()
        self.assertEqual(catalog["autosave"]["status"], "invalid")
        self.assertTrue(catalog["autosave"]["recoverable"])
        self.assertTrue(catalog["has_invalid"])
        self.assertFalse(catalog["continue_available"])
        with self.assertRaises(SlotError) as exc:
            self.player.continue_game()
        self.assertEqual(exc.exception.code, "no_valid_save")
        self.assertEqual(self.auto.read_bytes(), broken)

        self.player.restore_autosave_backup()
        self.assertEqual(self.player.session.recording(), original_record)
        self.assertEqual(self.auto.read_bytes(),
                         self.auto.with_suffix(".json.bak").read_bytes())
        self.assertEqual(self.auto.with_suffix(".json.damaged").read_bytes(), broken)
        self.assertEqual(self.player.saves.catalog()["autosave"]["status"], "valid")

    def test_corrupt_autosave_never_blocks_verified_manual_recovery(self):
        self._new()
        self.player.save(1)
        expected = self.player.session.recording()
        self.player.choose("enter")
        self.auto.write_text("{ nope", encoding="utf-8")
        original = self.auto.read_bytes()
        other = PlayerController(self.content, self.project, "main", self.directory)
        rows = other.state()["save_manager"]
        self.assertEqual(rows["continue_source"], 1)
        self.assertTrue(rows["has_invalid"])
        self.assertTrue(rows["warnings"])
        resumed = other.continue_game()
        self.assertEqual(resumed["screen"], "dialogue")
        self.assertEqual(other.session.recording(), expected)
        self.assertEqual(self.auto.read_bytes(), original)

    def test_failed_autosave_does_not_roll_back_committed_story(self):
        self._new()
        before_disk = self.auto.read_bytes()
        before_recording = self.player.session.recording()
        with patch.object(self.player.saves, "autosave",
                          side_effect=OSError("disk full")):
            updated = self.player.choose("enter")
        self.assertGreater(updated["revision"], 0)
        self.assertNotEqual(self.player.session.recording(), before_recording)
        self.assertEqual(self.auto.read_bytes(), before_disk)
        self.assertIn("Autosauvegarde impossible", updated["autosave_warning"])
        self.player.save(1)
        self.assertEqual(self.player._store(1).load().recording(),
                         self.player.session.recording())
        self.player.start_mission(MISSION)
        self.assertEqual(self.player.state()["autosave_warning"], "")
        self.assertEqual(self.player.saves.load_autosave().recording(),
                         self.player.session.recording())

    def test_atomic_replace_failure_preserves_prior_primary_bytes(self):
        from sporebound import storage
        self._new()
        primary = self.auto.read_bytes()
        original_replace = storage.os.replace

        def crash_before_publish(source, target):
            # Allow the previous generation to be written to .bak, then fail
            # exactly at the final atomic rename of the new primary.
            if Path(target) == self.auto:
                raise OSError("interrupted rename")
            return original_replace(source, target)

        with patch("sporebound.storage.os.replace", side_effect=crash_before_publish):
            state = self.player.choose("enter")
        self.assertIn("Autosauvegarde impossible", state["autosave_warning"])
        self.assertEqual(self.auto.read_bytes(), primary)
        self.assertEqual(self.auto.with_suffix(".json.bak").read_bytes(), primary)
        self.assertFalse(list(self.directory.glob("autosave.json.*.tmp")))
        self.assertEqual(self.player.state()["screen"], "campaign")
        self.assertNotEqual(self.player.session.recording(),
                            self.player.saves.load_autosave().recording())

    def test_rejected_rule_preview_selection_and_options_do_not_write(self):
        self._new()
        recorded = self.player.session.recording()
        original = self.auto.read_bytes()
        with self.assertRaises(ValueError):
            self.player.choose("nonexistent")
        self.player.set_display("high_contrast", True)
        self.player.set_profile("qwerty")
        self.assertEqual(recorded, self.player.session.recording())
        self.assertEqual(original, self.auto.read_bytes())
        self.player.choose("enter")
        self.player.start_mission(MISSION)
        before = self.auto.read_bytes()
        self.player.select_cell(-5, 900)
        try:
            self.player.preview("attack")
        except ValueError:
            pass
        self.assertEqual(before, self.auto.read_bytes())

    def test_invalid_autosave_is_not_overwritten_by_later_actions(self):
        self._new()
        self.auto.write_bytes(b"bad-primary")
        self.player.choose("enter")
        self.assertEqual(self.auto.read_bytes(), b"bad-primary")
        self.assertIn("Autosauvegarde impossible",
                      self.player.state()["autosave_warning"])
        self.player.save(1)
        self.assertTrue((self.directory / "slot_1.json").exists())
        self.assertEqual(self.auto.read_bytes(), b"bad-primary")

    def test_orphan_backup_must_be_recovered_explicitly(self):
        self._new()
        self.player.choose("enter")
        backup = self.auto.with_suffix(".json.bak")
        self.assertTrue(backup.exists())
        previous = backup.read_bytes()
        self.auto.unlink()
        clone = PlayerController(self.content, self.project, "main", self.directory)
        self.assertEqual(clone.state()["save_manager"]["autosave"]["backup_status"],
                         "valid")
        clone.new_game()
        self.assertTrue(clone.state()["autosave_warning"])
        self.assertEqual(backup.read_bytes(), previous)
        clone.restore_autosave_backup()
        self.assertEqual(self.auto.read_bytes(), previous)

    def test_packaged_jeanne_exploration_step_survives_restart(self):
        game = build_controller(save_dir=self.directory)
        self.assertEqual(game.new_game()["screen"], "exploration")
        game.explore_move(1, 0)
        game.explore_interact("ble")
        expected = game.session.recording()
        restarted = build_controller(save_dir=self.directory)
        self.assertEqual(restarted.continue_game()["screen"], "exploration")
        self.assertEqual(restarted.session.recording(), expected)
        self.assertEqual(restarted.state()["exploration"]["position"], [2, 5])
        self.assertTrue(next(p for p in restarted.state()["exploration"]["interactions"]
                             if p["id"] == "ble")["visited"])

    def test_slots_remain_stable_and_validate_foreign_campaign(self):
        self._new()
        before = self.auto.read_bytes()
        catalog = self.player.saves.catalog()
        catalog["autosave"]["status"] = "faked"
        self.assertEqual(self.player.saves.catalog()["autosave"]["status"], "valid")
        with self.assertRaises(ValueError):
            self.player.saves._store("slot_1")
        with self.assertRaises(ValueError):
            self.player.saves._store(0)
        self.assertEqual(self.auto.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

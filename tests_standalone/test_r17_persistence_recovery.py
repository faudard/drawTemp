"""R17.7 persistence regressions: no silent rollback, explicit retryable recovery.

No new save format: canonical GameSession v1 and R1 PlayerSlotStore only.
"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.slots import SlotError


class R17RecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.content, self.project = reference_project()
        self.player = PlayerController(self.content, self.project, "main", self.root)
        self.primary = self.root / "slot_1.json"
        self.backup = self.primary.with_suffix(".json.bak")
        self.damaged = self.primary.with_suffix(".json.damaged")

    def two_generations(self):
        initial = self.player.new_game()
        self.player.save(1)
        first = self.player.session.recording()
        self.player.choose("enter")
        self.player.save(1)
        latest = self.player.session.recording()
        self.assertNotEqual(first, latest)
        self.assertTrue(self.backup.is_file())
        return first, latest

    def test_manual_restore_never_downgrades_valid_primary(self):
        _, latest = self.two_generations()
        existing = (self.primary.read_bytes(), self.backup.read_bytes())
        with self.assertRaises(SlotError) as error:
            self.player.restore_backup(1)
        self.assertEqual(error.exception.code, "primary_valid")
        self.assertEqual((self.primary.read_bytes(), self.backup.read_bytes()), existing)
        self.assertEqual(self.player.session.recording(), latest)
        self.assertFalse(self.damaged.exists())

    def test_interruption_after_archiving_corruption_can_be_retried(self):
        old, live = self.two_generations()
        broken = b'{"damaged": true'
        self.primary.write_bytes(broken)
        backup_before = self.backup.read_bytes()
        from drawtemp.sdk import slots
        original_write = slots.write_bytes

        def fail_publish(path, data):
            if Path(path) == self.primary:
                raise OSError("simulated disk failure before recovered primary publish")
            return original_write(path, data)

        with patch("drawtemp.sdk.slots.write_bytes", side_effect=fail_publish):
            with self.assertRaisesRegex(OSError, "simulated disk failure"):
                self.player.restore_backup(1)
        self.assertEqual(self.primary.read_bytes(), broken)
        self.assertEqual(self.backup.read_bytes(), backup_before)
        self.assertEqual(self.damaged.read_bytes(), broken)
        self.assertEqual(self.player.session.recording(), live)

        # A second explicit user action may reuse the identical archived
        # bytes. The existing .damaged file must not make recovery impossible.
        self.player.restore_backup(1)
        self.assertEqual(self.primary.read_bytes(), backup_before)
        self.assertEqual(self.damaged.read_bytes(), broken)
        self.assertEqual(self.player.session.recording(), old)
        self.assertFalse((self.primary.with_name("slot_1.json.lock")).exists())

    def test_recovery_never_overwrites_different_existing_evidence(self):
        self.two_generations()
        self.primary.write_bytes(b"new corruption")
        self.damaged.write_bytes(b"previous unrelated corruption")
        before = (self.primary.read_bytes(), self.backup.read_bytes(),
                  self.damaged.read_bytes())
        with self.assertRaises(SlotError) as error:
            self.player.restore_backup(1)
        self.assertEqual(error.exception.code, "evidence_exists")
        self.assertEqual((self.primary.read_bytes(), self.backup.read_bytes(),
                          self.damaged.read_bytes()), before)

    def test_bad_backup_is_rejected_without_mutating_live_game(self):
        _, latest = self.two_generations()
        self.primary.write_bytes(b"invalid primary")
        self.backup.write_bytes(b"invalid backup")
        original = (self.primary.read_bytes(), self.backup.read_bytes())
        with self.assertRaises(Exception):
            self.player.restore_backup(1)
        self.assertEqual((self.primary.read_bytes(), self.backup.read_bytes()), original)
        self.assertEqual(self.player.session.recording(), latest)
        self.assertFalse(self.damaged.exists())

    def test_orphan_backup_restores_with_explicit_action(self):
        first, _ = self.two_generations()
        self.primary.unlink()
        self.player.restore_backup(1)
        self.assertEqual(self.player.session.recording(), first)
        self.assertEqual(self.primary.read_bytes(), self.backup.read_bytes())
        self.assertFalse(self.damaged.exists())

    @unittest.skipIf(os.name == "nt",
                     "Windows st_ctime is creation time; ordinary mtime checks still apply")
    def test_catalogue_invalidates_on_same_size_mtime_restored_corruption(self):
        self.player.new_game()
        catalogue = self.player.saves.catalog()
        self.assertEqual(catalogue["autosave"]["status"], "valid")
        auto = self.root / "autosave.json"
        baseline = auto.stat()
        data = auto.read_bytes()
        self.assertGreater(len(data), 1)
        import time
        time.sleep(0.02)  # Ensure filesystems with coarse change-time precision
        auto.write_bytes(b"!" + data[1:])
        os.utime(auto, ns=(baseline.st_atime_ns, baseline.st_mtime_ns))
        now = auto.stat()
        self.assertEqual(now.st_size, baseline.st_size)
        self.assertEqual(now.st_mtime_ns, baseline.st_mtime_ns)
        self.assertNotEqual(now.st_ctime_ns, baseline.st_ctime_ns)
        refresh = self.player.saves.catalog()
        self.assertEqual(refresh["autosave"]["status"], "invalid")
        self.assertTrue(refresh["has_invalid"])


if __name__ == "__main__":
    unittest.main()

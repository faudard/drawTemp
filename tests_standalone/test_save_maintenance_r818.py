"""R8.18 contract: immutable live saves, verified archives, explicit retention."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import time
import unittest

from examples.reliability_gate import fixture
from sporebound.game_session import GameSession
from sporebound.long_session import LongSessionStore
from sporebound.model import RuleError
from sporebound.save_maintenance import LongSessionMaintenance
from sporebound.session_lock import session_writer_lock


class SaveMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = fixture()

    def make(self, folder, *, checkpoint_every=2):
        path = Path(folder) / "slot_1.long.json"
        store = LongSessionStore(path, checkpoint_every=checkpoint_every)
        session = GameSession.new(self.content, self.project, "main", seed=17)
        store.initialize(session)
        manager = LongSessionMaintenance(
            path, self.content, self.project,
            checkpoint_every=checkpoint_every)
        return store, session, manager

    def test_read_only_inventory_and_verified_snapshot_preserve_live_bytes(self):
        with TemporaryDirectory() as root:
            store, session, manager = self.make(root)
            store.perform(session, "story-one", "choose_story_option", "assault")
            original_primary = store.store.path.read_bytes()
            original_journal = store.journal.read_bytes()
            inventory = manager.inspect()
            self.assertEqual(inventory["status"], "healthy")
            self.assertEqual(inventory["session_digest"],
                             store.load(self.content, self.project).recording()["digest"])
            self.assertEqual(inventory["replayed"], 1)
            self.assertEqual(inventory["archives"], [])
            saved = manager.archive_verified()
            self.assertTrue(saved["verified"])
            self.assertEqual(manager.verify_archive(manager.history / saved["name"]),
                             saved)
            self.assertEqual(store.store.path.read_bytes(), original_primary)
            self.assertEqual(store.journal.read_bytes(), original_journal)
            self.assertEqual(manager.inspect()["archives"][0]["name"], saved["name"])
            self.assertFalse(Path(str(store.store.path) + ".lock").exists())

    def test_corrupt_journal_is_reported_and_blocks_archiving(self):
        with TemporaryDirectory() as root:
            store, session, manager = self.make(root)
            store.perform(session, "story", "choose_story_option", "assault")
            store.journal.write_bytes(b"{truncated")
            original = store.journal.read_bytes()
            inventory = manager.inspect()
            self.assertEqual(inventory["status"], "invalid")
            self.assertTrue(any(i["role"] == "journal" and i["status"] == "invalid"
                                for i in inventory["assets"]))
            with self.assertRaises(RuleError):
                manager.archive_verified()
            self.assertEqual(store.journal.read_bytes(), original)
            self.assertFalse(manager.history.exists())

    def test_archive_tampering_fails_verification_and_prune(self):
        with TemporaryDirectory() as root:
            _, _, manager = self.make(root)
            generations = [manager.archive_verified() for _ in range(4)]
            oldest = manager.history / generations[0]["name"]
            original = (oldest / "manifest.json").read_bytes()
            (oldest / "manifest.json").write_bytes(b"{}")
            with self.assertRaises(RuleError):
                manager.verify_archive(oldest)
            with self.assertRaises(RuleError):
                manager.retention_plan(keep=2)
            self.assertEqual((oldest / "manifest.json").read_bytes(), b"{}")
            self.assertNotEqual(original, b"{}")
            self.assertEqual(len(manager._archive_dirs()), 4)

    def test_retention_keeps_two_and_requires_exact_fresh_token(self):
        with TemporaryDirectory() as root:
            store, _, manager = self.make(root)
            original = store.store.path.read_bytes()
            generated = [manager.archive_verified() for _ in range(4)]
            plan = manager.retention_plan(keep=2)
            self.assertEqual(len(plan["remove"]), 2)
            self.assertEqual(len(plan["preserve"]), 2)
            # A new generation invalidates a previously approved plan.
            manager.archive_verified()
            with self.assertRaisesRegex(RuleError, "stale"):
                manager.prune_archives(keep=2, expected_token=plan["token"])
            with self.assertRaises(RuleError):
                manager.prune_archives(keep=2, expected_token="not-a-token")
            current = manager.retention_plan(keep=2)
            result = manager.prune_archives(
                keep=2, expected_token=current["token"])
            self.assertEqual(result["remove"], current["remove"])
            self.assertEqual(len(manager._archive_dirs()), 2)
            for archive in manager._archive_dirs():
                self.assertTrue(manager.verify_archive(archive)["verified"])
            self.assertEqual(store.store.path.read_bytes(), original)
            self.assertEqual(len(generated), 4)

    def test_backup_and_damaged_evidence_are_not_automatically_removed(self):
        with TemporaryDirectory() as root:
            store, session, manager = self.make(root, checkpoint_every=1)
            store.perform(session, "story", "choose_story_option", "assault")
            self.assertTrue(store.store.backup.exists())
            damaged = Path(str(store.store.path) + ".damaged")
            damaged.write_bytes(b"keep damaged generation")
            backup = store.store.backup.read_bytes()
            generations = [manager.archive_verified() for _ in range(4)]
            current = manager.retention_plan(keep=2)
            manager.prune_archives(keep=2, expected_token=current["token"])
            self.assertEqual(store.store.backup.read_bytes(), backup)
            self.assertEqual(damaged.read_bytes(), b"keep damaged generation")
            self.assertEqual(len(generations), 4)

    def test_stale_temp_quarantine_only_after_explicit_confirm(self):
        with TemporaryDirectory() as root:
            store, _, manager = self.make(root)
            old_temp = Path(str(store.journal) + ".z4old.tmp")
            fresh_temp = Path(str(store.journal) + ".z5new.tmp")
            unrelated = Path(root) / "other.json.X.tmp"
            old_temp.write_bytes(b"possibly useful recovery bytes")
            fresh_temp.write_bytes(b"new atomic publish")
            unrelated.write_bytes(b"other slot")
            epoch = time.time() - 7200
            os.utime(old_temp, (epoch, epoch))
            planned = manager.temp_plan(min_age_seconds=3600)
            self.assertEqual(planned["count"], 1)
            self.assertEqual(planned["files"][0]["name"], old_temp.name)
            with self.assertRaises(RuleError):
                manager.quarantine_temps(
                    min_age_seconds=3600, expected_token="0" * 64)
            self.assertTrue(old_temp.exists())
            result = manager.quarantine_temps(
                min_age_seconds=3600, expected_token=planned["token"])
            self.assertEqual(result["count"], 1)
            self.assertFalse(old_temp.exists())
            self.assertEqual((manager.quarantine / result["moved"][0]).read_bytes(),
                             b"possibly useful recovery bytes")
            self.assertEqual(fresh_temp.read_bytes(), b"new atomic publish")
            self.assertEqual(unrelated.read_bytes(), b"other slot")

    def test_temp_change_invalidates_confirmation_and_preserves_evidence(self):
        with TemporaryDirectory() as root:
            store, _, manager = self.make(root)
            old_temp = Path(str(store.store.path) + ".old.tmp")
            old_temp.write_bytes(b"initial")
            age = time.time() - 7200
            os.utime(old_temp, (age, age))
            plan = manager.temp_plan(min_age_seconds=3600)
            old_temp.write_bytes(b"changed")
            os.utime(old_temp, (age, age))
            with self.assertRaisesRegex(RuleError, "changed"):
                manager.quarantine_temps(
                    min_age_seconds=3600, expected_token=plan["token"])
            self.assertEqual(old_temp.read_bytes(), b"changed")

    def test_writer_lock_blocks_archival_cleanup_and_preserves_slot(self):
        with TemporaryDirectory() as root:
            store, _, manager = self.make(root)
            before = store.store.path.read_bytes()
            with session_writer_lock(store.store.path):
                self.assertEqual(manager.inspect()["status"], "healthy")
                with self.assertRaisesRegex(RuleError, "lock"):
                    manager.archive_verified()
                with self.assertRaisesRegex(RuleError, "lock"):
                    manager.prune_archives(
                        keep=2, expected_token=manager.retention_plan(keep=2)["token"])
                with self.assertRaisesRegex(RuleError, "lock"):
                    manager.quarantine_temps(
                        min_age_seconds=3600,
                        expected_token=manager.temp_plan(min_age_seconds=3600)["token"])
            self.assertEqual(store.store.path.read_bytes(), before)
            self.assertFalse(manager.history.exists())

    def test_unrecoverable_primary_keeps_archived_generations_intact(self):
        with TemporaryDirectory() as root:
            store, _, manager = self.make(root)
            [manager.archive_verified() for _ in range(4)]
            planned = manager.retention_plan(keep=2)
            store.store.path.write_bytes(b"{")
            with self.assertRaisesRegex(RuleError, "degraded"):
                manager.prune_archives(keep=2, expected_token=planned["token"])
            self.assertEqual(len(manager._archive_dirs()), 4)


if __name__ == "__main__":
    unittest.main()

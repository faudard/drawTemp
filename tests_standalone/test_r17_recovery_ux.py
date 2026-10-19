"""R17.11: explicit, hash-bound Player recovery; zero silent fallback."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.slots import SlotError


class RecoveryConsentTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        content, project = reference_project()
        self.game = PlayerController(content, project, "main", self.directory)

    def save_generations(self, slot):
        self.game.new_game()
        if slot:
            self.game.save(slot)
        original = self.game.session.recording()
        self.game.choose("enter")
        if slot:
            self.game.save(slot)
        current = self.game.session.recording()
        name = "autosave.json" if slot == 0 else "slot_%d.json" % slot
        primary = self.directory / name
        backup = primary.with_suffix(".json.bak")
        self.assertTrue(primary.exists() and backup.exists())
        self.assertNotEqual(original, current)
        return original, current, primary, backup

    def restore(self, slot, **kwargs):
        if slot == 0:
            return self.game.restore_autosave_backup(**kwargs)
        return self.game.restore_backup(slot, **kwargs)

    def store(self, slot):
        return (self.game.saves._store("auto") if slot == 0
                else self.game._store(slot))

    def test_hashed_confirmation_accepts_explicit_corrupted_restore(self):
        for slot in (0, 1):
            with self.subTest(slot=slot):
                # Separate directories to avoid generation mixing.
                if slot:
                    self.directory = self.directory / "next"
                    self.directory.mkdir()
                    self.game = PlayerController(
                        self.game.content, self.game.project, "main", self.directory)
                original, current, primary, backup = self.save_generations(slot)
                damaged = b"broken checkpoint bytes"
                primary.write_bytes(damaged)
                observed = self.store(slot).recovery_fingerprints()
                before_backup = backup.read_bytes()
                self.assertEqual(observed[0], self.store(slot)._file_digest(primary))
                result = self.restore(slot, expected_fingerprints=observed)
                self.assertEqual(result["screen"], "dialogue")
                self.assertEqual(self.game.session.recording(), original)
                self.assertEqual(primary.read_bytes(), before_backup)
                self.assertEqual(primary.with_suffix(".json.damaged").read_bytes(),
                                 damaged)

    def test_changed_primary_after_consent_refuses_all_writes(self):
        _, live, primary, backup = self.save_generations(1)
        primary.write_bytes(b"first corruption")
        approved = self.store(1).recovery_fingerprints()
        primary.write_bytes(b"second corruption")
        old = (primary.read_bytes(), backup.read_bytes())
        with self.assertRaises(SlotError) as exc:
            self.restore(1, expected_fingerprints=approved)
        self.assertEqual(exc.exception.code, "stale_recovery")
        self.assertEqual((primary.read_bytes(), backup.read_bytes()), old)
        self.assertEqual(self.game.session.recording(), live)
        self.assertFalse(primary.with_suffix(".json.damaged").exists())

    def test_changed_backup_after_consent_refuses_all_writes(self):
        _, live, primary, backup = self.save_generations(0)
        primary.write_bytes(b"corrupt main")
        approved = self.store(0).recovery_fingerprints()
        backup.write_bytes(b"bad backup changed by external writer")
        prior = (primary.read_bytes(), backup.read_bytes())
        with self.assertRaises(SlotError) as exc:
            self.restore(0, expected_fingerprints=approved)
        self.assertEqual(exc.exception.code, "stale_recovery")
        self.assertEqual((primary.read_bytes(), backup.read_bytes()), prior)
        self.assertEqual(self.game.session.recording(), live)

    def test_confirmed_manual_restore_cannot_replace_valid_primary(self):
        _, current, primary, backup = self.save_generations(1)
        fingerprints = self.store(1).recovery_fingerprints()
        before = (primary.read_bytes(), backup.read_bytes())
        with self.assertRaises(SlotError) as caught:
            self.restore(1, expected_fingerprints=fingerprints)
        self.assertEqual(caught.exception.code, "primary_valid")
        self.assertEqual((primary.read_bytes(), backup.read_bytes()), before)
        self.assertEqual(self.game.session.recording(), current)

    def test_invalid_confirmation_rejected_without_side_effect(self):
        _, current, primary, backup = self.save_generations(1)
        primary.write_bytes(b"broken")
        before = (primary.read_bytes(), backup.read_bytes())
        for value in ((), (None,), ("not-a-hash", None), [None, None]):
            with self.subTest(value=value), self.assertRaises(SlotError):
                self.restore(1, expected_fingerprints=value)
        self.assertEqual((primary.read_bytes(), backup.read_bytes()), before)
        self.assertEqual(self.game.session.recording(), current)


if __name__ == "__main__":
    unittest.main()

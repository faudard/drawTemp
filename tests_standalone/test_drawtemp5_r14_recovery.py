"""R14.9 interruption/fault testing against the real R12 Player save manager."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.reference import MISSION, reference_project


class PlayerAtomicBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        content, project = reference_project()
        self.game = PlayerController(content, project, "main", self.temp.name)
        self.game.new_game()
        self.game.save(1)
        self.game.choose("enter")
        self.game.save(1)  # First known-good backup contains the dialogue state.
        self.game.start_mission(MISSION)
        self.slot = Path(self.temp.name) / "slot_1.json"
        self.backup = Path(self.temp.name) / "slot_1.json.bak"
        self.staged = Path(self.temp.name) / "slot_1.json.bak.tmp"
        self.old_slot = self.slot.read_bytes()
        self.old_backup = self.backup.read_bytes()

    def assert_recoverable(self):
        self.assertEqual(self.slot.read_bytes(), self.old_slot)
        self.assertEqual(self.backup.read_bytes(), self.old_backup)
        self.assertFalse(self.staged.exists(), "Interrupted backup staging must be cleaned")
        self.assertEqual(self.game.load(1)["screen"], "campaign")
        self.assertEqual(self.game.restore_backup(1)["screen"], "dialogue")

    def test_failed_partial_copy_preserves_original_backup(self):
        def interrupted_copy(source, destination):
            Path(destination).write_bytes(b"partial and corrupt")
            raise OSError("injected mid-copy fault")

        with patch("drawtemp.player.controller.shutil.copy2",
                   side_effect=interrupted_copy):
            with self.assertRaisesRegex(OSError, "injected mid-copy"):
                self.game.save(1)
        self.assert_recoverable()

    def test_failed_atomic_publish_preserves_original_backup(self):
        with patch("drawtemp.player.controller.os.replace",
                   side_effect=OSError("injected publish fault")):
            with self.assertRaisesRegex(OSError, "publish fault"):
                self.game.save(1)
        self.assert_recoverable()


if __name__ == "__main__":
    unittest.main()

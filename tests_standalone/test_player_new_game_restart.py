"""Regression: a confirmed New Game can restart an incompatible checkpoint safely."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import digest
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController


class PlayerNewGameRestartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)
        cls.project = GameProject.load(
            Path(DEFAULT_CONTENT).with_suffix(".game.json"), cls.content)

    def controller(self, root):
        return PlayerController(self.content, self.project, Path(root) / "profile")

    @staticmethod
    def _simulate_content_update(path):
        """Keep both envelopes valid while making their content ID obsolete."""
        document = json.loads(path.read_text(encoding="utf-8"))
        recorded = document["session"]
        recorded["content_digest"] = "0" * 64
        recorded["digest"] = digest({k: v for k, v in recorded.items()
                                     if k != "digest"})
        document["digest"] = digest({k: v for k, v in document.items()
                                     if k != "digest"})
        path.write_text(json.dumps(document), encoding="utf-8")

    def test_incompatible_primary_and_backup_are_archived_exactly(self):
        with TemporaryDirectory() as folder:
            player = self.controller(folder)
            player.new_game("main", 1)
            player.save()  # Ensure both primary and backup exist.
            path = player.path_for("main", 1)
            backup = path.with_name(path.name + ".bak")
            for evidence in (path, backup):
                self._simulate_content_update(evidence)
            old_bytes = {p.name: p.read_bytes() for p in (path, backup)}

            with self.assertRaisesRegex(RuleError, "Save incompatible \\(content\\)"):
                player.load_game("main", 1)
            with self.assertRaisesRegex(RuleError, "explicit overwrite"):
                player.new_game("main", 1)
            self.assertEqual({p.name: p.read_bytes() for p in (path, backup)},
                             old_bytes)

            fresh = player.new_game("main", 1, overwrite=True)
            archive = player.last_restart_archive
            self.assertIsNotNone(archive)
            self.assertEqual({name: (archive / name).read_bytes()
                              for name in old_bytes}, old_bytes)
            self.assertEqual(fresh.recording(), self.controller(folder)
                             .load_game("main", 1).recording())

            player.save()  # Backup rotation must not alter the archive.
            self.assertEqual({name: (archive / name).read_bytes()
                              for name in old_bytes}, old_bytes)

    def test_explicit_restart_preserves_valid_old_save_too(self):
        with TemporaryDirectory() as folder:
            player = self.controller(folder)
            player.new_game("main", 1)
            slot = player.path_for("main", 1)
            before = slot.read_bytes()
            player.new_game("main", 1, overwrite=True)
            self.assertEqual((player.last_restart_archive / slot.name).read_bytes(),
                             before)
            self.assertEqual(self.controller(folder).load_game("main", 1)
                             .recording(), player.session.recording())

    def test_failed_archive_does_not_modify_slot_or_session(self):
        with TemporaryDirectory() as folder:
            player = self.controller(folder)
            player.new_game("main", 1)
            path = player.path_for("main", 1)
            before = path.read_bytes()
            original = player.session
            with patch("sporebound.persistence.write_bytes",
                       side_effect=OSError("archive disk full")):
                with self.assertRaisesRegex(OSError, "archive disk full"):
                    player.new_game("main", 1, overwrite=True)
            self.assertEqual(path.read_bytes(), before)
            self.assertIs(player.session, original)
            self.assertEqual(self.controller(folder).load_game("main", 1)
                             .recording(), original.recording())

    def test_orphan_backup_can_be_preserved_and_restarted(self):
        with TemporaryDirectory() as folder:
            player = self.controller(folder)
            player.new_game("main", 1)
            path = player.path_for("main", 1)
            backup = path.with_name(path.name + ".bak")
            backup.write_bytes(path.read_bytes())
            path.unlink()
            before = backup.read_bytes()
            player.new_game("main", 1, overwrite=True)
            self.assertEqual((player.last_restart_archive / backup.name).read_bytes(),
                             before)
            self.assertEqual(self.controller(folder).load_game("main", 1)
                             .recording(), player.session.recording())


if __name__ == "__main__":
    unittest.main()

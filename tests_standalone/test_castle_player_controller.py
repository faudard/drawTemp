"""2.8.1 GUI controller: verified persistence, rollback and route choices."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from examples.castle_vertical_slice import castle_blueprint, castle_content
from sporebound.castle_player_controller import CastlePlayerController
from sporebound.model import RuleError
from sporebound.tactical_rpg3 import tactical_rpg_rules


class CastlePlayerControllerTests(unittest.TestCase):
    def make(self, folder):
        return CastlePlayerController(
            castle_content(), castle_blueprint(),
            Path(folder) / "castle.json", rules=tactical_rpg_rules())

    def test_preparation_route_checkpoint_and_verified_resume(self):
        with TemporaryDirectory() as folder:
            player = self.make(folder)
            player.new_game(seed=9)
            player.select_squad(["captain"])
            player.set_job("captain", "vanguard")
            player.buy("sturdy_armor")
            player.equip("captain", "sturdy_armor")
            player.start("direct")
            self.assertEqual(player.session.approach, "direct")
            self.assertEqual(player.session.fronts.logistics.supplies["player"], 2)
            self.assertTrue(player.session.fronts.route_locked)
            restored = self.make(folder)
            restored.continue_game()
            self.assertEqual(restored.session.recording(),
                             player.session.recording())
            self.assertEqual(restored.session.state(), player.session.state())
            with self.assertRaises(RuleError):
                restored.start("ram")
            self.assertEqual(restored.session.recording(),
                             player.session.recording())

    def test_bad_commands_do_not_change_saved_or_in_memory_state(self):
        with TemporaryDirectory() as folder:
            player = self.make(folder)
            player.new_game()
            snapshot = player.session.recording()
            with self.assertRaises(RuleError):
                player.select_squad(["captain", "captain"])
            with self.assertRaises(RuleError):
                player.equip("captain", "unowned")
            self.assertEqual(player.session.recording(), snapshot)
            self.assertEqual(self.make(folder).continue_game().recording(), snapshot)
            player.start("tunnels")
            snapshot = player.session.recording()
            with self.assertRaises(RuleError):
                player.switch("throne")
            with self.assertRaises(RuleError):
                player.execute({"kind": "not-a-command"})
            self.assertEqual(player.session.recording(), snapshot)
            self.assertEqual(self.make(folder).continue_game().recording(), snapshot)

    def test_failed_disk_write_rolls_back_preparation_and_route(self):
        with TemporaryDirectory() as folder:
            player = self.make(folder)
            player.new_game()
            checkpoint = player.session.recording()
            with patch.object(player, "save", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    player.buy("sturdy_armor")
            self.assertEqual(player.session.recording(), checkpoint)
            self.assertEqual(self.make(folder).continue_game().recording(), checkpoint)
            with patch.object(player, "save", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    player.start("direct")
            self.assertEqual(player.session.recording(), checkpoint)
            self.assertIsNone(player.session.fronts)

    def test_corrupt_checkpoint_rejected_without_mutating_loaded_game(self):
        with TemporaryDirectory() as folder:
            player = self.make(folder)
            player.new_game()
            previous = player.session.recording()
            path = Path(folder) / "castle.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["preparation"].append({"kind": "buy", "item": "sturdy_armor"})
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(RuleError):
                player.continue_game()
            self.assertEqual(player.session.recording(), previous)
            with self.assertRaises(RuleError):
                self.make(folder).continue_game()

    def test_overwrite_requires_explicit_confirmation(self):
        with TemporaryDirectory() as folder:
            player = self.make(folder)
            player.new_game()
            with self.assertRaises(RuleError):
                player.new_game()
            player.new_game(overwrite=True, seed=12)
            self.assertEqual(player.session.seed, 12)


if __name__ == "__main__":
    unittest.main()

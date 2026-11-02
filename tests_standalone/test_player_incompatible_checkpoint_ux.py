"""Recovery UX regressions: content drift never deletes existing checkpoints."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.player_app import PlayerApplication
from sporebound.player_controller import PlayerController


class IncompatibleCheckpointUxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)
        cls.project = GameProject.load(
            Path(DEFAULT_CONTENT).with_suffix(".game.json"), cls.content)

    def make_player(self, folder):
        return PlayerController(self.content, self.project,
                                Path(folder) / "profile")

    def test_free_slot_skips_backups_and_long_journals_without_writing(self):
        with TemporaryDirectory() as folder:
            player = self.make_player(folder)
            self.assertGreaterEqual(player.project.save_slots, 3)
            occupied = player.path_for("main", 1)
            recovery = player.path_for("main", 2).with_name("slot_2.json.bak")
            journal = player.long_path_for("main", 3)
            evidence = (occupied, recovery,
                        journal.with_name(journal.name + ".journal"))
            for path in evidence:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"original evidence")
            self.assertNotIn(player.first_free_slot("main"), (1, 2, 3))
            self.assertEqual([path.read_bytes() for path in evidence],
                             [b"original evidence"] * 3)

    def test_explicit_restart_chooses_an_empty_slot_and_preserves_old_save(self):
        with TemporaryDirectory() as folder:
            player = self.make_player(folder)
            player.new_game("main", 1)
            original = player.path_for("main", 1).read_bytes()
            selection = SimpleNamespace(value="1")
            slot_var = SimpleNamespace(
                get=lambda: selection.value,
                set=lambda value: setattr(selection, "value", value))
            launched = []
            messages = SimpleNamespace(
                askyesno=Mock(return_value=True), showwarning=Mock())
            view = SimpleNamespace(player=player, slot_var=slot_var,
                                   messagebox=messages,
                                   _new_game=lambda: launched.append(selection.value))
            error = RuleError(
                "No valid session checkpoint: Invalid checkpoint slot_1.json: "
                "Save incompatible (content): recorded=c63f375baa11, "
                "current=120da85b9e2a")
            handled = PlayerApplication._offer_new_slot_for_incompatible_save(
                view, "main", 1, error)
            self.assertTrue(handled)
            self.assertEqual(launched, ["2"])
            self.assertEqual(selection.value, "2")
            self.assertIn("NOUVELLE partie", messages.askyesno.call_args.args[1])
            self.assertEqual(player.path_for("main", 1).read_bytes(), original)
            self.assertFalse(player.path_for("main", 2).exists())

    def test_declining_restart_does_not_switch_slot(self):
        with TemporaryDirectory() as folder:
            player = self.make_player(folder)
            slot = SimpleNamespace(value="1")
            view = SimpleNamespace(
                player=player,
                slot_var=SimpleNamespace(
                    get=lambda: slot.value,
                    set=lambda value: setattr(slot, "value", value)),
                messagebox=SimpleNamespace(
                    askyesno=Mock(return_value=False), showwarning=Mock()),
                _new_game=Mock())
            handled = PlayerApplication._offer_new_slot_for_incompatible_save(
                view, "main", 1, RuleError("Save incompatible (project)"))
            self.assertTrue(handled)
            self.assertEqual(slot.value, "1")
            view._new_game.assert_not_called()

    def test_other_errors_are_not_masked(self):
        with TemporaryDirectory() as folder:
            player = self.make_player(folder)
            view = SimpleNamespace(player=player, messagebox=Mock(),
                                   slot_var=Mock(), _new_game=Mock())
            self.assertFalse(
                PlayerApplication._offer_new_slot_for_incompatible_save(
                    view, "main", 1, RuleError("Checkpoint checksum mismatch")))
            view.messagebox.askyesno.assert_not_called()

    def test_no_free_slot_reports_warning_without_deletion(self):
        with TemporaryDirectory() as folder:
            player = self.make_player(folder)
            evidence = []
            for slot in range(1, player.project.save_slots + 1):
                path = player.path_for("main", slot)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"save evidence")
                evidence.append(path)
            messages = SimpleNamespace(
                askyesno=Mock(), showwarning=Mock())
            view = SimpleNamespace(player=player, messagebox=messages,
                                   slot_var=Mock(), _new_game=Mock())
            self.assertTrue(
                PlayerApplication._offer_new_slot_for_incompatible_save(
                    view, "main", 1, RuleError("Save incompatible (content)")))
            messages.showwarning.assert_called_once()
            messages.askyesno.assert_not_called()
            view._new_game.assert_not_called()
            self.assertEqual([p.read_bytes() for p in evidence],
                             [b"save evidence"] * len(evidence))


if __name__ == "__main__":
    unittest.main()

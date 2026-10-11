"""Reliability gate: explicit migration, identity drift and player lifecycle."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, IncompatibleSaveError, digest
from sporebound.model import Content, RuleError
from sporebound.persistence import SessionStore
from sporebound.player_controller import PlayerController
from sporebound.player_app import PlayerApplication


class SaveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)
        cls.project = GameProject.load(
            Path(DEFAULT_CONTENT).with_suffix(".game.json"), cls.content)

    def controller(self, folder):
        return PlayerController(self.content, self.project, Path(folder) / "profile")

    def test_content_and_project_drift_refused_without_file_changes(self):
        with TemporaryDirectory() as folder:
            ui = self.controller(folder)
            ui.new_game("main", 1)
            store = ui.store()
            original = store.path.read_bytes()
            changed_content = deepcopy(self.content)
            changed_content.missions["garden"].name += " rewritten"
            with self.assertRaisesRegex(RuleError, "content"):
                store.load(changed_content, self.project, rules=ui.rules)
            changed_project = deepcopy(self.project)
            changed_project.title += " revision"
            with self.assertRaisesRegex(RuleError, "project"):
                store.load(self.content, changed_project, rules=ui.rules)
            self.assertEqual(store.path.read_bytes(), original)
            self.assertFalse(store.backup.exists())

    def test_changed_rules_fail_closed_even_if_saved_digest_is_valid(self):
        with TemporaryDirectory() as folder:
            ui = self.controller(folder)
            ui.new_game("main", 1)
            store = ui.store()
            recording = ui.session.recording()
            recording["rules"] = {"unsupported": "new-authoring-rules"}
            recording["digest"] = digest({k: v for k, v in recording.items() if k != "digest"})
            envelope = json.loads(store.path.read_text(encoding="utf-8"))
            envelope["session"] = recording
            envelope["digest"] = digest({k: v for k, v in envelope.items() if k != "digest"})
            store.path.write_text(json.dumps(envelope), encoding="utf-8")
            before = store.path.read_bytes()
            with self.assertRaisesRegex(RuleError, "rules"):
                ui.load_game("main", 1)
            self.assertEqual(store.path.read_bytes(), before)

    def test_explicit_v1_migration_preserves_bytes_and_rejects_remigration(self):
        with TemporaryDirectory() as folder:
            ui = self.controller(folder)
            path = ui.path_for("main", 1)
            old = GameSession.new(self.content, self.project, "main",
                                  rules=ui.rules, seed=17)
            old.start_mission("garden")
            path.parent.mkdir(parents=True, exist_ok=True)
            # Deliberately noncanonical JSON: migrating must not reformat the
            # original source in the recovery generation.
            path.write_text(json.dumps(old.recording(), separators=(",", ":")),
                            encoding="utf-8")
            original = path.read_bytes()
            with self.assertRaisesRegex(RuleError, "migrate_game"):
                ui.load_game("main", 1)
            self.assertEqual(path.read_bytes(), original)
            result = ui.migrate_game("main", 1)
            self.assertEqual(result.sequence, 1)
            self.assertFalse(result.migrated_from_v1)
            self.assertEqual(SessionStore(path).backup.read_bytes(), original)
            self.assertEqual(ui.load_game("main", 1).recording(), old.recording())
            with self.assertRaises(RuleError):
                ui.migrate_game("main", 1)

    def test_migration_fails_for_different_campaign_and_does_not_write(self):
        with TemporaryDirectory() as folder:
            ui = self.controller(folder)
            path = ui.path_for("main", 1)
            GameSession.new(self.content, self.project, "relique",
                            rules=ui.rules).save(path)
            original = path.read_bytes()
            with self.assertRaisesRegex(RuleError, "different campaign"):
                ui.migrate_game("main", 1)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(SessionStore(path).backup.exists())

    def test_failed_new_game_does_not_discard_current_session(self):
        with TemporaryDirectory() as folder:
            ui = self.controller(folder)
            existing = ui.new_game("main", 1)
            previous = (ui.campaign_id, ui.slot, ui.last_load_status)
            with patch("sporebound.player_controller.SessionStore.save",
                       side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    ui.new_game("main", 2)
            self.assertIs(ui.session, existing)
            self.assertEqual((ui.campaign_id, ui.slot, ui.last_load_status), previous)
            self.assertFalse(ui.path_for("main", 2).exists())

    def test_backup_recovery_is_reported_to_player(self):
        with TemporaryDirectory() as folder:
            ui = self.controller(folder)
            ui.new_game("main", 1)
            first = ui.session.recording()
            ui.start_mission("garden")
            ui.store().path.write_bytes(b"{")
            resumed = self.controller(folder)
            resumed.load_game("main", 1)
            self.assertEqual(resumed.last_load_status.source, "backup")
            self.assertEqual(resumed.session.recording(), first)

    def test_close_is_idempotent_and_cancel_does_not_close(self):
        app = PlayerApplication.__new__(PlayerApplication)
        app._closing = False
        app.player = SimpleNamespace(session=None)
        app.audio = MagicMock()
        app.root = MagicMock()
        app.close()
        app.close()
        app.audio.close.assert_called_once()
        app.root.destroy.assert_called_once()

        app._closing = False
        app.player = SimpleNamespace(session=object(), save=MagicMock(
            side_effect=OSError("read-only")))
        app.messagebox = SimpleNamespace(askyesno=MagicMock(return_value=False))
        app.audio.reset_mock()
        app.root.reset_mock()
        app.close()
        self.assertFalse(app._closing)
        app.audio.close.assert_not_called()
        app.root.destroy.assert_not_called()


if __name__ == "__main__":
    unittest.main()

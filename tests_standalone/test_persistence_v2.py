"""Persistence 2.0 regression gates: generations, recovery and migration."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.persistence import AutosaveSession, SessionStore
from sporebound.player_session import PlayerSession


class PersistenceV2Tests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.load(
            Path(DEFAULT_CONTENT).with_suffix(".game.json"), self.content)

    def new(self, campaign="main"):
        return GameSession.new(self.content, self.project, campaign, seed=27)

    def test_version_two_roundtrip_and_monotonic_backup(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            store = SessionStore(path)
            session = self.new("relique")
            store.save(session)
            first = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(first["version"], 2)
            self.assertEqual(first["sequence"], 1)
            self.assertIsNone(first["previous"])
            self.assertFalse(store.backup.exists())
            session.choose_story_option("guard")
            store.save(session)
            second = json.loads(path.read_text(encoding="utf-8"))
            backup = json.loads(store.backup.read_text(encoding="utf-8"))
            self.assertEqual(second["sequence"], 2)
            self.assertEqual(second["previous"], first["digest"])
            self.assertEqual(backup, first)
            loaded = store.load_with_status(self.content, self.project)
            self.assertEqual(loaded.source, "primary")
            self.assertEqual(loaded.sequence, 2)
            self.assertEqual(loaded.session.recording(), session.recording())

    def test_truncated_primary_recovers_previous_verified_generation(self):
        with TemporaryDirectory() as directory:
            store = SessionStore(Path(directory) / "slot.json")
            session = self.new("relique")
            store.save(session)
            first = session.recording()
            session.choose_story_option("guard")
            store.save(session)
            store.path.write_text('{"incomplete":', encoding="utf-8")
            outcome = store.load_with_status(self.content, self.project)
            self.assertEqual(outcome.source, "backup")
            self.assertEqual(outcome.sequence, 1)
            self.assertEqual(outcome.session.recording(), first)
            # Saving the recovered session preserves the good recovery file,
            # never promoting the damaged primary to backup.
            store.save(outcome.session)
            self.assertEqual(store.load(self.content, self.project).recording(), first)
            self.assertEqual(store.load_with_status(self.content, self.project).sequence, 2)

    def test_failed_publish_keeps_last_valid_generation(self):
        with TemporaryDirectory() as directory:
            store = SessionStore(Path(directory) / "checkpoint.json")
            session = self.new()
            store.save(session)
            previous = store.path.read_bytes()
            session.start_mission("garden")
            from sporebound.persistence import write_json as real_write
            def fail_primary(path, data):
                if Path(path) == store.path:
                    raise OSError("simulated disk interruption")
                return real_write(path, data)
            with patch("sporebound.persistence.write_json", side_effect=fail_primary):
                with self.assertRaises(OSError):
                    store.save(session)
            self.assertEqual(store.path.read_bytes(), previous)
            self.assertEqual(store.load_with_status(
                self.content, self.project).sequence, 1)

    def test_corruption_rejected_without_overwriting_last_good(self):
        with TemporaryDirectory() as directory:
            store = SessionStore(Path(directory) / "checkpoint.json")
            session = self.new()
            store.save(session)
            original = store.path.read_bytes()
            altered = json.loads(store.path.read_text(encoding="utf-8"))
            altered["session"]["progress"]["gold"] = 999
            store.path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(RuleError):
                store.load(self.content, self.project)
            with self.assertRaises(RuleError):
                store.save(session)
            self.assertNotEqual(store.path.read_bytes(), original)

    def test_legacy_v1_session_upgrades_without_losing_progress(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "previous.json"
            session = self.new("relique")
            session.choose_story_option("guard")
            session.save(path)
            legacy = path.read_bytes()
            store = SessionStore(path)
            loaded = store.load_with_status(self.content, self.project)
            self.assertTrue(loaded.migrated_from_v1)
            self.assertEqual(loaded.sequence, 0)
            self.assertEqual(loaded.session.recording(), session.recording())
            store.save(loaded.session)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["version"], 2)
            self.assertEqual(json.loads(store.backup.read_text(encoding="utf-8")),
                             json.loads(legacy.decode("utf-8")))
            self.assertEqual(json.loads(store.backup.read_text(encoding="utf-8"))["version"], 1)

    def test_legacy_campaign_slot_import_never_modifies_source(self):
        with TemporaryDirectory() as directory:
            profile = Path(directory) / "my.game.json"
            legacy = PlayerSession(self.content, self.project, profile)
            legacy.new_game("main", 1)
            legacy_path = profile.with_name(profile.stem + "_saves") / "main" / "slot_1.json"
            data = legacy_path.read_bytes()
            imported = SessionStore.import_player_slot(
                profile, self.project, self.content, "main", 1)
            self.assertEqual(imported.progress, legacy.progress)
            self.assertEqual(imported.mode, "campaign")
            SessionStore(Path(directory) / "unified.json").save(imported)
            self.assertEqual(legacy_path.read_bytes(), data)

    def test_tactical_replay_and_autosave_only_after_success(self):
        with TemporaryDirectory() as directory:
            store = SessionStore(Path(directory) / "autosave.json")
            session = self.new()
            autosave = AutosaveSession(session, store)
            autosave.perform("start_mission", "garden")
            first = store.path.read_bytes()
            with self.assertRaises(RuleError):
                autosave.perform("execute", {"kind": "invalid_action"})
            self.assertEqual(store.path.read_bytes(), first)
            autosave.perform("execute", {"kind": "end", "facing": [0, 1]})
            loaded = store.load(self.content, self.project)
            self.assertEqual(loaded.battle.digest(), session.battle.digest())
            self.assertEqual(loaded.battle.commands, session.battle.commands)
            with self.assertRaises(RuleError):
                autosave.perform("__class__")

    def test_project_identity_and_unknown_future_versions_rejected(self):
        with TemporaryDirectory() as directory:
            store = SessionStore(Path(directory) / "checkpoint.json")
            session = self.new()
            store.save(session)
            from copy import deepcopy
            changed = deepcopy(self.project)
            changed.title += " changed"
            with self.assertRaises(RuleError):
                store.load(self.content, changed)
            obj = json.loads(store.path.read_text(encoding="utf-8"))
            obj["version"] = 999
            store.path.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(RuleError):
                store.load(self.content, self.project)

    def test_size_limit_fails_before_writing(self):
        with TemporaryDirectory() as directory:
            store = SessionStore(Path(directory) / "small.json", max_bytes=256)
            with self.assertRaises(RuleError):
                store.save(self.new())
            self.assertFalse(store.path.exists())


if __name__ == "__main__":
    unittest.main()

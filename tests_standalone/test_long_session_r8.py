"""R8.9-R8.12: crash, migration, journal, dedupe and multi-front gates."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.reliability_gate import fixture
from sporebound.game_session import GameSession
from sporebound.long_session import LongSessionAutosave, LongSessionStore
from sporebound.model import RuleError
from sporebound.persistence import SessionStore


class LongSessionTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = fixture()

    def make(self, root, *, interval=8):
        store = LongSessionStore(Path(root) / "save.json", checkpoint_every=interval)
        session = GameSession.new(self.content, self.project, "main", seed=17)
        store.initialize(session)
        return store, LongSessionAutosave(session, store)

    def assert_resumes(self, store, actor):
        loaded = store.load_with_status(self.content, self.project)
        self.assertEqual(loaded.session.recording(), actor.session.recording())
        return loaded

    def test_short_journal_roundtrip_and_deduplicate_retried_request(self):
        with TemporaryDirectory() as root:
            store, actor = self.make(root)
            self.assertTrue(actor.perform("story-1", "choose_story_option", "assault").applied)
            self.assertEqual(self.assert_resumes(store, actor).applied, 1)
            before = actor.session.recording()
            self.assertFalse(actor.perform("story-1", "choose_story_option", "assault").applied)
            self.assertEqual(actor.session.recording(), before)
            self.assertEqual(store.load(self.content, self.project).recording(), before)

    def test_compaction_keeps_recent_receipts_and_monotonic_generation(self):
        with TemporaryDirectory() as root:
            store, actor = self.make(root, interval=2)
            actor.perform("story", "choose_story_option", "assault")
            done = actor.perform("start", "start_mission", "gate")
            self.assertTrue(done.compacted)
            self.assertEqual(self.assert_resumes(store, actor).applied, 0)
            self.assertEqual(SessionStore(store.store.path).load_with_status(
                self.content, self.project).sequence, 2)
            self.assertFalse(actor.perform("story", "choose_story_option", "assault").applied)
            actor.perform("end-1", "execute", {"kind": "end"})
            self.assert_resumes(store, actor)
            self.assertEqual(len(actor.session.battle.commands), 1)

    def test_crash_before_journal_publication_rolls_back_in_memory(self):
        with TemporaryDirectory() as root:
            store, actor = self.make(root)
            original = actor.session.recording()
            old_bytes = store.journal.read_bytes()
            with patch("sporebound.long_session.write_json",
                       side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    actor.perform("story", "choose_story_option", "assault")
            self.assertEqual(actor.session.recording(), original)
            self.assertEqual(store.journal.read_bytes(), old_bytes)

    def test_crash_between_checkpoint_and_journal_truncation_is_exactly_once(self):
        with TemporaryDirectory() as root:
            store, actor = self.make(root, interval=1)
            real = store._publish
            count = [0]

            def stop_after_checkpoint(obj):
                count[0] += 1
                if count[0] == 2:
                    raise OSError("interrupted journal cleanup")
                return real(obj)

            with patch.object(store, "_publish", side_effect=stop_after_checkpoint):
                result = actor.perform("story", "choose_story_option", "assault")
            self.assertTrue(result.applied)
            self.assertFalse(result.compacted)
            resumed = self.assert_resumes(store, actor)
            self.assertEqual(resumed.applied, 0)
            self.assertFalse(actor.perform("story", "choose_story_option", "assault").applied)
            # New operation must replace stale journal, not apply old actions.
            actor.perform("start", "start_mission", "gate")
            self.assert_resumes(store, actor)

    def test_verified_backup_requires_explicit_restore_and_retains_evidence(self):
        with TemporaryDirectory() as root:
            store, actor = self.make(root, interval=1)
            actor.perform("story", "choose_story_option", "assault")
            store.store.path.write_bytes(b'{"truncated":')
            result = store.load_with_status(self.content, self.project)
            self.assertEqual(result.source, "backup")
            self.assertTrue(result.degraded)
            self.assertNotEqual(result.session.recording(), actor.session.recording())
            with self.assertRaisesRegex(RuleError, "acknowledgement"):
                store.restore(result, expected_digest="0" * 64)
            restored = store.restore(result,
                                     expected_digest=result.session.recording()["digest"])
            self.assertEqual(restored.source, "primary")
            self.assertEqual(restored.session.recording(), result.session.recording())
            self.assertEqual((Path(root) / "save.json.damaged").read_bytes(),
                             b'{"truncated":')

    def test_explicit_v1_to_long_session_preserves_original_bytes(self):
        with TemporaryDirectory() as root:
            source = Path(root) / "legacy.json"
            session = GameSession.new(self.content, self.project, "main", seed=5)
            source.write_text(json.dumps(session.recording(), separators=(",", ":")),
                              encoding="utf-8")
            original = source.read_bytes()
            destination = LongSessionStore(Path(root) / "new.json")
            migrated = destination.migrate_from(source, self.content, self.project)
            self.assertTrue(migrated.migrated_from_v1)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(destination.load(self.content, self.project).recording(),
                             session.recording())
            with self.assertRaises(RuleError):
                destination.migrate_from(source, self.content, self.project)

    def test_migration_refuses_modified_content_without_touching_source(self):
        with TemporaryDirectory() as root:
            source = Path(root) / "legacy.json"
            session = GameSession.new(self.content, self.project, "main", seed=5)
            session.save(source)
            original = source.read_bytes()
            changed = deepcopy(self.project)
            changed.title = "Incompatible release"
            dest = LongSessionStore(Path(root) / "new.json")
            with self.assertRaises(RuleError):
                dest.migrate_from(source, self.content, changed)
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse(dest.store.path.exists())

    def test_malformed_journal_never_silently_drops_committed_actions(self):
        with TemporaryDirectory() as root:
            store, actor = self.make(root)
            actor.perform("story", "choose_story_option", "assault")
            store.journal.write_bytes(b'{"bad":')
            with self.assertRaises(RuleError):
                store.load(self.content, self.project)
            self.assertEqual(SessionStore(store.store.path).load(
                self.content, self.project).mode, "campaign")

    def test_multifront_focus_strategy_and_offscreen_history_are_replayed(self):
        with TemporaryDirectory() as root:
            store, actor = self.make(root, interval=4)
            actor.perform("story", "choose_story_option", "assault")
            actor.perform("fronts", "start_fronts", {"gate": "gate", "walls": "walls"},
                          "gate", specs={"gate": {"strength": 20, "opposition": 20},
                                         "walls": {"strength": 20, "opposition": 20}})
            actor.perform("end", "execute", {"kind": "end"})
            actor.perform("doctrine", "set_doctrine", "walls", "assault")
            actor.perform("advance", "advance_fronts")
            actor.perform("focus", "switch_front", "walls")
            loaded = self.assert_resumes(store, actor).session
            self.assertEqual(loaded.mode, "fronts")
            self.assertEqual(loaded.fronts.recording(), actor.session.fronts.recording())
            self.assertEqual(loaded.fronts.timeline.state(),
                             actor.session.fronts.timeline.state())
            self.assertEqual(loaded.fronts.history, actor.session.fronts.history)

    def test_long_command_history_survives_multiple_compactions(self):
        with TemporaryDirectory() as root:
            store, actor = self.make(root, interval=7)
            actor.perform("story", "choose_story_option", "assault")
            actor.perform("start", "start_mission", "gate")
            for i in range(45):
                actor.perform("turn-" + str(i), "execute", {"kind": "end"})
            loaded = self.assert_resumes(store, actor).session
            self.assertEqual(len(loaded.battle.commands), 45)
            self.assertEqual(loaded.battle.digest(), actor.session.battle.digest())
            self.assertGreater(store.store.load_with_status(
                self.content, self.project).sequence, 4)


if __name__ == "__main__":
    unittest.main()

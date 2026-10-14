"""R8.17: headless real-process durability gates (no Tk or fake save format)."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.persistence_fault_lab import (
    CUTS, run_concurrent_lock_gate, run_matrix,
)
from examples.reliability_gate import fixture
from sporebound.game_session import GameSession
from sporebound.long_session import LongSessionStore
from sporebound.model import RuleError


class PersistenceFaultLabTests(unittest.TestCase):
    def test_all_atomic_publication_cut_points_recover_once(self):
        result = run_matrix(seeds=(17,))
        self.assertTrue(result["verified"])
        self.assertEqual(len(result["cases"]), len(CUTS))
        for row in result["cases"]:
            with self.subTest(cut=row["cut"]):
                self.assertTrue(row["verified"])
                self.assertEqual(row["final_digest"], self._expected_digest())
                self.assertEqual(row["retry_applied"], not row["committed_at_cut"])
                self.assertGreaterEqual(row["checkpoint_sequence"], 1)

    @staticmethod
    def _expected_digest():
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=17)
        session.choose_story_option("assault")
        return session.recording()["digest"]

    def test_true_other_process_lock_rejects_contender_then_allows_writer(self):
        outcome = run_concurrent_lock_gate()
        self.assertTrue(outcome["verified"])
        self.assertTrue(outcome["concurrent_writer_rejected"])

    def test_tampered_journal_cannot_silently_fall_back_to_old_snapshot(self):
        content, project = fixture()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "save.json"
            store = LongSessionStore(path, checkpoint_every=5)
            session = GameSession.new(content, project, "main", seed=17)
            store.initialize(session)
            store.perform(session, "event1", "choose_story_option", "assault")
            journal = json.loads(store.journal.read_text(encoding="utf-8"))
            journal["entries"][0]["after"] = "0" * 64
            store.journal.write_text(json.dumps(journal), encoding="utf-8")
            with self.assertRaisesRegex(RuleError, "checksum"):
                store.load(content, project)
            self.assertFalse(path.with_name(path.name + ".lock").exists())

    def test_unknown_format_does_not_erase_fault_evidence(self):
        content, project = fixture()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "save.json"
            store = LongSessionStore(path)
            session = GameSession.new(content, project, "main", seed=17)
            store.initialize(session)
            original = path.read_bytes()
            store.journal.write_bytes(b"\\x00truncated")
            with self.assertRaises(RuleError):
                store.compact(content, project)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(store.journal.read_bytes(), b"\\x00truncated")
            self.assertFalse(path.with_name(path.name + ".lock").exists())


if __name__ == "__main__":
    unittest.main()

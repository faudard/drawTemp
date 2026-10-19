"""R17.11: Studio two-document journal reviews and consent-bound recovery."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from drawtemp.sdk.reference import reference_project
from sporebound.model import RuleError
from sporebound.studio_transaction import StudioTransactionStore


class StudioReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "studio.json"
        self.store = StudioTransactionStore(self.path)
        content, project = reference_project()
        self.base_content, self.base_project = content.to_dict(), project.to_dict()
        self.next_content = deepcopy(self.base_content)
        self.next_project = deepcopy(self.base_project)
        self.next_content["missions"][0]["name"] = "Campagne révisée"
        self.next_project["title"] = "Projet révisé"

    def interrupt(self, *, initial=False):
        if not initial:
            self.store.save(self.base_content, self.base_project)
            previous = tuple(p.read_bytes() for p in self.store.paths)
        else:
            previous = (None, None)
        original = self.store._publish_one
        calls = []

        def fail_second(path):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("injected power loss between two JSON publishes")
            original(path)

        with patch.object(self.store, "_publish_one", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "power loss"):
                self.store.save(self.next_content, self.next_project)
        self.assertTrue(self.store.pending)
        return previous

    def test_review_is_read_only_and_both_verified_outcomes_available(self):
        self.interrupt()
        before = (tuple(p.read_bytes() for p in self.store.paths),
                  self.store.journal.read_bytes())
        report = self.store.inspect_recovery()
        self.assertEqual(set(report["choices"]), {"complete", "rollback"})
        self.assertTrue(report["choices"]["complete"]["available"])
        self.assertTrue(report["choices"]["rollback"]["available"])
        self.assertEqual(len(report["fingerprints"]), 7)
        self.assertEqual((tuple(p.read_bytes() for p in self.store.paths),
                          self.store.journal.read_bytes()), before)
        self.assertTrue(self.store.pending)

    def test_user_complete_restores_valid_content_and_game_project(self):
        self.interrupt()
        review = self.store.inspect_recovery()
        self.store.recover("complete", expected_fingerprints=review["fingerprints"])
        self.assertFalse(self.store.pending)
        reopened = AuthoringSession.open(self.path).snapshot().to_dict()
        self.assertEqual(reopened["content"]["missions"][0]["name"],
                         self.next_content["missions"][0]["name"])
        self.assertEqual(reopened["project"]["title"], self.next_project["title"])

    def test_user_rollback_restores_exact_original_bytes(self):
        original = self.interrupt()
        review = self.store.inspect_recovery()
        self.store.recover("rollback", expected_fingerprints=review["fingerprints"])
        self.assertFalse(self.store.pending)
        self.assertEqual(tuple(p.read_bytes() for p in self.store.paths), original)

    def test_stage_edit_after_review_blocks_restoration_and_keeps_journal(self):
        self.interrupt()
        approved = self.store.inspect_recovery()["fingerprints"]
        staged_project = self.store._stage(self.store.project_path)
        staged_project.write_bytes(b"external modified staging file")
        before = tuple(p.read_bytes() for p in self.store.paths)
        with self.assertRaisesRegex(RuleError, "obsolète"):
            self.store.recover("complete", expected_fingerprints=approved)
        self.assertEqual(tuple(p.read_bytes() for p in self.store.paths), before)
        self.assertTrue(self.store.pending)
        report = self.store.inspect_recovery()
        self.assertFalse(report["choices"]["complete"]["available"])
        self.assertTrue(report["choices"]["rollback"]["available"])

    def test_changed_user_owned_target_blocks_both_choices(self):
        self.interrupt()
        approved = self.store.inspect_recovery()["fingerprints"]
        original_external = b'{"third_party":"modified"}'
        self.store.project_path.write_bytes(original_external)
        with self.assertRaisesRegex(RuleError, "obsolète"):
            self.store.recover("rollback", expected_fingerprints=approved)
        self.assertEqual(self.store.project_path.read_bytes(), original_external)
        review = self.store.inspect_recovery()
        self.assertFalse(review["choices"]["complete"]["available"])
        self.assertFalse(review["choices"]["rollback"]["available"])
        self.assertTrue(self.store.pending)

    def test_missing_initial_save_can_be_rolled_back_with_confirmation(self):
        self.interrupt(initial=True)
        inspection = self.store.inspect_recovery()
        self.assertTrue(inspection["choices"]["rollback"]["available"])
        self.store.recover("rollback", expected_fingerprints=inspection["fingerprints"])
        self.assertFalse(any(p.exists() for p in self.store.paths))
        self.assertFalse(self.store.pending)

    def test_foreign_or_corrupt_journal_cannot_be_accepted(self):
        self.interrupt()
        data = json.loads(self.store.journal.read_text(encoding="utf-8"))
        data["paths"][0] = "/unknown/foreign.json"
        self.store.journal.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(RuleError):
            self.store.inspect_recovery()
        self.assertTrue(self.store.pending)

    def test_external_conflict_preserves_authoring_state_and_copy(self):
        authoring = AuthoringSession.new(*reference_project())
        self.assertFalse(authoring.storage_status()["has_destination"])
        authoring.save_as(self.path)
        self.assertFalse(authoring.storage_status()["external_change"])
        plan = authoring.preview_project(
            lambda project: {**project, "title": "Édition locale"},
            kind="title")
        authoring.apply(plan)
        self.store.project_path.write_bytes(self.store.project_path.read_bytes() + b" ")
        status = authoring.storage_status()
        self.assertTrue(status["external_change"])
        external = self.store.project_path.read_bytes()
        with self.assertRaises(AuthoringError):
            authoring.save()
        self.assertEqual(self.store.project_path.read_bytes(), external)
        self.assertTrue(authoring.snapshot().dirty)
        copy = self.path.with_name("copie.json")
        authoring.save_as(copy)
        saved = AuthoringSession.open(copy).snapshot().to_dict()
        self.assertEqual(saved["project"]["title"], "Édition locale")
        self.assertEqual(self.store.project_path.read_bytes(), external)


if __name__ == "__main__":
    unittest.main()

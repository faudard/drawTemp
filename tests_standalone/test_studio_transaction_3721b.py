"""3.7.21B regression gate: cross-document undo and recoverable Save All."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.studio_transaction import StudioHistory, StudioTransactionStore


class StudioHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)

    def setUp(self):
        self.before = self.content.to_dict()
        self.project = GameProject.default(self.content)

    def changed(self):
        data = deepcopy(self.before)
        data["missions"][0]["name"] += " — changed"
        project = self.project.to_dict()
        project["title"] = "Jeanne — Valcroix"
        return data, project

    def test_cross_document_change_is_one_step(self):
        data, project = self.changed()
        history = StudioHistory(self.before, self.project)
        self.assertTrue(history.record(data, project))
        self.assertFalse(history.record(data, project))  # No-op isn't a step.
        self.assertTrue(history.can_undo)
        restored_content, restored_project = history.undo()
        self.assertEqual(restored_content, self.before)
        self.assertEqual(restored_project.to_dict(), self.project.to_dict())
        self.assertTrue(history.can_redo)
        content, manifest = history.redo()
        self.assertEqual(content, data)
        self.assertEqual(manifest.to_dict(), project)

    def test_new_edit_invalidates_redo(self):
        data, project = self.changed()
        history = StudioHistory(self.before, self.project, limit=2)
        history.record(data, project)
        history.undo()
        variant = deepcopy(project)
        variant["title"] = "Second route"
        history.record(self.before, variant)
        self.assertFalse(history.can_redo)
        with self.assertRaises(RuleError):
            history.redo()

    def test_invalid_undo_does_not_advance_cursor(self):
        data, project = self.changed()
        history = StudioHistory(self.before, self.project)
        # A bad snapshot must not partially change Content or GameProject.
        history.record(data, project)
        history._states[0][1]["campaigns"][0]["start_mission"] = "unknown"
        with self.assertRaises(RuleError):
            history.undo()
        self.assertTrue(history.can_undo)
        self.assertFalse(history.can_redo)


class StudioTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)

    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "jeanne.json"
        self.store = StudioTransactionStore(self.path)
        self.initial = self.content.to_dict()
        self.project = GameProject.default(self.content).to_dict()
        self.new = deepcopy(self.initial)
        self.new["missions"][0]["name"] += " — mission révisée"
        self.next_project = deepcopy(self.project)
        self.next_project["title"] = "Jeanne — reprise"

    def first_save(self):
        self.store.save(self.initial, self.project)
        return tuple(p.read_bytes() for p in self.store.paths)

    def interrupt_second_publish(self, content, project):
        original = self.store._publish_one
        calls = []
        def partial(path):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("power loss during project publish")
            return original(path)
        with patch.object(self.store, "_publish_one", side_effect=partial):
            with self.assertRaisesRegex(OSError, "power loss"):
                self.store.save(content, project)
        self.assertTrue(self.store.pending)

    def test_save_and_load_two_validated_documents(self):
        self.store.save(self.initial, self.project)
        self.assertFalse(self.store.pending)
        self.assertEqual(Content.load(self.store.content_path).to_dict(), self.initial)
        self.assertEqual(GameProject.load(self.store.project_path, self.content).to_dict(),
                         self.project)

    def test_expected_revisions_protect_both_documents_against_external_edits(self):
        originals = self.first_save()
        baseline = self.store.revisions()
        for index in (0, 1):
            path = self.store.paths[index]
            changed = path.read_bytes() + b" "
            path.write_bytes(changed)
            with self.assertRaisesRegex(RuleError, "changé sur disque"):
                self.store.save(self.new, self.next_project,
                                expected_previous=baseline)
            self.assertEqual(path.read_bytes(), changed)
            self.assertFalse(self.store.pending)
            path.write_bytes(originals[index])
        self.store.save(self.new, self.next_project, expected_previous=baseline)
        self.assertNotEqual(self.store.revisions(), baseline)

    def test_committed_content_changed_before_project_publish_keeps_journal(self):
        self.first_save()
        original_publish = self.store._publish_one
        external = b'{"changed":"racing content writer"}'
        def interfere(path):
            original_publish(path)
            if path == self.store.content_path:
                self.store.content_path.write_bytes(external)
        with patch.object(self.store, "_publish_one", side_effect=interfere):
            with self.assertRaisesRegex(RuleError, "modifié pendant"):
                self.store.save(self.new, self.next_project)
        self.assertEqual(self.store.content_path.read_bytes(), external)
        self.assertTrue(self.store.pending)
        with self.assertRaisesRegex(RuleError, "modifié"):
            self.store.recover("complete")

    def test_edit_during_staging_never_replaces_destination(self):
        self.first_save()
        from sporebound import studio_transaction as transactions
        original_write = transactions.write_bytes
        changed = b'{"changed":"outside Studio"}'
        calls = []
        def interfere(path, raw):
            original_write(path, raw)
            calls.append(path)
            if len(calls) == 1:
                self.store.project_path.write_bytes(changed)
        with patch.object(transactions, "write_bytes", side_effect=interfere):
            with self.assertRaisesRegex(RuleError, "pendant la préparation"):
                self.store.save(self.new, self.next_project)
        self.assertEqual(self.store.project_path.read_bytes(), changed)
        self.assertFalse(self.store.pending)

    def test_edit_between_publishes_blocks_second_overwrite(self):
        self.first_save()
        original_publish = self.store._publish_one
        external = b'{"changed":"another writer"}'
        calls = []
        def interfere(path):
            original_publish(path)
            calls.append(path)
            if len(calls) == 1:
                self.store.project_path.write_bytes(external)
        with patch.object(self.store, "_publish_one", side_effect=interfere):
            with self.assertRaisesRegex(RuleError, "modifié pendant la sauvegarde"):
                self.store.save(self.new, self.next_project)
        self.assertEqual(self.store.project_path.read_bytes(), external)
        self.assertTrue(self.store.pending)
        with self.assertRaisesRegex(RuleError, "modifié"):
            self.store.recover("rollback")

    def test_invalid_project_aborts_without_creating_files(self):
        bad = deepcopy(self.project)
        bad["campaigns"][0]["start_mission"] = "not_a_mission"
        with self.assertRaises(RuleError):
            self.store.save(self.initial, bad)
        self.assertFalse(any(path.exists() for path in self.store.paths))
        self.assertFalse(self.store.pending)

    def test_failed_replacement_rolls_back_exact_bytes(self):
        originals = self.first_save()
        self.interrupt_second_publish(self.new, self.next_project)
        self.assertNotEqual(self.store.content_path.read_bytes(), originals[0])
        self.assertEqual(self.store.project_path.read_bytes(), originals[1])
        # Never permit another Save All before resolving the pending journal.
        with self.assertRaisesRegex(RuleError, "interrompu"):
            self.store.save(self.new, self.next_project)
        self.store.recover("rollback")
        self.assertEqual(tuple(p.read_bytes() for p in self.store.paths), originals)
        self.assertFalse(self.store.pending)

    def test_failed_replacement_can_complete_new_generation(self):
        self.first_save()
        self.interrupt_second_publish(self.new, self.next_project)
        self.store.recover("complete")
        # Content.to_dict() contains tuple coordinates; JSON restores lists.
        self.assertEqual(json.loads(self.store.content_path.read_text(encoding="utf-8")),
                         json.loads(json.dumps(self.new)))
        self.assertEqual(json.loads(self.store.project_path.read_text(encoding="utf-8")),
                         self.next_project)
        self.assertFalse(self.store.pending)
        with self.assertRaises(RuleError):
            self.store.recover("complete")

    def test_first_save_can_rollback_to_two_missing_files(self):
        self.interrupt_second_publish(self.initial, self.project)
        self.store.recover("rollback")
        self.assertFalse(self.store.content_path.exists())
        self.assertFalse(self.store.project_path.exists())
        self.assertFalse(self.store.pending)

    def test_external_edits_block_recovery_without_overwrite(self):
        originals = self.first_save()
        self.interrupt_second_publish(self.new, self.next_project)
        external = b'{"external":"user edits"}'
        self.store.project_path.write_bytes(external)
        with self.assertRaisesRegex(RuleError, "modifié"):
            self.store.recover("rollback")
        self.assertEqual(self.store.project_path.read_bytes(), external)
        self.assertNotEqual(self.store.content_path.read_bytes(), originals[0])
        self.assertTrue(self.store.pending)

    def test_corrupted_backup_blocks_rollback_before_any_write(self):
        self.first_save()
        self.interrupt_second_publish(self.new, self.next_project)
        before = tuple(p.read_bytes() for p in self.store.paths)
        self.store._backup(self.store.content_path).write_bytes(b"corrupt")
        with self.assertRaisesRegex(RuleError, "altéré"):
            self.store.recover("rollback")
        self.assertEqual(tuple(p.read_bytes() for p in self.store.paths), before)
        self.assertTrue(self.store.pending)


if __name__ == "__main__":
    unittest.main()

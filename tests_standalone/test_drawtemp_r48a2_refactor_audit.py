"""R48.A2 regression: typed cross-document rename + local audit durability."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.project_audit import AuditError, LocalAuditLog
from drawtemp.sdk.project_refactor import (
    RefactorError, apply_rename, preview_rename,
)
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.semantic_review import fingerprint_pair


class ProjectRefactorTests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)
        self.initial = self.session.snapshot().to_dict()

    def test_scene_preview_rewrites_cross_document_links_and_undo(self):
        before = self.session.snapshot().to_dict()
        plan = preview_rename(self.session, "scene:arrival", "arrival_2")
        self.assertEqual(self.session.snapshot().to_dict(), before)
        self.assertIn("/project/story/scenes/arrival", plan.affected_paths)
        self.assertIn("/project/story/entry_scenes/main", plan.affected_paths)
        result = apply_rename(self.session, plan)
        self.assertEqual(result.snapshot.project["story"]["entry_scenes"]["main"],
                         "arrival_2")
        self.assertEqual(result.snapshot.project["story"]["scenes"][0]["id"],
                         "arrival_2")
        self.assertEqual(self.session.undo().snapshot.to_dict()["project"],
                         before["project"])

    def test_object_local_links_and_one_undo(self):
        key = "map_object:r0_village_forest/gate"
        plan = preview_rename(self.session, key, "gate2")
        self.assertIn("/content/missions/r0_village_forest/objects", plan.affected_paths)
        result = apply_rename(self.session, plan)
        objects = result.snapshot.content["missions"][0]["objects"]
        self.assertEqual(objects[0]["id"], "gate2")
        self.assertEqual(objects[1]["link"], "gate2")
        restored = self.session.undo().snapshot.content["missions"][0]["objects"]
        self.assertEqual(restored[0]["id"], "gate")
        self.assertEqual(restored[1]["link"], "gate")

    def test_campaign_refuses_unsaved_and_foreign_slot_directory(self):
        with self.assertRaises(RefactorError) as caught:
            preview_rename(self.session, "campaign:main", "main_new")
        self.assertEqual(caught.exception.code, "unsafe_save_slots")
        with TemporaryDirectory() as temp:
            file = Path(temp) / "projects/game.json"
            file.parent.mkdir()
            self.session.save_as(file)
            with self.assertRaises(RefactorError) as caught:
                preview_rename(self.session, "campaign:main", "main_new",
                               project_path=Path(temp) / "other.json")
            self.assertEqual(caught.exception.code, "wrong_destination")
            directory = file.with_name(file.stem + "_saves") / "main"
            directory.mkdir(parents=True)
            with self.assertRaises(RefactorError):
                preview_rename(self.session, "campaign:main", "main_new")
            directory.rmdir()
            planned = preview_rename(self.session, "campaign:main", "main_new",
                                     project_path=file)
            changed = apply_rename(self.session, planned)
            self.assertEqual(changed.snapshot.project["campaigns"][0]["id"], "main_new")
            self.assertEqual(changed.snapshot.project["story"]["entry_scenes"]["main_new"],
                             "arrival")
            self.assertTrue(changed.snapshot.dirty)
            self.assertTrue(file.is_file())

    def test_stale_aba_refuses_without_mutation(self):
        planned = preview_rename(self.session, "scene:arrival", "arrival_2")
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "title": "temporary"}))
        self.session.undo()
        before = self.session.snapshot().to_dict()
        with self.assertRaises(RefactorError) as caught:
            apply_rename(self.session, planned)
        self.assertEqual(caught.exception.code, "stale_preview")
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_opaque_reference_refused_instead_of_text_replacement(self):
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "story": {**p["story"], "scenes": [
                {**p["story"]["scenes"][0], "text": "arrival"}]}}))
        before = self.session.snapshot().to_dict()
        with self.assertRaises(RefactorError) as caught:
            preview_rename(self.session, "scene:arrival", "arrival_2")
        self.assertEqual(caught.exception.code, "unsupported_reference")
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_conflicting_ids_and_tampered_preview_rejected(self):
        before = self.session.snapshot().to_dict()
        with self.assertRaises(RefactorError):
            preview_rename(self.session, "scene:arrival", "bad/name")
        planned = preview_rename(self.session, "scene:arrival", "arrival_2")
        tampered = replace(planned, after_digest="0" * 64)
        with self.assertRaises(RefactorError) as caught:
            apply_rename(self.session, tampered)
        self.assertEqual(caught.exception.code, "changed_preview")
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_foreign_authoring_session_rejects_plan(self):
        planned = preview_rename(self.session, "scene:arrival", "arrival_2")
        other = AuthoringSession.new(self.initial["content"], self.initial["project"])
        with self.assertRaises(ValueError):
            apply_rename(other, planned)


class AuditLogTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "reviews.jsonl"
        self.audit = LocalAuditLog(self.path)
        self.a, self.b, self.c = "a" * 64, "b" * 64, "c" * 64

    def test_append_read_chain_and_stale_head(self):
        self.assertEqual(self.audit.inspect(), {"count": 0, "head": None})
        entry = self.audit.append(expected_head=None, actor="alice",
                                  operation="rename", resource="scene:arrival",
                                  before=self.a, after=self.b)
        self.assertEqual(entry["sequence"], 1)
        self.assertEqual(self.audit.inspect()["head"], entry["digest"])
        with self.assertRaises(AuditError) as caught:
            self.audit.append(expected_head=None, actor="bob",
                              operation="merge", resource="scene:arrival",
                              before=self.b, after=self.c)
        self.assertEqual(caught.exception.code, "stale_head")
        second = self.audit.append(expected_head=entry["digest"], actor="bob",
                                   operation="merge", resource="story",
                                   before=self.b, after=self.c)
        self.assertEqual(second["previous"], entry["digest"])
        self.assertEqual(len(self.audit.entries()), 2)
        self.assertEqual(self.audit.inspect()["count"], 2)

    def test_log_tampering_is_detected_without_overwriting(self):
        self.audit.append(expected_head=None, actor="alice",
                          operation="rename", resource="scene:arrival",
                          before=self.a, after=self.b)
        data = self.path.read_bytes().replace(b'"actor":"alice"', b'"actor":"bob"')
        self.path.write_bytes(data)
        with self.assertRaises(AuditError):
            self.audit.inspect()
        with self.assertRaises(AuditError):
            self.audit.append(expected_head=None, actor="alice",
                              operation="rename", resource="any",
                              before=self.a, after=self.b)
        self.assertEqual(self.path.read_bytes(), data)

    def test_crash_truncation_and_invalid_metadata(self):
        self.path.write_text('{"incomplete":', encoding="utf-8")
        with self.assertRaises(AuditError) as caught:
            self.audit.inspect()
        self.assertEqual(caught.exception.code, "truncated_log")
        self.path.unlink()
        with self.assertRaises(AuditError) as caught:
            self.audit.append(expected_head=None, actor="", operation="rename",
                              resource="scene:arrival", before=self.a, after=self.b)
        self.assertEqual(caught.exception.code, "invalid_metadata")
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()

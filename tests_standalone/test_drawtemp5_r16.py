"""R16: lossless project conversion, strict save import and retirement guardrails."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import GameSession
from drawtemp.sdk.legacy_migration import (
    MigrationError, import_save, inspect_save, migrate_project,
    plan_project, rollback_project,
)
from drawtemp.sdk.reference import reference_project
from scripts.inventory_drawtemp5_legacy import inventory
from sporebound.persistence import SessionStore


class R16MigrationTests(unittest.TestCase):
    def setUp(self):
        self.scratch = TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.content, self.project = reference_project()
        self.content_path = self.root / "source" / "jeanne.json"
        self.content_path.parent.mkdir()
        self.manifest_path = self.content_path.with_suffix(".game.json")
        self.content_path.write_text(
            json.dumps(self.content.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        self.manifest_path.write_text(
            json.dumps(self.project.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        self.originals = (self.content_path.read_bytes(), self.manifest_path.read_bytes())

    def test_plan_has_no_side_effects_and_migration_is_reversible(self):
        plan = plan_project(self.content_path)
        self.assertEqual(plan["strategy"], "canonical_v1_copy_with_exact_original_backup")
        bundle = self.root / "migrated"
        receipt = migrate_project(self.content_path, bundle)
        self.assertEqual(receipt["version"], 1)
        self.assertEqual(self.originals,
                         (self.content_path.read_bytes(), self.manifest_path.read_bytes()))
        self.assertEqual((bundle / "originals" / "jeanne.json").read_bytes(),
                         self.originals[0])
        self.assertEqual((bundle / "originals" / "jeanne.game.json").read_bytes(),
                         self.originals[1])
        self.assertEqual((bundle / "project" / "jeanne.json").read_bytes(), self.originals[0])
        self.assertEqual((bundle / "project" / "jeanne.game.json").read_bytes(), self.originals[1])
        # Canonical pair must be openable by the same authoring runtime.
        from drawtemp.sdk.authoring import AuthoringSession
        authoring = AuthoringSession.open(bundle / "project" / "jeanne.json")
        self.assertFalse(authoring.snapshot().dirty)
        restored = self.root / "restored"
        result = rollback_project(bundle, restored)
        self.assertTrue(result["originals_preserved"])
        self.assertEqual((restored / "jeanne.json").read_bytes(), self.originals[0])
        self.assertEqual((restored / "jeanne.game.json").read_bytes(), self.originals[1])
        self.assertTrue(bundle.is_dir())

    def test_no_overwrite_or_implicit_replacement(self):
        target = self.root / "migration"
        migrate_project(self.content_path, target)
        with self.assertRaises(MigrationError):
            migrate_project(self.content_path, target)
        rollback = self.root / "restore"
        rollback.mkdir()
        with self.assertRaises(MigrationError):
            rollback_project(target, rollback)
        self.assertEqual(self.originals,
                         (self.content_path.read_bytes(), self.manifest_path.read_bytes()))

    def test_tampering_fails_closed_and_cannot_publish_rollback(self):
        bundle = self.root / "migration"
        migrate_project(self.content_path, bundle)
        (bundle / "originals" / "jeanne.json").write_text('{"version": 7}', encoding="utf-8")
        with self.assertRaises(MigrationError):
            rollback_project(bundle, self.root / "restored")
        self.assertFalse((self.root / "restored").exists())

    def test_malformed_source_does_not_create_bundle(self):
        self.content_path.write_text('{"version": 99}', encoding="utf-8")
        with self.assertRaises(MigrationError):
            migrate_project(self.content_path, self.root / "new")
        self.assertFalse((self.root / "new").exists())

    def test_v1_save_import_is_verified_and_byte_identical(self):
        source = self.root / "save-v1.json"
        GameSession.new(self.content, self.project, "main", seed=17).save(source)
        original = source.read_bytes()
        destination = self.root / "imported" / "slot1.json"
        result = import_save(source, self.content_path, destination)
        self.assertEqual(result["kind"], "game_session_v1")
        self.assertEqual(original, destination.read_bytes())
        self.assertEqual(original, source.read_bytes())
        self.assertEqual(GameSession.load(destination, self.content, self.project)
                         .recording(), GameSession.load(source, self.content, self.project)
                         .recording())
        with self.assertRaises(MigrationError):
            import_save(source, self.content_path, destination)

    def test_v2_checkpoint_import_preserves_envelope(self):
        session = GameSession.new(self.content, self.project, "main", seed=17)
        path = self.root / "session-v2.json"
        SessionStore(path).save(session)
        result = inspect_save(path, self.content_path)
        self.assertEqual(result["kind"], "session_checkpoint_v2")
        destination = self.root / "restored-checkpoint.json"
        self.assertEqual(import_save(path, self.content_path, destination)["sequence"], 1)
        self.assertEqual(path.read_bytes(), destination.read_bytes())
        self.assertEqual(SessionStore(destination).load(self.content, self.project)
                         .recording(), session.recording())

    def test_unknown_legacy_slots_and_corrupt_saves_are_rejected(self):
        source = self.root / "unsupported.json"
        source.write_text('{"kind":"player_slot","version":1}', encoding="utf-8")
        with self.assertRaisesRegex(MigrationError, "Unsupported slot/replay"):
            import_save(source, self.content_path, self.root / "target.json")
        self.assertFalse((self.root / "target.json").exists())
        source = self.root / "damaged.json"
        record = GameSession.new(self.content, self.project, "main").recording()
        record["campaign_id"] = "another"
        source.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(MigrationError, "Incompatible/damaged"):
            inspect_save(source, self.content_path)

    def test_save_from_different_project_is_not_reinterpreted(self):
        source = self.root / "original-save.json"
        GameSession.new(self.content, self.project, "main").save(source)
        modified = self.project.to_dict()
        modified["title"] = "Different game"
        self.manifest_path.write_text(json.dumps(modified), encoding="utf-8")
        with self.assertRaisesRegex(MigrationError, "Incompatible/damaged"):
            import_save(source, self.content_path, self.root / "converted.json")
        self.assertFalse((self.root / "converted.json").exists())


class R16InventoryTests(unittest.TestCase):
    def test_flags_direct_qt_tk_but_does_not_claim_global_certification(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for path, code in (
                ("drawtemp/player/unsafe.py", "import tkinter as tk\n"),
                ("sporebound/old.py", "from tkinter import Canvas\n"),
                ("drawtemp/sdk/adapter.py", "from sporebound.game_session import GameSession\n"),
            ):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(code, encoding="utf-8")
            report = inventory(root)
            self.assertEqual(report["direct_qt_tk"], ["drawtemp/player/unsafe.py"])
            self.assertFalse(report["retirement_certified"])
            self.assertEqual(len(report["tk_modules"]), 2)
            self.assertEqual(report["compatibility_modules"][0]["path"],
                             "drawtemp/sdk/adapter.py")


if __name__ == "__main__":
    unittest.main()

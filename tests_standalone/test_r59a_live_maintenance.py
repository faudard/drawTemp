"""R59.A unit gates: no release approval, no in-place save overwrite."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.export.live_maintenance import (
    release_descriptor, validate_release_descriptor, plan_update,
    snapshot_saves, verify_save_snapshot, restore_saves,
)
from drawtemp.export.r15 import ExportError


def descriptor(version, digest, *, target="linux-x86_64", family="srpg", save_schema=2):
    return {
        "schema": 1, "kind": "drawtemp-r59-release-descriptor",
        "version": version, "revision": "a" * 40, "target": target,
        "family": family, "manifest_sha256": digest * 64,
        "dependencies_sha256": "f" * 64, "save_schema": save_schema,
        "readable_save_schemas": [save_schema],
        "decision": "NO-GO", "release_certified": False,
    }


class DescriptorTests(unittest.TestCase):
    def setUp(self):
        self.old = descriptor("1.0.0", "a")
        self.new = descriptor("1.1.0", "b")

    def test_release_is_bound_to_existing_r39_validation(self):
        plan = {"manifest_sha256": "b" * 64,
                "dependencies": [{"name": "Python", "version": "3.12", "license": "PSF-2.0"}]}
        with patch("drawtemp.export.live_maintenance.publication_plan", return_value=plan) as pub:
            record = release_descriptor("/bundle", {"verified": "via-r39"},
                                        version="1.1.0", revision="a" * 40,
                                        target="linux-x86_64", family="srpg", save_schema=2)
        pub.assert_called_once()
        self.assertEqual(record["decision"], "NO-GO")
        self.assertFalse(record["release_certified"])
        self.assertEqual(record["readable_save_schemas"], [2])
        validate_release_descriptor(record)

    def test_only_strict_versions_and_schemas_accepted(self):
        for version in ("1", "1.0", "1.0.0-rc", "01.0.0", "1.02.3", "1.0.00", "a.b.c"):
            with self.subTest(version=version):
                bad = dict(self.new, version=version)
                with self.assertRaises(ExportError):
                    validate_release_descriptor(bad)
        with self.assertRaises(ExportError):
            validate_release_descriptor(dict(self.new, save_schema=True))

    def test_unknown_approval_and_fake_migrations_rejected(self):
        for key, value in (
            ("decision", "GO"), ("release_certified", True),
            ("readable_save_schemas", [1, 2]), ("revision", "master"),
            ("manifest_sha256", "invalid"), ("target", "web"),
        ):
            with self.subTest(field=key):
                with self.assertRaises(ExportError):
                    validate_release_descriptor(dict(self.new, **{key: value}))
        with self.assertRaises(ExportError):
            validate_release_descriptor(dict(self.new, unreviewed=True))

    def test_upgrade_plans_are_never_release_approval(self):
        plan = plan_update(self.old, self.new, observed_save_schemas=[2])
        self.assertEqual(plan["compatibility"], "candidate")
        self.assertEqual(plan["decision"], "NO-GO")
        self.assertTrue(plan["blockers"])
        self.assertEqual(plan_update(self.new, self.old)["compatibility"], "blocked")
        self.assertEqual(plan_update(self.old, self.old)["compatibility"], "blocked")
        self.assertEqual(plan_update(self.old, self.new, observed_save_schemas=[1])["compatibility"], "blocked")
        self.assertEqual(plan_update(self.old, dict(self.new, family="roguelite"))["compatibility"], "blocked")
        with self.assertRaises(ExportError):
            plan_update(self.old, self.new, observed_save_schemas=[True])


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.saves = self.root / "saves"
        (self.saves / "campaign").mkdir(parents=True)
        (self.saves / "campaign" / "slot_1.json").write_bytes(b'{"v":1}\n')
        (self.saves / "campaign" / "slot_1.json.bak").write_bytes(b"legacy")
        self.snapshot = self.root / "snapshot"

    def test_snapshot_restore_roundtrip_is_non_destructive(self):
        before = {p.relative_to(self.saves): p.read_bytes()
                  for p in self.saves.rglob("*") if p.is_file()}
        record = snapshot_saves(self.saves, self.snapshot)
        self.assertEqual(len(record["files"]), 2)
        self.assertEqual(record, verify_save_snapshot(self.snapshot))
        restored = restore_saves(self.snapshot, self.root / "restored")
        self.assertEqual(before, {p.relative_to(restored): p.read_bytes()
                                  for p in restored.rglob("*") if p.is_file()})
        self.assertEqual(before, {p.relative_to(self.saves): p.read_bytes()
                                  for p in self.saves.rglob("*") if p.is_file()})

    def test_existing_destination_refused_without_mutation(self):
        snapshot_saves(self.saves, self.snapshot)
        target = self.root / "protected"
        target.mkdir()
        (target / "keep").write_text("never overwrite")
        with self.assertRaisesRegex(ExportError, "already exists"):
            restore_saves(self.snapshot, target)
        self.assertEqual((target / "keep").read_text(), "never overwrite")
        with self.assertRaisesRegex(ExportError, "already exists"):
            snapshot_saves(self.saves, self.snapshot)

    def test_tampered_bytes_block_restore_and_leave_target_absent(self):
        snapshot_saves(self.saves, self.snapshot)
        (self.snapshot / "files" / "campaign" / "slot_1.json").write_bytes(b"corrupt")
        target = self.root / "target"
        with self.assertRaisesRegex(ExportError, "checksum"):
            restore_saves(self.snapshot, target)
        self.assertFalse(target.exists())

    def test_manifest_duplicate_and_path_escape_rejected(self):
        snapshot_saves(self.saves, self.snapshot)
        manifest = self.snapshot / "snapshot.json"
        raw = json.loads(manifest.read_text())
        raw["files"][0]["path"] = "../escape"
        manifest.write_text(json.dumps(raw))
        with self.assertRaises(ExportError):
            verify_save_snapshot(self.snapshot)
        manifest.write_text('{"schema":1,"schema":1}')
        with self.assertRaisesRegex(ExportError, "Duplicate"):
            verify_save_snapshot(self.snapshot)

    def test_untracked_files_and_symlinks_rejected(self):
        snapshot_saves(self.saves, self.snapshot)
        (self.snapshot / "files" / "new-save.json").write_text("unexpected")
        with self.assertRaisesRegex(ExportError, "match manifest"):
            verify_save_snapshot(self.snapshot)
        (self.snapshot / "files" / "new-save.json").unlink()
        try:
            (self.saves / "linked.json").symlink_to(self.saves / "campaign" / "slot_1.json")
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable on this runner")
        with self.assertRaisesRegex(ExportError, "Linked"):
            snapshot_saves(self.saves, self.root / "second")

    def test_snapshot_destination_inside_save_root_refused(self):
        with self.assertRaisesRegex(ExportError, "overlap"):
            snapshot_saves(self.saves, self.saves / "snapshot")
        self.assertFalse((self.saves / "snapshot").exists())

    def test_snapshot_bytes_are_deterministic(self):
        first = snapshot_saves(self.saves, self.snapshot)
        second = snapshot_saves(self.saves, self.root / "snapshot-two")
        self.assertEqual(first, second)
        self.assertEqual((self.snapshot / "snapshot.json").read_bytes(),
                         (self.root / "snapshot-two" / "snapshot.json").read_bytes())


if __name__ == "__main__":
    unittest.main()

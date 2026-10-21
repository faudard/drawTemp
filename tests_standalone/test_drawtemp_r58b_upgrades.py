"""R58.B2: versioned upgrades, explicit downgrade, no-overwrite and Undo."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.assets.packs import install_pack, publish_pack, verify_installed_packs
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.package_upgrades import (
    PackageUpgradeError, apply_package_upgrade, preview_package_upgrade,
)
from tests_standalone.test_drawtemp5_r24c import make_manifest, make_source


class PackageUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.editor = AuthoringSession.new(*reference_project())
        self.old_path, self.old_pack = self.make_pack("1.0.0")
        install_pack(self.old_pack, self.editor, self.root)
        self.old_snapshot = self.editor.snapshot().to_dict()

    def make_pack(self, version, *, manifest_override=None):
        manifest = make_manifest()
        manifest["version"] = version
        if manifest_override is not None:
            manifest_override(manifest)
        source = make_source(self.root / ("source-" + version.replace(".", "-") +
                                          "-" + str(len(list(self.root.glob("source-*"))))),
                             manifest)
        archive = self.root / ("pack-" + version + "-" +
                               str(len(list(self.root.glob("pack-*")))) + ".rpack")
        return archive, publish_pack(source, archive)

    def preview(self, path, pack, *, downgrade=False):
        return preview_package_upgrade(
            self.editor, self.root, path,
            expected_sha256=pack.sha256,
            allow_downgrade=downgrade,
            expected_revision=self.editor.revision,
        )

    def version(self):
        row = self.editor.snapshot().to_dict()["project"]
        return row["extensions"]["org.drawtemp.resourcepacks"]["data"]["packs"][0]["version"]

    def test_upgrade_and_undo_redo_keep_both_versions(self):
        path, pack = self.make_pack("1.1.0")
        before = deepcopy(self.old_snapshot["project"])
        planned = self.preview(path, pack)
        self.assertFalse(planned.reuse_existing_bytes)
        self.assertFalse(planned.downgrade)
        self.assertEqual(planned.to_dict()["to_version"], "1.1.0")
        self.assertEqual(self.editor.snapshot().to_dict()["project"], before)
        result = apply_package_upgrade(planned, self.editor, self.root)
        self.assertEqual(result.snapshot.revision, 2)
        self.assertEqual(self.version(), "1.1.0")
        self.assertEqual(verify_installed_packs(
            self.root, self.editor.snapshot().to_dict()["project"]), [])
        self.assertTrue((self.root / "assets/packs/forest-pack/1.0.0/terrain/forest.png").is_file())
        self.assertTrue((self.root / "assets/packs/forest-pack/1.1.0/terrain/forest.png").is_file())
        self.editor.undo()
        self.assertEqual(self.version(), "1.0.0")
        self.assertEqual(self.editor.snapshot().to_dict()["project"], before)
        self.editor.redo()
        self.assertEqual(self.version(), "1.1.0")

    def test_explicit_downgrade_reuses_old_verified_files_and_save_reload(self):
        new_path, new_pack = self.make_pack("1.1.0")
        apply_package_upgrade(self.preview(new_path, new_pack), self.editor, self.root)
        with self.assertRaises(PackageUpgradeError) as error:
            self.preview(self.old_path, self.old_pack)
        self.assertEqual(error.exception.code, "downgrade_denied")
        plan = self.preview(self.old_path, self.old_pack, downgrade=True)
        self.assertTrue(plan.downgrade)
        self.assertTrue(plan.reuse_existing_bytes)
        self.assertEqual(plan.added_paths, ())
        apply_package_upgrade(plan, self.editor, self.root)
        self.assertEqual(self.version(), "1.0.0")
        self.editor.save_as(self.root / "game.json")
        reloaded = AuthoringSession.open(self.root / "game.json")
        self.assertEqual(
            verify_installed_packs(self.root, reloaded.snapshot().to_dict()["project"]), [])

    def test_digest_identity_and_version_must_change(self):
        path, pack = self.make_pack("1.1.0")
        with self.assertRaises(PackageUpgradeError) as digest:
            preview_package_upgrade(self.editor, self.root, path,
                                    expected_sha256="0" * 64)
        self.assertEqual(digest.exception.code, "digest_mismatch")
        with self.assertRaises(PackageUpgradeError) as same:
            self.preview(self.old_path, self.old_pack)
        self.assertEqual(same.exception.code, "same_version")
        with self.assertRaises(PackageUpgradeError) as pin:
            preview_package_upgrade(self.editor, self.root, path,
                                    expected_sha256="not-a-pin")
        self.assertEqual(pin.exception.code, "invalid_pin")

    def test_migrations_and_dependencies_refused_without_explicit_contract(self):
        path, pack = self.make_pack(
            "1.1.0",
            manifest_override=lambda m: (
                m["entries"][0].update(id="different"),
                m["entries"][1]["frames"][0].update(sprite="different"),
            ))
        with self.assertRaises(PackageUpgradeError) as error:
            self.preview(path, pack)
        self.assertEqual(error.exception.code, "migration_required")
        path2, pack2 = self.make_pack("1.2.0", manifest_override=lambda m: (
            m["dependencies"].append({
                "id": "other-pack", "version": "1.0.0", "sha256": "0" * 64,
            })
        ))
        with self.assertRaises(PackageUpgradeError) as dep:
            self.preview(path2, pack2)
        self.assertEqual(dep.exception.code, "dependency_migration_required")

    def test_existing_bad_version_directory_is_never_overwritten(self):
        path, pack = self.make_pack("1.1.0")
        existing = self.root / "assets/packs/forest-pack/1.1.0"
        existing.mkdir()
        (existing / "unexpected.txt").write_bytes(b"keep")
        with self.assertRaises(PackageUpgradeError) as error:
            self.preview(path, pack)
        self.assertEqual(error.exception.code, "destination_exists")
        self.assertEqual((existing / "unexpected.txt").read_bytes(), b"keep")
        self.assertEqual(self.editor.revision, 1)

    def test_rollback_on_editor_apply_failure_keeps_old_data(self):
        path, pack = self.make_pack("1.1.0")
        planned = self.preview(path, pack)
        before = deepcopy(self.editor.snapshot().to_dict())
        with patch.object(self.editor, "apply", side_effect=RuntimeError("apply failed")):
            with self.assertRaisesRegex(RuntimeError, "apply failed"):
                apply_package_upgrade(planned, self.editor, self.root)
        self.assertEqual(self.editor.snapshot().to_dict(), before)
        self.assertFalse((self.root / "assets/packs/forest-pack/1.1.0").exists())
        self.assertTrue((self.root / "assets/packs/forest-pack/1.0.0").is_dir())

    def test_stale_preview_and_tampered_installed_bytes_are_rejected(self):
        path, pack = self.make_pack("1.1.0")
        planned = self.preview(path, pack)
        self.editor.apply(self.editor.preview_project(
            lambda p: {**p, "subtitle": "After preview"}, kind="fixture"))
        with self.assertRaises(PackageUpgradeError) as stale:
            apply_package_upgrade(planned, self.editor, self.root)
        self.assertEqual(stale.exception.code, "stale_preview")
        self.assertFalse((self.root / "assets/packs/forest-pack/1.1.0").exists())

    def test_external_old_file_reference_requires_explicit_migration(self):
        old_file = "assets/packs/forest-pack/1.0.0/terrain/forest.png"
        self.editor.apply(self.editor.preview_project(
            lambda project: {**project, "subtitle": old_file},
            kind="fixture-external-physical-path"))
        path, pack = self.make_pack("1.1.0")
        with self.assertRaises(PackageUpgradeError) as refused:
            self.preview(path, pack)
        self.assertEqual(refused.exception.code, "migration_required")
        self.assertFalse((self.root / "assets/packs/forest-pack/1.1.0").exists())

    def test_modified_archive_after_preview_is_rejected(self):
        path, pack = self.make_pack("1.1.0")
        planned = self.preview(path, pack)
        path.write_bytes(path.read_bytes() + b"tampered")
        with self.assertRaises(PackageUpgradeError) as error:
            apply_package_upgrade(planned, self.editor, self.root)
        self.assertEqual(error.exception.code, "stale_preview")
        self.assertEqual(self.editor.snapshot().to_dict()["project"],
                         self.old_snapshot["project"])
        self.assertFalse((self.root / "assets/packs/forest-pack/1.1.0").exists())

    def test_other_proven_independent_package_allows_leaf_upgrade(self):
        source = make_source(self.root / "source-second", make_manifest("second-pack"))
        second = publish_pack(source, self.root / "second.rpack")
        install_pack(second, self.editor, self.root)
        path, pack = self.make_pack("1.1.0")
        plan = self.preview(path, pack)
        apply_package_upgrade(plan, self.editor, self.root)
        self.assertEqual(self.version(), "1.1.0")
        self.assertEqual(self.editor.revision, 3)
        self.assertEqual(verify_installed_packs(
            self.root, self.editor.snapshot().to_dict()["project"]), [])



if __name__ == "__main__":
    unittest.main()

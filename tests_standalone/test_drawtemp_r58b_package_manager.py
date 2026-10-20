"""R58.B1: reversible package lifecycle previews and usage diagnostics."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.assets.packs import install_pack, publish_pack
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.package_manager import (
    PackageManagerError, installed_package_usage,
    preview_package_removal, apply_package_removal,
)
from tests_standalone.test_drawtemp5_r24c import make_manifest, make_source


class PackageManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.editor = AuthoringSession.new(*reference_project())

    def install(self, name="forest-pack"):
        src = make_source(self.root / ("source-" + name), make_manifest(name))
        preview = publish_pack(src, self.root / (name + ".rpack"))
        install_pack(preview, self.editor, self.root)
        return preview

    def reports(self):
        return installed_package_usage(self.editor, self.root)

    def assert_blocked(self, code, package="forest-pack"):
        before = deepcopy(self.editor.snapshot().to_dict())
        with self.assertRaises(PackageManagerError) as caught:
            preview_package_removal(self.editor, self.root, package)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.editor.snapshot().to_dict(), before)

    def test_preview_then_apply_removal_reversible_and_non_destructive(self):
        preview_pack = self.install()
        before = deepcopy(self.editor.snapshot().to_dict())
        asset = self.root / "assets/packs/forest-pack/1.0.0/terrain/forest.png"
        digest = sha256(asset.read_bytes()).hexdigest()
        usage = self.reports()
        self.assertEqual(len(usage), 1)
        self.assertTrue(usage[0]["removable"])
        self.assertEqual(usage[0]["used_by"], [])
        change = preview_package_removal(
            self.editor, self.root, "forest-pack",
            expected_revision=self.editor.revision)
        info = change.to_dict()
        self.assertEqual(info["files_retained"], [
            "assets/packs/forest-pack/1.0.0/terrain/forest.png"
        ])
        self.assertFalse(info["filesystem_deleted"])
        self.assertTrue(info["reversible_via_editor_undo"])
        self.assertEqual(self.editor.snapshot().to_dict(), before)
        self.assertEqual(self.editor.revision, 1)
        apply_package_removal(change, self.editor, self.root)
        self.assertEqual(self.editor.revision, 2)
        self.assertEqual(self.reports(), ())
        project = self.editor.snapshot().to_dict()["project"]
        self.assertNotIn("org.drawtemp.resourcepacks", project.get("extensions", {}))
        self.assertEqual(sha256(asset.read_bytes()).hexdigest(), digest)
        self.editor.undo()
        self.assertEqual(self.reports()[0]["sha256"], preview_pack.sha256)
        self.assertEqual(self.editor.snapshot().to_dict()["project"], before["project"])
        self.editor.redo()
        self.assertEqual(self.reports(), ())
        self.assertEqual(sha256(asset.read_bytes()).hexdigest(), digest)

    def test_protects_external_bindings(self):
        self.install()
        self.editor.apply(self.editor.preview_project(
            lambda project: self._bind(project), kind="fixture-binding"))
        report = self.reports()[0]
        self.assertFalse(report["removable"])
        self.assertIn("binding:sprite/hero", report["used_by"])
        self.assert_blocked("package_in_use")

    @staticmethod
    def _bind(project):
        project["assets"]["bindings"] = {"sprite": {"hero": "forest-pack.tree"}}
        return project

    def test_protects_animation_and_project_string_references(self):
        self.install()
        def use_asset(project):
            project["assets"]["entries"].append({
                "id": "external-loop", "kind": "animation", "loop": True,
                "frames": [{"sprite": "forest-pack.tree", "duration_ms": 150}],
            })
            project["subtitle"] = "forest-pack.tree"
            return project
        self.editor.apply(self.editor.preview_project(use_asset, kind="fixture-use"))
        report = self.reports()[0]
        self.assertIn("animation:external-loop", report["used_by"])
        self.assertTrue(any(x.startswith("reference:project") for x in report["used_by"]))
        self.assert_blocked("package_in_use")

    def test_shared_asset_path_blocks_removal_without_dropping_provenance(self):
        self.install()
        def alias(project):
            project["assets"]["entries"].append({
                "id": "outside-pack-alias", "kind": "sprite",
                "path": "assets/packs/forest-pack/1.0.0/terrain/forest.png",
            })
            return project
        self.editor.apply(self.editor.preview_project(alias, kind="fixture-alias"))
        report = self.reports()[0]
        self.assertIn("shared-path:outside-pack-alias", report["used_by"])
        self.assert_blocked("package_in_use")

    def test_two_proven_independent_packages_can_remove_a_leaf(self):
        self.install("forest-pack")
        self.install("second-pack")
        reports = self.reports()
        self.assertEqual([row["id"] for row in reports],
                         ["forest-pack", "second-pack"])
        self.assertTrue(all(row["reverse_dependencies_verified"] for row in reports))
        self.assertTrue(all(row["removable"] for row in reports))
        plan = preview_package_removal(self.editor, self.root, "forest-pack")
        apply_package_removal(plan, self.editor, self.root)
        self.assertEqual([row["id"] for row in self.reports()], ["second-pack"])
        self.editor.undo()
        self.assertEqual(len(self.reports()), 2)

    def test_mixed_legacy_receipts_refuse_unproven_multi_pack_removal(self):
        self.install("forest-pack")
        def strip_provenance(project):
            project["extensions"]["org.drawtemp.resourcepacks"]["data"]["packs"][0].pop(
                "dependencies")
            return project
        self.editor.apply(self.editor.preview_project(
            strip_provenance, kind="legacy-fixture"))
        self.install("second-pack")
        reports = self.reports()
        self.assertFalse(any(row["reverse_dependencies_verified"] for row in reports))
        self.assertTrue(all(
            "other-installed-pack-dependencies-unrecorded" in row["used_by"]
            for row in reports))
        self.assert_blocked("package_in_use")

    def test_fails_closed_for_corruption_and_stale_previews(self):
        self.install()
        change = preview_package_removal(self.editor, self.root, "forest-pack")
        asset = self.root / "assets/packs/forest-pack/1.0.0/terrain/forest.png"
        asset.write_bytes(asset.read_bytes() + b"invalid")
        with self.assertRaises(PackageManagerError) as problem:
            apply_package_removal(change, self.editor, self.root)
        self.assertEqual(problem.exception.code, "invalid_receipts")
        self.assertEqual(self.editor.revision, 1)

    def test_stale_editor_revision_and_invalid_id(self):
        self.install()
        with self.assertRaises(PackageManagerError) as invalid:
            preview_package_removal(self.editor, self.root, "bad-id",
                                    expected_revision=0)
        self.assertEqual(invalid.exception.code, "stale_revision")
        self.assert_blocked("unknown_package", package="bad-id")
        change = preview_package_removal(self.editor, self.root, "forest-pack")
        self.editor.apply(self.editor.preview_project(
            lambda project: {**project, "subtitle": "Edited"},
            kind="fixture-edit"))
        with self.assertRaises(PackageManagerError) as stale:
            apply_package_removal(change, self.editor, self.root)
        self.assertEqual(stale.exception.code, "stale_preview")
        self.assertEqual(self.editor.revision, 2)


if __name__ == "__main__":
    unittest.main()

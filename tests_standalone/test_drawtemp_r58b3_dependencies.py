"""R58.B3: canonical dependency provenance, exact reverse pins and safe leaves."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.assets.packs import (
    RECEIPT_NAMESPACE, install_pack, publish_pack,
    verify_installed_packs, verify_receipt_dependency_graph,
)
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.package_manager import (
    PackageManagerError, apply_package_removal, installed_package_usage,
    preview_package_removal,
)
from drawtemp.studio.package_upgrades import (
    PackageUpgradeError, apply_package_upgrade, preview_package_upgrade,
)
from tests_standalone.test_drawtemp5_r24c import make_manifest, make_source


class VerifiedPackageDependencies(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.editor = AuthoringSession.new(*reference_project())
        self.serial = 0

    def make(self, pack_id, version="1.0.0", dependencies=()):
        self.serial += 1
        manifest = make_manifest(pack_id, deps=list(dependencies))
        manifest["version"] = version
        source = make_source(self.root / ("source-" + str(self.serial)), manifest)
        archive = self.root / ("archive-" + str(self.serial) + ".rpack")
        return archive, publish_pack(source, archive)

    def install(self, pack_id, version="1.0.0", dependencies=()):
        archive, pack = self.make(pack_id, version, dependencies)
        install_pack(pack, self.editor, self.root)
        return archive, pack

    def project(self):
        return self.editor.snapshot().to_dict()["project"]

    def receipts(self):
        return self.project()["extensions"][RECEIPT_NAMESPACE]["data"]["packs"]

    def pin(self, pack_id, pack, version="1.0.0"):
        return {"id": pack_id, "version": version, "sha256": pack.sha256}

    def upgrade(self, archive, pack, *, downgrade=False):
        return preview_package_upgrade(
            self.editor, self.root, archive,
            expected_sha256=pack.sha256, allow_downgrade=downgrade)

    def test_new_receipts_persist_direct_dependencies_without_new_envelope(self):
        _, library = self.install("lib-pack")
        _, consumer = self.install(
            "ui-pack", dependencies=[self.pin("lib-pack", library)])
        rows = self.receipts()
        self.assertEqual(rows[0]["dependencies"], [])
        self.assertEqual(rows[1]["dependencies"], [self.pin("lib-pack", library)])
        self.assertTrue(verify_receipt_dependency_graph(rows))
        self.assertEqual(verify_installed_packs(self.root, self.project()), [])

    def test_reverse_pin_blocks_library_but_leaf_is_removable_and_undoable(self):
        _, library = self.install("lib-pack")
        self.install("ui-pack", dependencies=[self.pin("lib-pack", library)])
        reports = {report["id"]: report for report in
                   installed_package_usage(self.editor, self.root)}
        self.assertIn("required-by:ui-pack", reports["lib-pack"]["used_by"])
        self.assertFalse(reports["lib-pack"]["removable"])
        self.assertFalse(reports["lib-pack"]["upgradable"])
        self.assertTrue(reports["ui-pack"]["removable"])
        self.assertTrue(reports["ui-pack"]["upgradable"])
        with self.assertRaises(PackageManagerError) as error:
            preview_package_removal(self.editor, self.root, "lib-pack")
        self.assertEqual(error.exception.code, "package_in_use")
        plan = preview_package_removal(self.editor, self.root, "ui-pack")
        apply_package_removal(plan, self.editor, self.root)
        self.assertEqual([r["id"] for r in self.receipts()], ["lib-pack"])
        self.assertEqual(verify_installed_packs(self.root, self.project()), [])
        self.editor.undo()
        self.assertEqual([r["id"] for r in self.receipts()], ["lib-pack", "ui-pack"])

    def test_dependent_upgrade_preserves_existing_forward_pins(self):
        _, library = self.install("lib-pack")
        dependencies = [self.pin("lib-pack", library)]
        self.install("ui-pack", dependencies=dependencies)
        archive, candidate = self.make("ui-pack", "1.1.0", dependencies)
        plan = self.upgrade(archive, candidate)
        self.assertEqual(plan.version, "1.1.0")
        apply_package_upgrade(plan, self.editor, self.root)
        self.assertEqual(
            next(r for r in self.receipts() if r["id"] == "ui-pack")["dependencies"],
            dependencies)
        self.assertEqual(verify_installed_packs(self.root, self.project()), [])
        self.editor.undo()
        self.assertEqual(
            next(r for r in self.receipts() if r["id"] == "ui-pack")["version"],
            "1.0.0")

    def test_upgrading_pinned_library_refused_before_disk_mutation(self):
        _, library = self.install("lib-pack")
        self.install("ui-pack", dependencies=[self.pin("lib-pack", library)])
        archive, candidate = self.make("lib-pack", "1.1.0")
        with self.assertRaises(PackageUpgradeError) as refusal:
            self.upgrade(archive, candidate)
        self.assertEqual(refusal.exception.code, "dependency_in_use")
        self.assertFalse((self.root / "assets/packs/lib-pack/1.1.0").exists())

    def test_changing_forward_dependencies_needs_explicit_migration(self):
        _, library = self.install("lib-pack")
        self.install("ui-pack", dependencies=[self.pin("lib-pack", library)])
        archive, candidate = self.make("ui-pack", "1.1.0")
        with self.assertRaises(PackageUpgradeError) as refusal:
            self.upgrade(archive, candidate)
        self.assertEqual(refusal.exception.code, "dependency_migration_required")
        self.assertEqual(verify_installed_packs(self.root, self.project()), [])

    def test_invalid_missing_dependency_conflict_and_cycle_fail_export_integrity(self):
        _, library = self.install("lib-pack")
        self.install("ui-pack", dependencies=[self.pin("lib-pack", library)])
        source = self.project()
        receipts = source["extensions"][RECEIPT_NAMESPACE]["data"]["packs"]
        receipts[1]["dependencies"][0]["sha256"] = "0" * 64
        self.assertTrue(any("dependency" in msg.lower()
                            for msg in verify_installed_packs(self.root, source)))
        cycle = self.project()
        rows = cycle["extensions"][RECEIPT_NAMESPACE]["data"]["packs"]
        rows[0]["dependencies"] = [{
            "id": "ui-pack", "version": "1.0.0", "sha256": rows[1]["sha256"]
        }]
        self.assertTrue(any("cycle" in msg.lower()
                            for msg in verify_installed_packs(self.root, cycle)))
        no_dep = self.project()
        rows = no_dep["extensions"][RECEIPT_NAMESPACE]["data"]["packs"]
        rows[:] = [rows[1]]
        self.assertTrue(any("dependency" in msg.lower()
                            for msg in verify_installed_packs(self.root, no_dep)))

    def test_unknown_legacy_receipt_cannot_prove_multi_pack_graph(self):
        self.install("lib-pack")
        self.install("ui-pack")
        document = self.project()
        rows = document["extensions"][RECEIPT_NAMESPACE]["data"]["packs"]
        rows[0].pop("dependencies")
        self.assertFalse(verify_receipt_dependency_graph(rows))
        self.assertEqual(verify_installed_packs(self.root, document), [])
        self.editor.apply(self.editor.preview_project(
            lambda _: deepcopy(document), kind="fixture-legacy"))
        reports = installed_package_usage(self.editor, self.root)
        self.assertTrue(all(not item["removable"] for item in reports))
        archive, candidate = self.make("ui-pack", "1.1.0")
        with self.assertRaises(PackageUpgradeError) as refusal:
            self.upgrade(archive, candidate)
        self.assertEqual(refusal.exception.code, "dependency_unknown")

    def test_reject_corrupt_dependency_payload(self):
        self.install("lib-pack")
        project = self.project()
        row = project["extensions"][RECEIPT_NAMESPACE]["data"]["packs"][0]
        for value in (None, {}, [{"id": "foo", "version": "bogus", "sha256": "x" * 64}]):
            with self.subTest(value=value):
                broken = deepcopy(project)
                broken["extensions"][RECEIPT_NAMESPACE]["data"]["packs"][0][
                    "dependencies"] = value
                self.assertTrue(verify_installed_packs(self.root, broken))


if __name__ == "__main__":
    unittest.main()

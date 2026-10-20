"""R58.A: integration of pinned package planning with R24.C archives."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile
import unittest

from drawtemp.assets.packs import PackPreview, install_pack, publish_pack
from drawtemp.assets.package_ecosystem import PackagePlanError, plan_package_install
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.simulation import freeze
from tests_standalone.test_drawtemp5_r24c import make_manifest, make_source


class PackageEcosystemTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.editor = AuthoringSession.new(*reference_project())

    @property
    def project(self):
        return self.editor.snapshot().to_dict()["project"]

    def pack(self, name, deps=None, version="1.0.0"):
        manifest = make_manifest(name, deps)
        manifest["version"] = version
        source = make_source(self.root / ("source-" + name), manifest)
        path = self.root / (name + ".rpack")
        return path, publish_pack(source, path)

    def plan(self, archives, pins, *, root=None, project=None):
        return plan_package_install(
            archives, project_root=self.root if root is None else root,
            project=self.project if project is None else project,
            expected_sha256=pins,
        )

    def rejects(self, code, archives, pins):
        with self.assertRaises(PackagePlanError) as ctx:
            self.plan(archives, pins)
        self.assertEqual(ctx.exception.code, code)

    def test_topological_order_is_deterministic_and_reusable_across_projects(self):
        library, lib = self.pack("z-library")
        quest, q = self.pack("a-quest", [
            {"id": "z-library", "version": "1.0.0", "sha256": lib.sha256}
        ])
        pins = {"z-library": lib.sha256, "a-quest": q.sha256}
        original = deepcopy(self.project)
        first = self.plan([quest, library], pins)
        second = self.plan([library, quest], pins)
        self.assertEqual([p.pack_id for p in first.packages],
                         ["z-library", "a-quest"])
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(self.project, original)
        self.assertEqual(self.editor.revision, 0)
        self.assertFalse((self.root / "assets").exists())

        other_root = self.root / "different-game"
        other_root.mkdir()
        another_project = AuthoringSession.new(*reference_project()).snapshot().to_dict()["project"]
        in_other_game = self.plan([library, quest], pins,
                                  root=other_root, project=another_project)
        self.assertEqual(in_other_game.fingerprint, first.fingerprint)
        self.assertFalse(in_other_game.to_dict()["export_approved"])
        self.assertFalse(in_other_game.to_dict()["signature_verified"])
        self.assertFalse(in_other_game.to_dict()["rights_verified"])
        self.assertEqual(in_other_game.to_dict()["permissions_granted"], [])

    def test_missing_conflicting_and_duplicate_dependencies_fail_closed(self):
        library, lib = self.pack("z-library")
        quest, q = self.pack("a-quest", [
            {"id": "z-library", "version": "1.0.0", "sha256": lib.sha256}
        ])
        self.rejects("missing_dependency", [quest], {"a-quest": q.sha256})
        self.rejects("duplicate_package", [library, library],
                     {"z-library": lib.sha256, "unused": "0" * 64})
        self.rejects("missing_pin", [library], {})
        self.rejects("invalid_pin", [library], {"z-library": "wrong"})
        self.rejects("digest_mismatch", [library], {"z-library": "0" * 64})
        self.rejects("missing_pin", [library], {"another-pack": lib.sha256})
        self.rejects("invalid_input", [], {})

        install_pack(lib, self.editor, self.root)
        self.rejects("already_installed", [library], {"z-library": lib.sha256})
        # Installed dependency can satisfy the exact pin without being reinstalled.
        planned = self.plan([quest], {"a-quest": q.sha256})
        self.assertEqual([p.pack_id for p in planned.packages], ["a-quest"])
        self.assertEqual(self.editor.revision, 1)

        bad_deps = [{"id": "z-library", "version": "9.0.0", "sha256": lib.sha256}]
        bad_path, bad = self.pack("b-quest", bad_deps)
        self.rejects("dependency_conflict", [bad_path], {"b-quest": bad.sha256})

    def test_damaged_install_receipt_blocks_future_plans(self):
        library, lib = self.pack("z-library")
        install_pack(lib, self.editor, self.root)
        asset = (self.root / "assets/packs/z-library/1.0.0/terrain/forest.png")
        asset.write_bytes(asset.read_bytes() + b"tamper")
        quest, q = self.pack("a-quest")
        self.rejects("invalid_receipts", [quest], {"a-quest": q.sha256})

    def test_symlinks_traversal_and_extra_payload_are_refused(self):
        source, valid = self.pack("z-library")
        linked = self.root / "linked.rpack"
        try:
            linked.symlink_to(source)
        except (OSError, NotImplementedError):
            pass
        else:
            self.rejects("unsafe_archive", [linked], {"z-library": valid.sha256})

        with ZipFile(source, "a") as archive:
            archive.writestr("files/../outside.png", b"untrusted")
        self.rejects("invalid_archive", [source], {"z-library": valid.sha256})
        self.assertFalse((self.root / "outside.png").exists())
        self.assertFalse((self.root / "assets").exists())

    def test_dependency_cycle_is_detected_even_for_untrusted_catalog_data(self):
        # Circular content-addressed archives cannot be built normally; mocked
        # inspections isolate the graph validation from ZIP integrity checks.
        a, b = self.root / "a.rpack", self.root / "b.rpack"
        a.write_bytes(b"stub")
        b.write_bytes(b"stub")
        manifest_a, manifest_b = make_manifest("pack-a"), make_manifest("pack-b")
        manifest_a["dependencies"] = [{
            "id": "pack-b", "version": "1.0.0", "sha256": "b" * 64
        }]
        manifest_b["dependencies"] = [{
            "id": "pack-a", "version": "1.0.0", "sha256": "a" * 64
        }]
        previews = [
            PackPreview(a, "a" * 64, freeze(manifest_a)),
            PackPreview(b, "b" * 64, freeze(manifest_b)),
        ]
        with patch("drawtemp.assets.package_ecosystem.inspect_pack",
                   side_effect=previews):
            self.rejects("dependency_cycle", [a, b],
                         {"pack-a": "a" * 64, "pack-b": "b" * 64})

    def test_no_implicit_rights_or_executable_payloads(self):
        archive, preview = self.pack("z-library")
        record = self.plan([archive], {"z-library": preview.sha256}).to_dict()
        self.assertEqual(record["packages"][0]["authenticity"], "not-verified")
        self.assertFalse(record["packages"][0]["rights_verified"])
        self.assertFalse(record["packages"][0]["executable"])
        self.assertEqual(record["packages"][0]["license_assertions"][0]["license_id"],
                         "Fixture-Only")
        self.assertEqual(record["kind"], "drawtemp-r58-install-plan")


if __name__ == "__main__":
    unittest.main()

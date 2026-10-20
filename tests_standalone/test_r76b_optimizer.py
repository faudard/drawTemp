"""R76.B1 lossless derived asset optimization and transactional undo tests."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.optimizer import (
    OptimizerError, plan_optimization, publish_derived_assets, undo_derived_assets,
)
from sporebound.assets import AssetRegistry
from tests_standalone.test_r76_asset_audit import png


def make_registry(*, with_duplicates=True):
    entries = [
        {"id": "sprite_a", "kind": "sprite", "path": "a.png", "region": [0, 0, 1, 1]},
        {"id": "sprite_b", "kind": "sprite",
         "path": "b.png" if with_duplicates else "a.png",
         "region": [1, 0, 1, 1]},
        {"id": "idle", "kind": "animation", "loop": True,
         "frames": [{"sprite": "sprite_a", "duration_ms": 100},
                    {"sprite": "sprite_b", "duration_ms": 100}]},
    ]
    return AssetRegistry({"version": 1, "entries": entries,
                          "bindings": {"animation": {"idle": "idle"}}})


class OptimizerB1Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.workspace = Path(temp.name)
        self.root = self.workspace / "source"
        self.root.mkdir()
        self.destination = self.workspace / "optimized-preview"
        (self.root / "a.png").write_bytes(png(2, 3))
        (self.root / "b.png").write_bytes(png(2, 3))
        self.registry = make_registry()

    def test_plan_is_deterministic_and_does_not_modify_original_registry(self):
        baseline = self.registry.to_dict()
        plan = plan_optimization(self.registry, self.root)
        self.assertEqual(plan, plan_optimization(self.registry, self.root))
        self.assertEqual(baseline, self.registry.to_dict())
        self.assertEqual(plan["cost"]["candidate_count"], 1)
        self.assertEqual(plan["proposals"][0]["source_path"], "b.png")
        self.assertEqual(plan["proposals"][0]["canonical_path"], "a.png")
        self.assertEqual(plan["cost"]["bytes_saved"], len(png(2, 3)))
        self.assertEqual(plan["cost"]["derived_bytes"], len(png(2, 3)))
        self.assertEqual(plan["rights"], "not_assessed")
        self.assertFalse(plan["image_golden_approved"])
        self.assertFalse(plan["release_certified"])
        projected = AssetRegistry(plan["projected_registry"])
        self.assertEqual(projected.require_reference("sprite_b")["path"], "a.png")
        self.assertEqual(projected.require_reference("idle")["frames"],
                         baseline["entries"][2]["frames"])

    def test_publication_is_explicit_atomic_and_undo_preserves_every_source(self):
        source = {p.name: p.read_bytes() for p in self.root.iterdir()}
        plan = plan_optimization(self.registry, self.root)
        with self.assertRaises(OptimizerError):
            publish_derived_assets(self.registry, self.root, plan,
                                   self.destination, approved=False)
        self.assertFalse(self.destination.exists())
        receipt = publish_derived_assets(self.registry, self.root, plan,
                                         self.destination, approved=True)
        self.assertEqual(receipt["cost"]["bytes_saved"], len(source["b.png"]))
        self.assertFalse(receipt["release_certified"])
        self.assertEqual(sorted(p.relative_to(self.destination).as_posix()
                                for p in self.destination.rglob("*") if p.is_file()),
                         ["assets/a.png", "receipt.json", "registry.json"])
        deriv = AssetRegistry(json.loads(
            (self.destination / "registry.json").read_text(encoding="utf-8")))
        self.assertEqual(deriv.diagnostics(self.destination / "assets"), [])
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, source)
        self.assertTrue(undo_derived_assets(
            self.destination, expected_receipt_sha256=receipt["receipt_sha256"]))
        self.assertFalse(self.destination.exists())
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, source)

    def test_refuse_destination_inside_project_or_existing(self):
        plan = plan_optimization(self.registry, self.root)
        with self.assertRaises(OptimizerError):
            publish_derived_assets(self.registry, self.root, plan,
                                   self.root / "preview", approved=True)
        self.destination.mkdir()
        (self.destination / "user-file.txt").write_text("DO NOT TOUCH")
        with self.assertRaises(OptimizerError):
            publish_derived_assets(self.registry, self.root, plan,
                                   self.destination, approved=True)
        self.assertEqual((self.destination / "user-file.txt").read_text(), "DO NOT TOUCH")

    def test_symlinked_destination_denied(self):
        plan = plan_optimization(self.registry, self.root)
        try:
            self.destination.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink not available")
        with self.assertRaises(OptimizerError):
            publish_derived_assets(self.registry, self.root, plan,
                                   self.destination, approved=True)
        self.assertTrue(self.destination.is_symlink())
        self.assertTrue((self.root / "a.png").exists())

    def test_stale_source_bytes_and_registry_cancel_before_publication(self):
        plan = plan_optimization(self.registry, self.root)
        self.root.joinpath("b.png").write_bytes(png(3, 3))
        with self.assertRaises(OptimizerError):
            publish_derived_assets(self.registry, self.root, plan,
                                   self.destination, approved=True)
        self.assertFalse(self.destination.exists())
        self.root.joinpath("b.png").write_bytes(png(2, 3))
        changed = deepcopy(self.registry.to_dict())
        changed["bindings"] = {}
        with self.assertRaises(OptimizerError):
            publish_derived_assets(AssetRegistry(changed), self.root, plan,
                                   self.destination, approved=True)
        self.assertFalse(self.destination.exists())

    def test_tampering_blocks_undo_and_unexpected_files_are_not_deleted(self):
        plan = plan_optimization(self.registry, self.root)
        receipt = publish_derived_assets(self.registry, self.root, plan,
                                         self.destination, approved=True)
        rogue = self.destination / "unrelated.txt"
        rogue.write_text("preserve me")
        with self.assertRaises(OptimizerError):
            undo_derived_assets(
                self.destination, expected_receipt_sha256=receipt["receipt_sha256"])
        self.assertEqual(rogue.read_text(), "preserve me")
        rogue.unlink()
        (self.destination / "assets" / "a.png").write_bytes(b"tampered")
        with self.assertRaises(OptimizerError):
            undo_derived_assets(
                self.destination, expected_receipt_sha256=receipt["receipt_sha256"])
        self.assertTrue(self.destination.exists())

    def test_receipt_capability_and_source_is_not_promoted_to_release(self):
        plan = plan_optimization(self.registry, self.root)
        receipt = publish_derived_assets(self.registry, self.root, plan,
                                         self.destination, approved=True)
        data = json.loads((self.destination / "receipt.json").read_text())
        self.assertFalse(data["release_certified"])
        self.assertEqual(data["rights"], "not_attested_for_derived_package")
        self.assertEqual(data["gameplay_parity"], "not_assessed")
        self.assertEqual(data["cost"]["bytes_saved"], len(png(2, 3)))
        with self.assertRaises(OptimizerError):
            undo_derived_assets(self.destination, expected_receipt_sha256="0" * 64)
        self.assertTrue(self.destination.is_dir())
        self.assertTrue(undo_derived_assets(
            self.destination, expected_receipt_sha256=receipt["receipt_sha256"]))

    def test_no_duplicate_means_no_optimization_or_output(self):
        registry = make_registry(with_duplicates=False)
        plan = plan_optimization(registry, self.root)
        self.assertEqual(plan["proposals"], [])
        with self.assertRaises(OptimizerError):
            publish_derived_assets(registry, self.root, plan,
                                   self.destination, approved=True)
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()

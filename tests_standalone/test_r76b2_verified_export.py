"""R76.B2: strict R15 optimized project and decoded PNG parity regression tests.

Rights records and native executables in these tests are synthetic fixtures.
They are NOT real licenses or production clean-machine proof.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from drawtemp.assets.optimizer import OptimizerError, _digest
from drawtemp.export.r15 import preflight, verify_bundle, project_path
from drawtemp.export.r76b2 import (
    inspect_preview, prepare_preview, export_native_preview, undo_preview, main,
)
from drawtemp.export.templates import create_template
from sporebound.assets import AssetRegistry

try:
    import PIL
except ImportError:
    PIL = None


@unittest.skipIf(PIL is None, "Pillow needed for decoded image comparison")
class R76B2StrictExportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = create_template("jeanne", self.root / "authored")
        self.content = self.source / "game.json"
        project_file = project_path(self.content)
        project = json.loads(project_file.read_text(encoding="utf-8"))
        registry = AssetRegistry(project["assets"]).to_dict()
        reference = next(e for e in registry["entries"] if e["kind"] == "sprite")
        original = self.source / reference["path"]
        self.alias = "art/r76b2-byte-copy.png"
        (self.source / "art").mkdir(exist_ok=True)
        shutil.copyfile(original, self.source / self.alias)
        duplicate = deepcopy(reference)
        duplicate["id"] = "r76b2_fixture_dup"
        duplicate["path"] = self.alias
        registry["entries"].append(duplicate)
        project["assets"] = registry
        project_file.write_text(json.dumps(project, indent=2), encoding="utf-8")
        evidence = self.source / "licenses" / "test-only.txt"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("Fixture only; no genuine license conveyed.\n", encoding="utf-8")
        assets = preflight(self.content)["assets"]
        rights = {
            rel: {
                "status": "approved",
                "rights_holder": "Synthetic fixture only",
                "license_id": "TEST-ONLY",
                "evidence_path": "licenses/test-only.txt",
                "sha256": sha256((self.source / rel).read_bytes()).hexdigest(),
                "allow_modification": True,
                "allow_redistribution": True,
            } for rel in assets
        }
        (self.source / "asset-licenses.json").write_text(
            json.dumps({"schema": 1, "assets": rights}, indent=2),
            encoding="utf-8")
        self.assertTrue(preflight(self.content, require_licenses=True)["passed"])
        self.destination = self.root / "staged-r76"
        self.plan = inspect_preview(self.content)

    def test_preview_has_real_decoded_pixel_proof_and_approval_is_not_forged(self):
        rows = [e for e in self.plan["visual_evidence"] if e["before"] == self.alias]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "png_rgba")
        self.assertEqual(len(rows[0]["rgba_sha256"]), 64)
        self.assertTrue(rows[0]["identical"])
        self.assertFalse(self.plan["manual_golden_approval"])
        self.assertFalse(self.plan["release_certified"])
        self.assertEqual(self.plan, inspect_preview(self.content))
        self.assertEqual(self.plan["optimizer_plan"]["cost"]["candidate_count"], 1)

    def test_staged_project_r15_roundtrip_preview_bundle_and_safe_undo(self):
        original_files = {
            x.relative_to(self.source).as_posix(): sha256(x.read_bytes()).hexdigest()
            for x in self.source.rglob("*") if x.is_file()
        }
        with self.assertRaises(OptimizerError):
            prepare_preview(self.content, self.plan, self.destination, approved=False)
        result = prepare_preview(self.content, self.plan, self.destination, approved=True)
        self.assertFalse((self.destination / self.alias).exists())
        self.assertTrue(self.content.is_file())
        self.assertTrue(preflight(self.destination / "game.json",
                                  require_licenses=True)["passed"])
        self.assertEqual(result["rights_checked"], True)
        self.assertFalse(result["release_certified"])
        derived_project = json.loads(
            project_path(self.destination / "game.json").read_text())
        manifest = AssetRegistry(derived_project["assets"])
        self.assertNotIn(self.alias, {
            e["path"] for e in manifest.to_dict()["entries"] if e["kind"] != "animation"
        })
        derived_rights = json.loads(
            (self.destination / "asset-licenses.json").read_text())
        self.assertNotIn(self.alias, derived_rights["assets"])
        runtime = self.root / "runtime"
        runtime.mkdir()
        binary = "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"
        (runtime / binary).write_bytes(b"synthetic native Player placeholder")
        bundle = self.root / "bundle"
        exported = export_native_preview(
            self.destination, result["receipt_sha256"], runtime, bundle)
        self.assertFalse(exported["release_certified"])
        self.assertFalse(verify_bundle(bundle)["release_candidate"])
        self.assertTrue(undo_preview(
            self.destination, expected_receipt_sha256=result["receipt_sha256"]))
        self.assertFalse(self.destination.exists())
        self.assertEqual(original_files, {
            x.relative_to(self.source).as_posix(): sha256(x.read_bytes()).hexdigest()
            for x in self.source.rglob("*") if x.is_file()
        })

    def test_rights_mismatch_of_same_png_blocks_plan(self):
        rights_file = self.source / "asset-licenses.json"
        rights = json.loads(rights_file.read_text())
        rights["assets"][self.alias]["license_id"] = "ALTERNATE-TEST"
        rights_file.write_text(json.dumps(rights), encoding="utf-8")
        # Original strict gate can still pass independent rights with same bytes,
        # but R76 cannot silently merge their provenance.
        self.assertTrue(preflight(self.content, require_licenses=True)["passed"])
        with self.assertRaisesRegex(OptimizerError, "Incompatible rights"):
            inspect_preview(self.content)
        self.assertFalse(self.destination.exists())

    def test_stale_plan_and_changed_evidence_refuse_publication(self):
        proof = self.source / "licenses" / "test-only.txt"
        proof.write_text("changed fixture proof", encoding="utf-8")
        with self.assertRaisesRegex(OptimizerError, "Stale"):
            prepare_preview(self.content, self.plan, self.destination, approved=True)
        self.assertFalse(self.destination.exists())

    def test_undo_rejects_unknown_files_and_tampered_content(self):
        result = prepare_preview(self.content, self.plan, self.destination, approved=True)
        unknown = self.destination / "user-created.txt"
        unknown.write_text("never remove this")
        with self.assertRaises(OptimizerError):
            undo_preview(self.destination, expected_receipt_sha256=result["receipt_sha256"])
        self.assertTrue(unknown.exists())
        unknown.unlink()
        (self.destination / "game.json").write_text("tampered")
        with self.assertRaises(OptimizerError):
            undo_preview(self.destination, expected_receipt_sha256=result["receipt_sha256"])
        self.assertTrue(self.destination.exists())

    def test_stage_refuses_existing_directory_and_project_local_destination(self):
        self.destination.mkdir()
        (self.destination / "keep").write_text("preserve")
        with self.assertRaises(OptimizerError):
            prepare_preview(self.content, self.plan, self.destination, approved=True)
        self.assertEqual((self.destination / "keep").read_text(), "preserve")
        with self.assertRaises(OptimizerError):
            prepare_preview(self.content, self.plan,
                            self.source / "project-stage", approved=True)
        self.assertFalse((self.source / "project-stage").exists())

    def test_undecodable_png_or_symlink_input_fails_closed(self):
        target = self.source / self.alias
        target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        with self.assertRaises(OptimizerError):
            inspect_preview(self.content)
        target.unlink()
        try:
            target.symlink_to(next(p for p in self.source.rglob("*.png")
                                   if p.name != target.name))
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable")
        with self.assertRaises(OptimizerError):
            inspect_preview(self.content)

    def test_cli_plan_and_reject_unapproved_stage(self):
        self.assertEqual(main(["plan", "--content", str(self.content)]), 0)
        self.assertEqual(main([
            "stage", "--content", str(self.content),
            "--output", str(self.destination),
            "--expected-plan-sha256", _digest(self.plan)]), 1)
        self.assertFalse(self.destination.exists())

    def test_stage_failure_rolls_back_atomic_directory(self):
        from drawtemp.export import r76b2
        gate = r76b2.preflight
        def reject_stage(path, *, require_licenses=False):
            result = gate(path, require_licenses=require_licenses)
            if Path(path).resolve().parent != self.source:
                result["passed"] = False
                result["errors"] = ["induced staged failure"]
            return result
        with patch.object(r76b2, "preflight", side_effect=reject_stage):
            with self.assertRaisesRegex(OptimizerError, "staged R15"):
                prepare_preview(self.content, self.plan, self.destination, approved=True)
        self.assertFalse(self.destination.exists())
        self.assertFalse(any(self.root.glob(".r76b2-stage-*")))


if __name__ == "__main__":
    unittest.main()

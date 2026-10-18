"""R15 Creator: content preflight, fail-closed packaging and tampering."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.r15 import (
    ExportError, export_game, preflight, project_path, verify_bundle,
)


class R15ExportTests(unittest.TestCase):
    def setUp(self):
        from importlib.resources import files
        self.content = Path(str(files("sporebound").joinpath("content/jeanne.json")))
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        name = "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"
        (self.runtime / name).write_bytes(b"fake binary for integrity tests")
        (self.runtime / "support.dat").write_bytes(b"Qt runtime placeholder")

    def test_canonical_jeanne_preflight_and_project_pair(self):
        self.assertEqual(project_path(self.content).name, "jeanne.game.json")
        result = preflight(self.content)
        self.assertTrue(result["passed"], result["errors"])
        self.assertIn("p0_01_lame", result["missions"])

    def test_multiple_sprite_regions_share_one_verified_atlas_file(self):
        """R17.8: one PNG can back dozens of independently named frames."""
        from sporebound.assets import AssetRegistry
        document = json.loads(
            project_path(self.content).read_text(encoding="utf-8"))
        registry = AssetRegistry(document["assets"])
        atlas = "art/jeanne/jeanne_atlas.png"
        references = [entry for entry in registry.to_dict()["entries"]
                      if entry.get("path") == atlas]
        self.assertGreater(len(references), 2)
        self.assertTrue(all(entry["kind"] == "sprite" for entry in references))
        report = preflight(self.content)
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["assets"].count(atlas), 1)
        self.assertEqual(len(report["assets"]),
                         len({path.casefold() for path in report["assets"]}))
        target = self.root / "multiple-regions"
        export_game(self.content, self.runtime, target)
        manifest = verify_bundle(target)
        self.assertEqual(sum(
            entry["path"] == "game/" + atlas for entry in manifest["files"]), 1)
        self.assertTrue((target / "game" / atlas).is_file())

    def test_export_roundtrip_and_hash_integrity(self):
        target = self.root / "Jeanne"
        export_game(self.content, self.runtime, target)
        manifest = verify_bundle(target)
        self.assertEqual(manifest["kind"], "drawtemp5-standalone-game")
        self.assertEqual(manifest["content"], "game/jeanne.json")
        self.assertTrue((target / "game" / "jeanne.game.json").is_file())
        first = target / "game" / "jeanne.json"
        first.write_bytes(first.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ExportError, "integrity"):
            verify_bundle(target)

    def test_existing_target_and_missing_runtime_do_not_overwrite(self):
        target = self.root / "existing"
        target.mkdir()
        sentinel = target / "keep"
        sentinel.write_text("original")
        with self.assertRaises(ExportError):
            export_game(self.content, self.runtime, target)
        self.assertEqual(sentinel.read_text(), "original")
        (self.runtime / ("DrawTempPlayer.exe" if os.name == "nt"
                         else "DrawTempPlayer")).unlink()
        with self.assertRaisesRegex(ExportError, "executable"):
            export_game(self.content, self.runtime, self.root / "absent")
        self.assertFalse((self.root / "absent").exists())

    def test_missing_asset_and_modified_manifest_fail_closed(self):
        target = self.root / "bundle"
        export_game(self.content, self.runtime, target)
        manifest = target / "manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["files"][0]["path"] = "../escape"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ExportError):
            verify_bundle(target)

    def test_release_requires_verified_r14_gate(self):
        report = self.root / "r14.json"
        report.write_text(json.dumps({"schema": 1}), encoding="utf-8")
        with self.assertRaisesRegex(ExportError, "R14 release gate"):
            export_game(self.content, self.runtime, self.root / "release",
                        r14_report=report)
        self.assertFalse((self.root / "release").exists())

    def test_unlisted_files_rejected(self):
        target = self.root / "bundle"
        export_game(self.content, self.runtime, target)
        (target / "unlisted.txt").write_text("oops")
        with self.assertRaisesRegex(ExportError, "Unlisted"):
            verify_bundle(target)


if __name__ == "__main__":
    unittest.main()

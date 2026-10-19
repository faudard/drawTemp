"""R30.B safe pack import: no overwrite, no unapproved rights, canonical R1."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zlib

from drawtemp.export.creator_packs import build_pack
from drawtemp.export.pack_import import (
    PackImportError, preview_pack_import, import_pack_to_copy,
)
from drawtemp.export.r15 import preflight
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from sporebound.assets import AssetRegistry
from sporebound.studio_transaction import validate_pair


def _png():
    def chunk(name, payload):
        return (struct.pack(">I", len(payload)) + name + payload +
                struct.pack(">I", zlib.crc32(name + payload) & 0xffffffff))
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return (header + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(b"\x00\x88\x55\x33\xff")) +
            chunk(b"IEND", b""))


def _manifest(payload):
    return {
        "schema": 1, "id": "art-pack", "version": "1.0.0", "kind": "terrain",
        "requires": {"min_api": "1.0.0", "max_api": "2.0.0",
                     "features": ["authoring.v1"]},
        "files": [{
            "path": "terrain/grass.png", "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "origin": "Original automated-test pixels",
            "license": "CC0-1.0",
        }],
    }


class R30PackImportTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source_root = self.root / "source"
        self.source_root.mkdir()
        self.content, self.project = reference_project()
        AuthoringSession.new(self.content, self.project).save_as(
            self.source_root / "game.json")
        self.source = self.source_root / "game.json"
        self.pack_source = self.root / "pack-source"
        (self.pack_source / "terrain").mkdir(parents=True)
        self.payload = _png()
        (self.pack_source / "terrain" / "grass.png").write_bytes(self.payload)
        self.archive = build_pack(self.pack_source, self.root / "pack.zip",
                                  _manifest(self.payload))
        self.bindings = [{"path": "terrain/grass.png",
                          "kind": "sprite", "name": "grass"}]
        self.destination = self.root / "imported"

    def preview(self):
        return preview_pack_import(self.source, self.archive, self.bindings)

    def test_preview_is_read_only_and_reports_uncleared_rights(self):
        original = self.source.read_bytes()
        prior_project = (self.source_root / "game.game.json").read_bytes()
        preview = self.preview()
        self.assertEqual(preview.pack_id, "art-pack")
        self.assertEqual(preview.selections[0].asset_id, "art-pack.grass")
        self.assertFalse(preview.to_dict()["rights_verified"])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual((self.source_root / "game.game.json").read_bytes(), prior_project)
        self.assertFalse(self.destination.exists())

    def test_copy_import_is_canonical_and_does_not_modify_source(self):
        initial_bytes = (self.source.read_bytes(),
                         (self.source_root / "game.game.json").read_bytes())
        preview = self.preview()
        published = import_pack_to_copy(preview, self.destination)
        self.assertEqual(published, self.destination)
        self.assertEqual((self.source.read_bytes(),
                          (self.source_root / "game.game.json").read_bytes()),
                         initial_bytes)
        original_content, original_project = validate_pair(
            json.loads(initial_bytes[0]), json.loads(initial_bytes[1]))
        data, project = validate_pair(
            json.loads((published / "game.json").read_text(encoding="utf-8")),
            json.loads((published / "game.game.json").read_text(encoding="utf-8")))
        self.assertEqual(data, original_content)
        registry = AssetRegistry(project["assets"])
        self.assertEqual(registry.require_reference("art-pack.grass")["path"],
                         "packs/art-pack/1.0.0/terrain/grass.png")
        self.assertEqual(registry.diagnostics(published), [])
        self.assertNotEqual(project, original_project)
        self.assertEqual((published / "packs/art-pack/1.0.0/terrain/grass.png").read_bytes(),
                         self.payload)
        self.assertTrue(preflight(published / "game.json")["passed"])
        report = json.loads((published / "r30-pack-import-report.json").read_text())
        self.assertFalse(report["rights_verified"])
        self.assertFalse(report["release_certified"])
        self.assertFalse((published / "asset-licenses.json").exists())

    def test_duplicate_destination_is_untouched(self):
        self.destination.mkdir()
        sentinel = self.destination / "important.txt"
        sentinel.write_text("do not replace")
        with self.assertRaises(PackImportError) as caught:
            import_pack_to_copy(self.preview(), self.destination)
        self.assertEqual(caught.exception.code, "destination_exists")
        self.assertEqual(sentinel.read_text(), "do not replace")

    def test_changed_archive_and_source_are_refused(self):
        preview = self.preview()
        self.archive.write_bytes(self.archive.read_bytes() + b"appended")
        with self.assertRaises(PackImportError) as caught:
            import_pack_to_copy(preview, self.destination)
        self.assertEqual(caught.exception.code, "pack_changed")
        self.assertFalse(self.destination.exists())
        self.archive.unlink()
        build_pack(self.pack_source, self.archive, _manifest(self.payload))
        preview = self.preview()
        self.source.write_bytes(self.source.read_bytes() + b" ")
        with self.assertRaises(PackImportError) as caught:
            import_pack_to_copy(preview, self.destination)
        self.assertEqual(caught.exception.code, "source_changed")
        self.assertFalse(self.destination.exists())

    def test_bad_image_header_rejected_and_stage_rolled_back(self):
        invalid = b"not a PNG, although named PNG"
        bad_source = self.root / "bad_source"
        (bad_source / "terrain").mkdir(parents=True)
        (bad_source / "terrain/grass.png").write_bytes(invalid)
        bad_pack = build_pack(bad_source, self.root / "bad_pack.zip",
                              _manifest(invalid))
        preview = preview_pack_import(self.source, bad_pack, self.bindings)
        with self.assertRaises(PackImportError) as caught:
            import_pack_to_copy(preview, self.destination)
        self.assertEqual(caught.exception.code, "invalid_asset")
        self.assertFalse(self.destination.exists())

    def test_collisions_unknown_resources_and_invalid_kinds_fail(self):
        for bindings in (
            [*self.bindings, *self.bindings],
            [{"path": "../game.json", "kind": "sprite", "name": "grass"}],
            [{"path": "terrain/grass.png", "kind": "sound", "name": "grass"}],
            [{"path": "terrain/grass.png", "kind": "sprite", "name": "../other"}],
            [{"path": "terrain/grass.png", "kind": "animation", "name": "grass"}],
        ):
            with self.subTest(bindings=bindings), self.assertRaises(PackImportError):
                preview_pack_import(self.source, self.archive, bindings)
        imported = import_pack_to_copy(self.preview(), self.destination)
        with self.assertRaises(PackImportError) as caught:
            preview_pack_import(imported / "game.json", self.archive, self.bindings)
        self.assertEqual(caught.exception.code, "collision")

    def test_staging_io_failure_keeps_original_files_and_destination_absent(self):
        preview = self.preview()
        before = (self.source.read_bytes(),
                  (self.source_root / "game.game.json").read_bytes())
        real_copy = shutil.copy2
        def fail_copy(src, dst, *args, **kwargs):
            raise OSError("injected staging copy failure")
        # Introduce an existing validated source asset, requiring a physical copy.
        content, project = reference_project()
        project.assets = {
            "version": 1,
            "entries": [{"id": "existing", "kind": "sprite",
                         "path": "art/existing.png"}],
            "bindings": {},
        }
        (self.source_root / "art").mkdir()
        (self.source_root / "art/existing.png").write_bytes(_png())
        self.source.unlink()
        (self.source_root / "game.game.json").unlink()
        AuthoringSession.new(content, project).save_as(self.source)
        preview = self.preview()
        before = (self.source.read_bytes(),
                  (self.source_root / "game.game.json").read_bytes())
        with patch("drawtemp.export.pack_import.shutil.copy2", side_effect=fail_copy):
            with self.assertRaises(OSError):
                import_pack_to_copy(preview, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual((self.source.read_bytes(),
                          (self.source_root / "game.game.json").read_bytes()),
                         before)
        self.assertTrue((self.source_root / "art/existing.png").exists())

    def test_preserves_existing_registered_source_asset_in_new_copy(self):
        content, project = reference_project()
        project.assets = {
            "version": 1,
            "entries": [{"id": "prior-sprite", "kind": "sprite",
                         "path": "art/prior.png"}],
            "bindings": {},
        }
        (self.source_root / "art").mkdir()
        original = _png()
        (self.source_root / "art/prior.png").write_bytes(original)
        self.source.unlink()
        (self.source_root / "game.game.json").unlink()
        AuthoringSession.new(content, project).save_as(self.source)
        preview = self.preview()
        imported = import_pack_to_copy(preview, self.destination)
        self.assertEqual((imported / "art/prior.png").read_bytes(), original)
        data, manifest = validate_pair(
            json.loads((imported / "game.json").read_text(encoding="utf-8")),
            json.loads((imported / "game.game.json").read_text(encoding="utf-8")))
        registry = AssetRegistry(manifest["assets"])
        self.assertEqual(registry.diagnostics(imported), [])
        self.assertEqual({e["id"] for e in registry.to_dict()["entries"]},
                         {"prior-sprite", "art-pack.grass"})

    def test_cli_is_preview_only_without_explicit_confirm(self):
        import contextlib
        from io import StringIO
        from drawtemp.export.pack_import_cli import main
        choices = self.root / "choices.json"
        choices.write_text(json.dumps(self.bindings), encoding="utf-8")
        args = ["--content", str(self.source), "--pack", str(self.archive),
                "--bindings", str(choices)]
        output = StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(args), 0)
        self.assertFalse(json.loads(output.getvalue())["applied"])
        self.assertFalse(self.destination.exists())
        with self.assertRaises(SystemExit):
            main([*args, "--confirm"])
        output = StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main([*args, "--output", str(self.destination),
                                   "--confirm"]), 0)
        self.assertTrue(json.loads(output.getvalue())["applied"])
        self.assertTrue((self.destination / "game.game.json").is_file())

    def test_non_destructive_destination_policy(self):
        preview = self.preview()
        with self.assertRaises(PackImportError) as caught:
            import_pack_to_copy(preview, self.source_root / "nested")
        self.assertEqual(caught.exception.code, "invalid_destination")
        self.assertFalse((self.source_root / "nested").exists())


if __name__ == "__main__":
    unittest.main()

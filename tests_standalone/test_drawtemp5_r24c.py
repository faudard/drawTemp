"""R24.C: pack publication/import, dependencies, digest and fail-closed rollback."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from drawtemp.assets.packs import (
    ResourcePackError, RECEIPT_NAMESPACE, inspect_pack, install_pack,
    publish_pack, validate_pack_manifest, verify_installed_packs,
)
from drawtemp.export.r15 import preflight
from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from drawtemp.sdk.reference import reference_project


def png_bytes():
    import zlib
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + (
            struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress((b"\x00" + b"\x33\x44\x55\xff" * 2) * 2)) +
            chunk(b"IEND", b""))


PNG = png_bytes()


def make_manifest(pack_id="forest-pack", deps=None):
    return {
        "schema_version": 1,
        "id": pack_id,
        "version": "1.0.0",
        "name": "Forest Test Pack",
        "files": [{
            "path": "terrain/forest.png",
            "sha256": sha256(PNG).hexdigest(),
            "bytes": len(PNG),
            "license": {
                "id": "Fixture-Only", "rights_holder": "Synthetic test fixture",
                "evidence": "Generated solely by unit test, not a legal grant",
                "redistributable": True, "modifiable": True,
            },
        }],
        "entries": [
            {"id": "tree", "kind": "sprite", "path": "terrain/forest.png"},
            {"id": "tree-loop", "kind": "animation", "loop": True,
             "frames": [{"sprite": "tree", "duration_ms": 130}]},
        ],
        "dependencies": deps if deps is not None else [],
    }


def make_source(root, document):
    root.mkdir()
    (root / "pack.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    path = root / "files/terrain/forest.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(PNG)
    return root


class PackPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = make_source(self.root / "source", make_manifest())
        self.archive = self.root / "forest.rpack"

    def test_published_archive_is_deterministic_and_inspectable(self):
        first = publish_pack(self.input, self.archive)
        self.assertEqual(first.to_dict()["manifest"]["id"], "forest-pack")
        self.assertEqual(first.sha256, inspect_pack(self.archive).sha256)
        self.assertEqual(first.manifest["entries"][0]["id"], "tree")
        with self.assertRaises(TypeError):
            first.manifest["id"] = "bad"
        other = self.root / "forest-copy.rpack"
        publish_pack(self.input, other)
        self.assertEqual(self.archive.read_bytes(), other.read_bytes())
        with self.assertRaises(ResourcePackError) as caught:
            publish_pack(self.input, self.archive)
        self.assertEqual(caught.exception.code, "already_exists")

    def test_malformed_and_unlicensed_files_fail_before_publication(self):
        base = make_manifest()
        wrong = [
            ({**base, "schema_version": 2}, "unsupported_schema"),
            ({**base, "version": "1.0.0-dev"}, "unsupported_version"),
            ({**base, "id": "../escape"}, "invalid_manifest"),
            ({**base, "files": [base["files"][0], base["files"][0]]}, "path_collision"),
            ({**base, "files": [{**base["files"][0], "sha256": "0" * 64}]}, None),
            ({**base, "files": [{**base["files"][0],
                "license": {**base["files"][0]["license"], "redistributable": False}}]},
             "license_unapproved"),
            ({**base, "entries": [base["entries"][0], deepcopy(base["entries"][0])]},
             "id_collision"),
            ({**base, "dependencies": [{"id": "forest-pack", "version": "1.0.0",
                                        "sha256": "0" * 64}]}, "invalid_dependency"),
        ]
        for index, (manifest, expected) in enumerate(wrong):
            with self.subTest(case=index):
                folder = self.root / ("wrong-" + str(index))
                make_source(folder, manifest)
                target = self.root / ("wrong-" + str(index) + ".rpack")
                with self.assertRaises(ResourcePackError) as caught:
                    publish_pack(folder, target)
                if expected:
                    self.assertEqual(caught.exception.code, expected)
                self.assertFalse(target.exists())
        (self.input / "files/terrain/forest.png").write_bytes(PNG + b"tampered")
        with self.assertRaises(ResourcePackError) as caught:
            publish_pack(self.input, self.archive)
        self.assertEqual(caught.exception.code, "hash_mismatch")
        self.assertFalse(self.archive.exists())

    def test_archive_unlisted_member_tamper_and_stale(self):
        publish_pack(self.input, self.archive)
        preview = inspect_pack(self.archive)
        with ZipFile(self.archive, "a") as archive:
            archive.writestr("files/../evil.png", PNG)
        with self.assertRaises(ResourcePackError):
            inspect_pack(self.archive)
        with TemporaryDirectory() as root:
            editor = AuthoringSession.new(*reference_project())
            with self.assertRaises(ResourcePackError) as caught:
                install_pack(preview, editor, root)
            self.assertEqual(caught.exception.code, "stale_preview")
            self.assertEqual(editor.revision, 0)
        self.assertFalse((self.root / "evil.png").exists())

    def test_noncanonical_archive_members_fail_closed(self):
        for index, extra in enumerate(["evil.py", "files/../escape.png",
                                       "files/TERRAIN/forest.png"]):
            target = self.root / ("unexpected-" + str(index) + ".rpack")
            with ZipFile(target, "w") as stream:
                stream.writestr("pack.json", json.dumps(make_manifest()))
                stream.writestr("files/terrain/forest.png", PNG)
                stream.writestr(extra, PNG)
            with self.subTest(extra=extra), self.assertRaises(ResourcePackError):
                inspect_pack(target)


class PackInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.editor = AuthoringSession.new(*reference_project())

    def pack(self, name="forest-pack", deps=None):
        source = make_source(self.root / ("src-" + name), make_manifest(name, deps))
        return publish_pack(source, self.root / (name + ".rpack"))

    def test_canonical_commit_save_roundtrip_export_preflight_and_tamper(self):
        preview = self.pack()
        before = self.editor.snapshot().to_dict()
        install_pack(preview, self.editor, self.root, expected_revision=0)
        current = self.editor.snapshot().to_dict()
        self.assertEqual(self.editor.revision, 1)
        self.assertEqual(before["content"], current["content"])
        assets = current["project"]["assets"]["entries"]
        self.assertEqual([row["id"] for row in assets],
                         ["forest-pack.tree", "forest-pack.tree-loop"])
        receipt = current["project"]["extensions"][RECEIPT_NAMESPACE]["data"]["packs"][0]
        self.assertEqual(receipt["sha256"], preview.sha256)
        self.assertEqual(verify_installed_packs(self.root, current["project"]), [])
        saved = self.root / "game.json"
        self.editor.save_as(saved)
        self.assertTrue(preflight(saved)["passed"])
        self.editor.undo()
        self.assertNotIn("assets", self.editor.snapshot().to_dict()["project"])
        self.editor.redo()
        self.assertEqual(self.editor.snapshot().to_dict()["project"], current["project"])
        sprite = self.root / receipt["files"][0]["path"]
        sprite.write_bytes(PNG + b"corruption")
        self.assertTrue(any("SHA-256 mismatch" in issue for issue in
                            verify_installed_packs(self.root, current["project"])))
        result = preflight(saved)
        self.assertFalse(result["passed"])
        self.assertTrue(any("SHA-256 mismatch" in issue for issue in result["errors"]))

    def test_pinned_deps_and_no_duplicate_import(self):
        base = self.pack()
        dependent = self.pack("second-pack", deps=[
            {"id": "forest-pack", "version": "1.0.0", "sha256": base.sha256}])
        with self.assertRaises(AuthoringError):
            install_pack(dependent, self.editor, self.root)
        self.assertEqual(self.editor.revision, 0)
        self.assertFalse((self.root / "assets").exists())
        install_pack(base, self.editor, self.root)
        install_pack(dependent, self.editor, self.root)
        self.assertEqual(self.editor.revision, 2)
        self.assertEqual(len(self.editor.snapshot().to_dict()
                             ["project"]["extensions"][RECEIPT_NAMESPACE]["data"]["packs"]), 2)
        with self.assertRaises(AuthoringError):
            install_pack(base, self.editor, self.root)
        self.assertEqual(self.editor.revision, 2)

    def test_rollback_on_apply_fault_does_not_change_existing_bytes(self):
        preview = self.pack()
        unchanged = self.editor.snapshot().to_dict()
        with patch.object(self.editor, "apply", side_effect=RuntimeError("write fault")):
            with self.assertRaisesRegex(RuntimeError, "write fault"):
                install_pack(preview, self.editor, self.root)
        self.assertEqual(self.editor.snapshot().to_dict(), unchanged)
        self.assertFalse((self.root / "assets").exists())
        collision = self.root / "assets/packs/forest-pack/1.0.0/terrain/forest.png"
        collision.parent.mkdir(parents=True)
        collision.write_bytes(b"existing bytes")
        with self.assertRaises(ResourcePackError) as caught:
            install_pack(preview, self.editor, self.root)
        self.assertEqual(caught.exception.code, "already_exists")
        self.assertEqual(collision.read_bytes(), b"existing bytes")
        self.assertEqual(self.editor.revision, 0)

    def test_reject_stale_revision_and_invalid_data_without_writes(self):
        preview = self.pack()
        with self.assertRaises(ResourcePackError) as caught:
            install_pack(preview, self.editor, self.root, expected_revision=1)
        self.assertEqual(caught.exception.code, "stale_revision")
        self.assertFalse((self.root / "assets").exists())
        existing = self.editor.snapshot().to_dict()
        with self.assertRaises(ResourcePackError):
            validate_pack_manifest({**make_manifest(), "entries": [
                {"id": "evil", "kind": "sprite", "path": "../evil.png"}]})
        self.assertEqual(self.editor.snapshot().to_dict(), existing)

    def test_legacy_projects_unaffected(self):
        content, project = reference_project()
        self.assertNotIn("extensions", project.to_dict())
        self.assertEqual(verify_installed_packs(self.root, project.to_dict()), [])


if __name__ == "__main__":
    unittest.main()

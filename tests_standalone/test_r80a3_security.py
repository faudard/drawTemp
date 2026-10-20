"""R80.A3 regression tests for SDK compatibility and importer fail-closed inputs."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from drawtemp.export.creator_packs import PackError, build_pack, inspect_pack
from drawtemp.export.pack_import import (
    PackImportError, _read_project_document, import_pack_to_copy, preview_pack_import,
)
from drawtemp.export.safe_inputs import UnsafeSnapshotError, read_regular_snapshot
from drawtemp.quality.r80_security import (
    A3SecurityError, R16_NAMES, R16_FEATURES, check_inert_import_security,
    check_python_sdk, run_a3_audit,
)
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project


def _pack_document(raw):
    return {
        "schema": 1, "id": "a3-pack", "version": "1.0.0", "kind": "terrain",
        "requires": {"min_api": "1.0.0", "max_api": "2.0.0",
                     "features": ["authoring.v1"]},
        "files": [{"path": "terrain/grass.png", "size": len(raw),
                   "sha256": sha256(raw).hexdigest(),
                   "license": "CC0-1.0", "origin": "R80 original test bytes"}],
    }


class R80A3SecurityTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def test_r16_public_python_surface_still_resolves(self):
        result = check_python_sdk()
        self.assertEqual(result["resolved_r16_symbols"], len(R16_NAMES))
        self.assertEqual(set(result["preserved_r16_features"]), R16_FEATURES)
        self.assertTrue(result["python_surface_compatible"])
        self.assertFalse(result["native_abi_verified"])

    def test_removed_public_symbol_is_detected(self):
        import drawtemp.sdk as sdk
        altered = [name for name in sdk.__all__ if name != "PlayerSlotStore"]
        with patch.object(sdk, "__all__", altered):
            with self.assertRaisesRegex(A3SecurityError, "public names removed"):
                check_python_sdk()

    def test_security_smoke_refuses_exec_fields_and_traversal(self):
        report = check_inert_import_security()
        self.assertEqual(report["pack_traversal_cases_rejected"], 6)
        self.assertEqual(report["executable_mod_cases_rejected"], 2)
        self.assertFalse(report["source_modified"])
        self.assertFalse(report["rights_verified"])

    def test_cli_report_never_claims_release(self):
        from drawtemp.quality.r80_security import main
        target = self.root / "a3" / "report.json"
        self.assertEqual(main(["--output", str(target)]), 0)
        report = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["release_certified"])
        self.assertFalse(report["tag_allowed"])

    def test_snapshot_rejects_bytes_over_limit_and_direct_symlink(self):
        source = self.root / "source.txt"
        source.write_bytes(b"12345")
        self.assertEqual(read_regular_snapshot(source, limit=5), b"12345")
        with self.assertRaises(UnsafeSnapshotError):
            read_regular_snapshot(source, limit=4)
        alias = self.root / "alias.txt"
        try:
            alias.symlink_to(source)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(UnsafeSnapshotError):
            read_regular_snapshot(alias, limit=100)

    def test_snapshot_detects_concurrent_file_metadata_change(self):
        source = self.root / "source.txt"
        source.write_bytes(b"12345")
        actual_fstat = os.fstat
        hits = [0]

        def changed_after_read(fd):
            original = actual_fstat(fd)
            hits[0] += 1
            if hits[0] == 1:
                return original
            return SimpleNamespace(
                st_mode=original.st_mode, st_dev=original.st_dev,
                st_ino=original.st_ino, st_size=original.st_size,
                st_mtime_ns=original.st_mtime_ns + 1,
                st_ctime_ns=original.st_ctime_ns,
            )
        with patch("drawtemp.export.safe_inputs.os.fstat", side_effect=changed_after_read):
            with self.assertRaisesRegex(UnsafeSnapshotError, "modified during"):
                read_regular_snapshot(source, limit=100)

    def test_duplicate_and_nan_project_keys_rejected(self):
        path = self.root / "project.json"
        for content in ('{"version":1,"version":1}', '{"version":1,"num":NaN}',
                        '{"version":1,"num":Infinity}'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(PackImportError) as raised:
                    _read_project_document(path)
                self.assertEqual(raised.exception.code, "invalid_source")
                self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_zip_symlink_is_rejected_by_creator_inspection(self):
        path = self.root / "real.zip"
        path.write_bytes(b"not a valid ZIP")
        alias = self.root / "linked.zip"
        try:
            alias.symlink_to(path)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(PackError) as raised:
            inspect_pack(alias)
        self.assertEqual(raised.exception.code, "unsafe_archive")

    def make_import(self):
        directory = self.root / "project"
        directory.mkdir()
        content, project = reference_project()
        source = directory / "game.json"
        AuthoringSession.new(content, project).save_as(source)
        pack_dir = self.root / "resource"
        (pack_dir / "terrain").mkdir(parents=True)
        # The importer currently checks the PNG magic and minimum 24 bytes.
        raw = b"\x89PNG\r\n\x1a\n" + b"R80-a3-inert-test-bytes"
        (pack_dir / "terrain" / "grass.png").write_bytes(raw)
        pack = build_pack(pack_dir, self.root / "pack.zip", _pack_document(raw))
        bindings = [{"path": "terrain/grass.png", "kind": "sprite", "name": "grass"}]
        return source, pack, bindings

    def test_import_refuses_source_changed_after_preview(self):
        source, pack, bindings = self.make_import()
        preview = preview_pack_import(source, pack, bindings)
        source.write_bytes(source.read_bytes() + b" ")
        target = self.root / "published"
        with self.assertRaises(PackImportError) as raised:
            import_pack_to_copy(preview, target)
        self.assertEqual(raised.exception.code, "source_changed")
        self.assertFalse(target.exists())

    def test_import_refuses_document_mutated_mid_staging(self):
        from drawtemp.export import pack_import
        source, pack, bindings = self.make_import()
        original = source.read_bytes()
        preview = preview_pack_import(source, pack, bindings)
        real_verify = pack_import._verify_selected_bytes

        def mutate_after_validation(data, manifest, selections):
            validated = real_verify(data, manifest, selections)
            source.write_bytes(original + b" ")
            return validated

        target = self.root / "published"
        with patch("drawtemp.export.pack_import._verify_selected_bytes",
                   side_effect=mutate_after_validation):
            with self.assertRaises(PackImportError) as raised:
                import_pack_to_copy(preview, target)
        self.assertEqual(raised.exception.code, "source_changed")
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()

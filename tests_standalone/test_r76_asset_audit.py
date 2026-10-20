"""R76.A contracts: read-only scan, stable dependency graph and fail-closed reports."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from drawtemp.assets.optimization_audit import (
    COMPRESSION_POLICY, audit_registry, audit_content, main,
)
from sporebound.assets import AssetRegistry


def _chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))


def png(width=2, height=3):
    scanline = b"\x00" + b"\xff\x00\x00\xff" * width
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(scanline * height))
            + _chunk(b"IEND", b""))


def registry(entries, bindings=None):
    return AssetRegistry({"version": 1, "entries": entries,
                          "bindings": bindings or {}})


class R76AAssetAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_dependency_graph_and_physical_atlas_count_once(self):
        asset = png()
        (self.root / "atlas.png").write_bytes(asset)
        entries = [
            {"id": "hero", "kind": "sprite", "path": "atlas.png",
             "region": [0, 0, 1, 3]},
            {"id": "enemy", "kind": "sprite", "path": "atlas.png",
             "region": [1, 0, 1, 3]},
            {"id": "walk", "kind": "animation", "loop": True,
             "frames": [{"sprite": "hero", "duration_ms": 100},
                        {"sprite": "enemy", "duration_ms": 100}]},
        ]
        report = audit_registry(registry(entries, {"animation": {"hero_walk": "walk"}}),
                                self.root)
        self.assertEqual(report["integrity"], "inspected")
        self.assertEqual(report["rights"], "not_assessed")
        self.assertFalse(report["release_certified"])
        self.assertEqual(report["summary"]["registered_assets"], 3)
        self.assertEqual(report["summary"]["physical_paths"], 1)
        self.assertEqual(report["summary"]["encoded_bytes_hashed"], len(asset))
        self.assertEqual(report["summary"]["rgba_staging_bytes_estimate"], 24)
        self.assertEqual(report["files"][0]["sha256"], sha256(asset).hexdigest())
        self.assertEqual([d["relation"] for d in report["dependency_edges"]],
                         ["animation_frame", "animation_frame",
                          "presentation_binding"])
        self.assertEqual(json.dumps(report, sort_keys=True),
                         json.dumps(audit_registry(registry(entries,
                                      {"animation": {"hero_walk": "walk"}}),
                                      self.root), sort_keys=True))

    def test_duplicate_group_is_suggestion_and_originals_untouched(self):
        original = png(1, 1)
        for name in ("one.png", "two.png"):
            (self.root / name).write_bytes(original)
        entries = [{"id": name[:-4], "kind": "sprite", "path": name}
                   for name in ("one.png", "two.png")]
        before = {f.name: f.read_bytes() for f in self.root.iterdir()}
        report = audit_registry(registry(entries), self.root)
        self.assertEqual(report["duplicate_candidates"], [["one.png", "two.png"]])
        self.assertEqual(report["summary"]["duplicate_content_groups"], 1)
        self.assertEqual(COMPRESSION_POLICY["version"], 1)
        self.assertEqual(report["compression_policy"]["application"], "manual_review_only")
        self.assertEqual(before, {f.name: f.read_bytes() for f in self.root.iterdir()})

    def test_missing_bad_signature_and_large_dimensions_fail_closed(self):
        (self.root / "bad.png").write_bytes(b"this is not png")
        (self.root / "huge.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" +
            struct.pack(">II", 99999, 1) + b"\x08\x06\x00\x00\x00")
        entries = [
            {"id": "bad", "kind": "sprite", "path": "bad.png"},
            {"id": "huge", "kind": "portrait", "path": "huge.png"},
            {"id": "missing", "kind": "sprite", "path": "missing.png"},
        ]
        report = audit_registry(registry(entries), self.root)
        self.assertEqual(report["integrity"], "blocked")
        self.assertEqual(report["summary"]["hashed_files"], 0)
        self.assertEqual(len(report["issues"]), 3)
        self.assertTrue(all(row["bytes"] is None for row in report["files"]))

    def test_case_collisions_are_rejected_even_on_case_sensitive_host(self):
        (self.root / "A.png").write_bytes(png())
        (self.root / "a.png").write_bytes(png())
        report = audit_registry(registry([
            {"id": "a1", "kind": "sprite", "path": "A.png"},
            {"id": "a2", "kind": "sprite", "path": "a.png"},
        ]), self.root)
        self.assertEqual(report["integrity"], "blocked")
        self.assertIn("case_collision", [row["code"] for row in report["issues"]])

    def test_symlink_refused_even_when_target_inside_root(self):
        target = self.root / "real.png"
        target.write_bytes(png())
        try:
            (self.root / "link.png").symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink unavailable")
        report = audit_registry(registry([
            {"id": "link", "kind": "sprite", "path": "link.png"},
        ]), self.root)
        self.assertEqual(report["integrity"], "blocked")
        self.assertIn("symbolic_link", report["issues"][0]["detail"])

    def test_sound_is_measured_as_encoded_bytes_not_fictional_gpu_ram(self):
        (self.root / "voice.ogg").write_bytes(b"OggS" + b"\x00" * 32)
        report = audit_registry(registry([
            {"id": "voice", "kind": "sound", "path": "voice.ogg"},
        ]), self.root)
        self.assertEqual(report["integrity"], "inspected")
        self.assertIsNone(report["files"][0]["rgba_staging_bytes_estimate"])
        self.assertEqual(report["quality"]["gpu_memory"], "not_measured")

    def test_strict_r15_rights_gate_is_reused_not_reimplemented(self):
        content = self.root / "story.json"
        content.write_text("{}", encoding="utf-8")
        project = self.root / "story.game.json"
        project.write_text(json.dumps({"assets": registry([]).to_dict()}),
                           encoding="utf-8")
        from drawtemp.export import r15
        with patch.object(r15, "preflight", return_value={
                "passed": False, "rights_attestations_checked": False,
                "errors": ["Missing rights"], "warnings": [],
        }) as gate:
            result = audit_content(content)
            gate.assert_called_once_with(content.resolve(), require_licenses=True)
            self.assertEqual(result["integrity"], "blocked")
            self.assertEqual(result["rights"], "blocked")
            self.assertEqual(result["r15_preflight"]["errors"], ["Missing rights"])
        # A green unit-test mock is NOT a real redistribution or release certificate.
        with patch.object(r15, "preflight", return_value={
                "passed": True, "rights_attestations_checked": True,
                "errors": [], "warnings": [],
        }):
            result = audit_content(content)
            self.assertEqual(result["integrity"], "inspected")
            self.assertEqual(result["rights"], "r15_strict_preflight_passed")
            self.assertFalse(result["release_certified"])

    def test_cli_rejects_report_inside_project_and_leaves_game_untouched(self):
        content = self.root / "bad.json"
        content.write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit) as raised:
            main(["--content", str(content), "--report", str(self.root / "report.json")])
        self.assertEqual(raised.exception.code, 2)
        self.assertFalse((self.root / "report.json").exists())
        self.assertEqual(content.read_text(), "{}")


if __name__ == "__main__":
    unittest.main()

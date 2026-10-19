"""R23.A release safety regressions against forged or unsafe exports."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.r15 import ExportError, export_game, verify_bundle
from drawtemp.export.templates import create_template


class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="r23a-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.content = create_template("blank", self.root / "source") / "game.json"
        runtime = self.root / "runtime"
        runtime.mkdir()
        native = "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"
        (runtime / native).write_bytes(b"native fixture for the integrity contract")
        (runtime / "support.dat").write_bytes(b"Qt fixture")
        self.bundle = export_game(self.content, runtime, self.root / "bundle")

    def manifest(self):
        return json.loads((self.bundle / "manifest.json").read_text(encoding="utf-8"))

    def write_manifest(self, document):
        (self.bundle / "manifest.json").write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8")

    def test_bundle_relocates_and_historical_manifest_remains_compatible(self):
        import shutil
        moved = self.root / "elsewhere" / "bundle"
        moved.parent.mkdir()
        shutil.move(self.bundle, moved)
        self.assertEqual(verify_bundle(moved)["schema"], 1)
        self.assertEqual(verify_bundle(moved)["kind"], "drawtemp5-standalone-game")

    def test_missing_companion_is_rejected_even_if_file_index_was_rewritten(self):
        (self.bundle / "game" / "game.game.json").unlink()
        manifest = self.manifest()
        manifest["files"] = [entry for entry in manifest["files"]
                             if entry["path"] != "game/game.game.json"]
        self.write_manifest(manifest)
        with self.assertRaisesRegex(ExportError, "GameProject"):
            verify_bundle(self.bundle)

    def test_manifest_duplicate_json_keys_are_rejected(self):
        path = self.bundle / "manifest.json"
        raw = path.read_text(encoding="utf-8")
        path.write_text('{"schema": 1, ' + raw.lstrip()[1:], encoding="utf-8")
        with self.assertRaisesRegex(ExportError, "Duplicate JSON"):
            verify_bundle(self.bundle)

    def test_unbounded_manifest_is_rejected_before_json_parsing(self):
        path = self.bundle / "manifest.json"
        with path.open("ab") as fp:
            fp.write(b" " * (8 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(ExportError, "8 MiB"):
            verify_bundle(self.bundle)

    def test_symlink_to_internal_file_is_rejected(self):
        target = self.bundle / "Player" / "support.dat"
        target.unlink()
        try:
            target.symlink_to("DrawTempPlayer.exe" if os.name == "nt"
                              else "DrawTempPlayer")
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Symlinks unavailable: " + str(exc))
        with self.assertRaisesRegex(ExportError, "Symlink"):
            verify_bundle(self.bundle)

    def test_symlinked_folder_is_rejected(self):
        try:
            (self.bundle / "alias").symlink_to(self.bundle / "game",
                                              target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Symlinks unavailable: " + str(exc))
        with self.assertRaisesRegex(ExportError, "Symlink"):
            verify_bundle(self.bundle)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX-only special file")
    def test_fifo_is_rejected(self):
        os.mkfifo(self.bundle / "unindexed.fifo")
        with self.assertRaisesRegex(ExportError, "Special file"):
            verify_bundle(self.bundle)

    def test_broken_symlink_destination_is_not_overwritten(self):
        target = self.root / "broken"
        try:
            target.symlink_to(self.root / "not-created", target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest("Symlinks unavailable: " + str(exc))
        runtime = self.root / "runtime"
        with self.assertRaisesRegex(ExportError, "Destination exists"):
            export_game(self.content, runtime, target)
        self.assertTrue(target.is_symlink())


if __name__ == "__main__":
    unittest.main()

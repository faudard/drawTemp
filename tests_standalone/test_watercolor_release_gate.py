"""Release-gate regression tests; no Pillow, Tk, OpenCV or artwork required."""
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile
import zlib

from scripts.import_watercolor_sheets import SHEETS, build_registry
from scripts.verify_watercolor_release import verify_archive, verify_directory

PREFIX = "assets/watercolor/"


def _chunk(name, data):
    return (struct.pack(">I", len(data)) + name + data +
            struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF))


def png():
    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) +
            _chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff")) +
            _chunk(b"IEND", b""))


def fixture():
    sprites = [{"id": group + "_" + pose,
                "path": f"sprites/{group}/{pose}.png",
                "frame_size": [1, 1]}
               for group, _, _, _, poses in SHEETS
               for pose in poses.split()]
    return {"schema_version": 1, "sprites": sprites}, build_registry(sprites)


class WatercolorReleaseGateTests(unittest.TestCase):
    def test_real_png_signature_and_references_accept_full_bundle(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, registry = fixture()
            archive = root / "pack.zip"
            with ZipFile(archive, "w") as out:
                out.writestr(PREFIX + "index.json", json.dumps(index))
                out.writestr(PREFIX + "registry.json", json.dumps(registry))
                for sprite in index["sprites"]:
                    out.writestr(PREFIX + sprite["path"], png())
            result = verify_archive(archive)
            self.assertEqual(result["sprites"], 88)
            self.assertEqual(result["animations"], 15)
            self.assertEqual(sum(result["groups"].values()), 88)

    def test_rejects_corrupt_crc_and_false_provenance_hash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, registry = fixture()
            for defect in ('crc', 'hash'):
                with self.subTest(defect=defect):
                    archive = root / (defect + '.zip')
                    if defect == 'hash':
                        index['sprites'][0]['sha256'] = '0' * 64
                    with ZipFile(archive, 'w') as out:
                        out.writestr(PREFIX + 'index.json', json.dumps(index))
                        out.writestr(PREFIX + 'registry.json', json.dumps(registry))
                        for i, sprite in enumerate(index['sprites']):
                            data = bytearray(png())
                            if defect == 'crc' and i == 0:
                                data[-1] ^= 1
                            out.writestr(PREFIX + sprite['path'], bytes(data))
                    with self.assertRaisesRegex(ValueError,
                                                'CRC' if defect == 'crc' else 'SHA-256'):
                        verify_archive(archive)

    def test_absent_pngs_report_pending_only_when_explicitly_allowed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(verify_directory(root, allow_missing=True)["status"],
                             "not_published")
            with self.assertRaisesRegex(ValueError, "no files"):
                verify_directory(root)

    def test_partial_directory_is_hard_failure(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, registry = fixture()
            (root / "sprites/vfx").mkdir(parents=True)
            (root / "sprites/vfx/moon_small.png").write_bytes(png())
            (root / "index.json").write_text(json.dumps(index))
            (root / "registry.json").write_text(json.dumps(registry))
            with self.assertRaisesRegex(ValueError, "Missing sprite"):
                verify_directory(root, allow_missing=True)

    def test_registry_and_index_must_agree(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, registry = fixture()
            index["sprites"][0]["frame_size"] = [2, 2]
            archive = root / "bad.zip"
            with ZipFile(archive, "w") as out:
                out.writestr(PREFIX + "index.json", json.dumps(index))
                out.writestr(PREFIX + "registry.json", json.dumps(registry))
                for sprite in index["sprites"]:
                    out.writestr(PREFIX + sprite["path"], png())
            with self.assertRaisesRegex(ValueError, "dimensions mismatch"):
                verify_archive(archive)


if __name__ == "__main__":
    unittest.main()

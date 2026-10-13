"""Watercolor v3 publication: crash-safe import, provenance and idempotence."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from scripts.publish_watercolor_pack import publish
from scripts.verify_watercolor_release import verify_directory
from tests_standalone.test_watercolor_release_gate import PREFIX, fixture, png


def sample_bundle(directory):
    root = Path(directory)
    pack = root / "source_v3.zip"
    dest = root / "watercolor"
    dest.mkdir()
    index, registry = fixture()
    payload = png()
    with ZipFile(pack, "w") as archive:
        archive.writestr(PREFIX + "index.json", json.dumps(index))
        archive.writestr(PREFIX + "registry.json", json.dumps(registry))
        for sprite in index["sprites"]:
            archive.writestr(PREFIX + sprite["path"], payload)
    provenance = {
        "schema_version": 1,
        "source_archive": pack.name,
        "archive_sha256": sha256(pack.read_bytes()).hexdigest(),
        "sprite_hashes": {item["path"]: sha256(payload).hexdigest()
                          for item in index["sprites"]},
    }
    for name, data in (
            ("index.json", index), ("registry.json", registry),
            ("provenance.json", provenance)):
        (dest / name).write_text(json.dumps(data), encoding="utf-8")
    return pack, dest, provenance


class PublishWatercolorTests(unittest.TestCase):
    def test_dry_run_does_not_write_sprites(self):
        with TemporaryDirectory() as tmp:
            pack, root, _ = sample_bundle(tmp)
            self.assertEqual(publish(pack, root, dry_run=True)["status"],
                             "ready_to_publish")
            self.assertFalse((root / "sprites").exists())

    def test_atomic_publish_and_idempotent_second_run(self):
        with TemporaryDirectory() as tmp:
            pack, root, _ = sample_bundle(tmp)
            first = publish(pack, root)
            self.assertEqual(first["status"], "published")
            self.assertEqual(first["provenance_sha256_verified"], 88)
            self.assertEqual(verify_directory(root)["sprites"], 88)
            self.assertEqual(publish(pack, root)["status"], "already_published")
            self.assertFalse(list(root.glob(".watercolor-stage-*")))

    def test_rejects_different_archive_before_extracting(self):
        with TemporaryDirectory() as tmp:
            pack, root, _ = sample_bundle(tmp)
            pack.write_bytes(pack.read_bytes() + b"altered")
            with self.assertRaisesRegex(ValueError, "Bundle SHA-256"):
                publish(pack, root)
            self.assertFalse((root / "sprites").exists())

    def test_rejects_modified_png_without_partial_extraction(self):
        with TemporaryDirectory() as tmp:
            pack, root, data = sample_bundle(tmp)
            key = next(iter(data["sprite_hashes"]))
            data["sprite_hashes"][key] = "0" * 64
            (root / "provenance.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "Sprite SHA-256"):
                publish(pack, root)
            self.assertFalse((root / "sprites").exists())

    def test_rejects_conflicting_partial_installation(self):
        with TemporaryDirectory() as tmp:
            pack, root, _ = sample_bundle(tmp)
            (root / "sprites" / "vfx").mkdir(parents=True)
            (root / "sprites" / "vfx" / "moon_small.png").write_bytes(png())
            with self.assertRaises(ValueError):
                publish(pack, root)
            self.assertEqual(len(list((root / "sprites").rglob("*.png"))), 1)


if __name__ == "__main__":
    unittest.main()

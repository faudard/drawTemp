"""Headless VF-B catalog tests: real metadata, provenance and authored timing."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.watercolor_catalog import (
    DEFAULT_WATERCOLOR_ROOT, WatercolorCatalog,
)
from tests_standalone.test_watercolor_release_gate import png


def copied_metadata(directory):
    directory = Path(directory)
    for name in ("index.json", "registry.json", "provenance.json"):
        (directory / name).write_bytes((DEFAULT_WATERCOLOR_ROOT / name).read_bytes())
    return directory


class WatercolorCatalogTests(unittest.TestCase):
    def test_real_manifest_catalogues_all_88_png_and_15_animations(self):
        catalog = WatercolorCatalog()
        self.assertTrue(catalog.has_metadata())
        self.assertEqual(sum(i.kind == "sprite" for i in catalog.entries), 88)
        self.assertEqual(sum(i.kind == "animation" for i in catalog.entries), 15)
        self.assertEqual(catalog.lookup("jeanne_idle").group, "jeanne")
        self.assertEqual(catalog.lookup("anim_jeanne_attack").frame_count, 3)

    def test_authored_animation_timing_and_terminal_frames(self):
        catalog = WatercolorCatalog()
        self.assertEqual(catalog.frame("anim_jeanne_walk", 0),
                         ("jeanne_walk_a", 180))
        self.assertEqual(catalog.frame("anim_jeanne_walk", 1),
                         ("jeanne_walk_b", 180))
        self.assertEqual(catalog.sample("anim_jeanne_walk", 179),
                         ("jeanne_walk_a", 0))
        self.assertEqual(catalog.sample("anim_jeanne_walk", 180),
                         ("jeanne_walk_b", 1))
        self.assertEqual(catalog.sample("anim_jeanne_walk", 360),
                         ("jeanne_walk_a", 0))
        self.assertEqual(catalog.sample("anim_jeanne_attack", 9999),
                         ("jeanne_followthrough", 2))
        with self.assertRaises(IndexError):
            catalog.frame("anim_jeanne_walk", 2)
        with self.assertRaises(KeyError):
            catalog.lookup("fictional_pose")

    def test_missing_pack_remains_visible_but_not_usable(self):
        with TemporaryDirectory() as tmp:
            catalog = WatercolorCatalog(copied_metadata(tmp))
            self.assertEqual(catalog.status("jeanne_idle"), ("missing", None))
            self.assertEqual(catalog.status("jeanne_idle", verify=True),
                             ("missing", None))

    def test_verified_sprite_detects_modified_file(self):
        with TemporaryDirectory() as tmp:
            root = copied_metadata(tmp)
            relative = "sprites/jeanne/idle.png"
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(png())
            catalog = WatercolorCatalog(root)
            self.assertEqual(catalog.status("jeanne_idle", verify=True),
                             ("modified", None))
            provenance_path = root / "provenance.json"
            provenance = json.loads(provenance_path.read_text())
            provenance["sprite_hashes"][relative] = sha256(png()).hexdigest()
            provenance_path.write_text(json.dumps(provenance))
            catalog = WatercolorCatalog(root)
            status, verified_path = catalog.status("jeanne_idle", verify=True)
            self.assertEqual(status, "ready")
            # Windows 8.3 aliases and long paths may spell the same file differently.
            self.assertTrue(verified_path.samefile(target))

    def test_missing_metadata_is_safe_for_installed_wheels(self):
        with TemporaryDirectory() as tmp:
            catalog = WatercolorCatalog(tmp)
            self.assertFalse(catalog.has_metadata())
            self.assertEqual(catalog.entries, ())
            with self.assertRaises(KeyError):
                catalog.frame("jeanne_idle")


if __name__ == "__main__":
    unittest.main()

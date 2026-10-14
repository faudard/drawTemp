"""Jeanne watercolor motion: real PNG outputs, deterministic metadata and safe timing.

These tests require neither Pillow, NumPy nor OpenCV. Rendering remains
authoring-only; Player and Studio read pre-generated transparent PNG files.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest

from scripts.verify_watercolor_release import png_dimensions, verify_directory
from sporebound.watercolor_catalog import WatercolorCatalog, DEFAULT_WATERCOLOR_ROOT


class JeanneMotionPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = DEFAULT_WATERCOLOR_ROOT
        cls.index = json.loads((cls.root / "index.json").read_text(encoding="utf-8"))
        cls.provenance = json.loads((cls.root / "provenance.json").read_text(encoding="utf-8"))
        cls.registry = json.loads((cls.root / "registry.json").read_text(encoding="utf-8"))

    def test_composition_and_unchanged_source_provenance(self):
        original = self.provenance["sprite_hashes"]
        derived = self.provenance["derived_hashes"]
        self.assertEqual(len(original), 88)
        self.assertEqual(len(derived), 11)
        self.assertFalse(set(original) & set(derived))
        self.assertEqual(len(self.index["sprites"]), 99)
        self.assertEqual(
            {item["path"] for item in self.index["sprites"]},
            set(original) | set(derived))
        self.assertTrue(all(path.startswith("sprites/jeanne_motion/")
                            for path in derived))
        self.assertEqual(
            {entry["id"] for entry in self.registry["entries"]
             if entry["kind"] == "animation" and "jeanne" in entry["id"]},
            {"anim_jeanne_walk", "anim_jeanne_attack",
             "anim_jeanne_hit", "anim_jeanne_ko"})

    def test_real_clean_alpha_pngs_and_dimensions(self):
        digests = set()
        for relative, digest in self.provenance["derived_hashes"].items():
            with self.subTest(image=relative):
                png = (self.root / relative).read_bytes()
                self.assertEqual(sha256(png).hexdigest(), digest)
                self.assertEqual(png_dimensions(png, relative), (384, 341))
                self.assertNotIn(digest, digests, "Frames must not be byte-identical")
                digests.add(digest)

    def test_walk_eight_attack_twelve_hold_and_loop(self):
        catalog = WatercolorCatalog()
        self.assertEqual(catalog.lookup("anim_jeanne_walk").frame_count, 8)
        self.assertEqual(catalog.lookup("anim_jeanne_attack").frame_count, 12)
        walking = [catalog.frame("anim_jeanne_walk", i)[0] for i in range(8)]
        attacking = [catalog.frame("anim_jeanne_attack", i)[0] for i in range(12)]
        self.assertEqual(walking[0], "jeanne_walk_a")
        self.assertIn("jeanne_walk_b", walking)
        self.assertIn("jeanne_idle", walking)
        self.assertEqual(attacking[0], "jeanne_ready")
        self.assertIn("jeanne_windup", attacking)
        self.assertIn("jeanne_slash", attacking)
        self.assertIn("jeanne_followthrough", attacking)
        self.assertEqual(attacking[-1], "jeanne_guard")
        self.assertEqual(catalog.sample("anim_jeanne_walk", 600), ("jeanne_walk_a", 0))
        self.assertEqual(catalog.sample("anim_jeanne_attack", 9999), ("jeanne_guard", 11))
        self.assertEqual(len(set(attacking)), 12)

    def test_originals_and_derived_pass_full_release_gate(self):
        report = verify_directory(self.root)
        self.assertEqual(report["sprites"], 99)
        self.assertEqual(report["animations"], 15)
        self.assertEqual(report["provenance_sha256_verified"], 99)


if __name__ == "__main__":
    unittest.main()

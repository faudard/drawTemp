"""R19.B1: generated Jeanne gestures, portable R7 pack and strict candidate gate."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.art_gate import audit_character
from drawtemp.assets.character_runtime import CharacterPack
from drawtemp.assets.characters import ACTIONS, DIRECTIONS, render_frame, validate
from drawtemp.assets.jeanne_art import OUTFITS
from drawtemp.assets.jeanne_motion_r19 import (
    MOTION, build_jeanne_motion, motion_recipe, render_motion_strips,
)

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None


@unittest.skipUnless(Image is not None, "R19.B authoring requires Pillow")
class R19JeanneMotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "synthetic-source"
        folder = self.repo / "sporebound/content/art/jeanne"
        folder.mkdir(parents=True)
        self.source = folder / "jeanne_atlas.png"
        atlas = Image.new("RGBA", (256, 512))
        draw = ImageDraw.Draw(atlas)
        for row in range(8):
            for col in range(4):
                x, y = col * 64, row * 64
                fill = ((20 + row * 21) % 255,
                        (39 + col * 43) % 255,
                        (61 + row * 13 + col * 9) % 255, 255)
                draw.ellipse((x + 25, y + 12, x + 39, y + 30), fill=fill)
                draw.polygon([(x + 26, y + 31), (x + 40, y + 31),
                              (x + 42, y + 53), (x + 23, y + 54)],
                             fill=fill)
                draw.line((x + 22, y + 57, x + 40, y + 62), fill=fill, width=3)
        atlas.save(self.source)
        for mood in ("neutral", "smile", "determined"):
            Image.new("RGBA", (64, 64), (120, 103, 86, 255)).save(
                folder / f"jeanne_{mood}.png")
        self.target = self.root / "jeanne-r19"

    def test_six_directional_motion_strips_have_distinct_pixel_poses(self):
        from PIL import ImageChops
        strips = render_motion_strips(self.source)
        self.assertEqual(set(strips), set(MOTION))
        for action, strip in strips.items():
            count = len(MOTION[action][1])
            self.assertEqual(strip.size, (256, 64 * count))
            for column in range(4):
                frames = [strip.crop((column * 64, row * 64,
                                     (column + 1) * 64, (row + 1) * 64))
                          for row in range(count)]
                self.assertNotEqual(frames[0].tobytes(), frames[-1].tobytes(),
                                    (action, column))
                self.assertIsNotNone(ImageChops.difference(
                    frames[0], frames[-1]).getbbox())

    def test_r19_extends_r7_recipe_without_new_schema(self):
        from drawtemp.assets.jeanne_art import generate_recipe
        baseline = generate_recipe(self.root)
        before = json.dumps(baseline, sort_keys=True)
        result = motion_recipe(baseline)
        self.assertEqual(json.dumps(baseline, sort_keys=True), before)
        self.assertEqual(set(result["variants"]), set(OUTFITS))
        self.assertEqual(validate(result), result)
        for data in result["variants"].values():
            self.assertEqual(set(data["clips"]), set(ACTIONS))
            for action in MOTION:
                clip = data["clips"][action]
                self.assertEqual(clip["loop"], MOTION[action][3])
                self.assertEqual(set(clip["directions"]), set(DIRECTIONS))
                self.assertTrue(all(len(seq) == len(MOTION[action][1])
                                    for seq in clip["directions"].values()))

    def test_canonical_runtime_reuses_distinct_art_and_preserves_source(self):
        original = sha256(self.source.read_bytes()).hexdigest()
        recipe = build_jeanne_motion(self.repo, self.target)
        self.assertEqual(sha256(self.source.read_bytes()).hexdigest(), original)
        self.assertEqual(recipe["id"], "jeanne")
        proof = json.loads((self.target / "r19-motion-provenance.json").read_text())
        self.assertFalse(proof["redistribution_approved"])
        self.assertEqual(proof["art_review"], "pending")
        self.assertEqual(len(proof["derived_sha256"]), 6)
        self.assertTrue(all((self.target / name).is_file()
                            for name in proof["derived_sha256"]))
        report = audit_character(recipe, self.target)
        self.assertEqual(report["status"], "passed_structural_pixel",
                         report["issues"])
        self.assertEqual(report["human_art_approval"], "not_assessed")
        runtime = CharacterPack(self.target / "runtime")
        self.assertEqual(set(runtime.variants), set(OUTFITS))
        for action in MOTION:
            for direction in DIRECTIONS:
                for outfit in OUTFITS:
                    self.assertGreater(runtime.duration(outfit, action, direction), 0)
                    self.assertTrue(runtime.sample(variant=outfit, action=action,
                                                   direction=direction)["spriteReady"])
            first = render_frame(recipe, "peasant", action, "south", 0, self.target)
            last = render_frame(recipe, "peasant", action, "south",
                                len(MOTION[action][1]) - 1, self.target)
            self.assertNotEqual(first.tobytes(), last.tobytes())
        # Deterministic rebuild leaves every byte unchanged.
        current = (self.target / "runtime/atlas.png").read_bytes()
        build_jeanne_motion(self.repo, self.target)
        self.assertEqual((self.target / "runtime/atlas.png").read_bytes(), current)
        # An artist's edited sheet is never silently overwritten.
        edited = self.target / "sources/jeanne_r19_magic.png"
        edited.write_bytes(edited.read_bytes() + b"manual edit")
        with self.assertRaises(ValueError):
            build_jeanne_motion(self.repo, self.target)


if __name__ == "__main__":
    unittest.main()

"""Four-view artist PNG imports and the R7 export pipeline."""
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw
from drawtemp.assets.character_artwork import (
    import_character_art, import_part_set, import_reference_art, reference_path,
)
from drawtemp.assets.characters import (
    CharacterError, DIRECTIONS, render_frame, diagnostics, export_pack, validate,
)
from drawtemp.assets.character_parts import available_parts


class ArtworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.art = Path(self.temp.name) / "source"
        self.art.mkdir()

    def make_sources(self, size=(384, 512), *, opaque=False, copies=False):
        for index, facing in enumerate(("front", "right", "back", "left")):
            n = 0 if copies else index
            image = Image.new("RGBA", size,
                              "#eedbcd" if opaque else (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            cx = size[0] // 2
            draw.ellipse((cx-30+n*5, 40, cx+30+n*5, 120),
                         fill=(240, 181, 122, 255))
            draw.polygon([(cx-23, 123), (cx+25, 123),
                          (cx+30+n*5, size[1]-8),
                          (cx-28, size[1]-8)],
                         fill=(36+n*30, 80, 155, 255))
            image.save(self.art / (facing + ".png"))

    def test_import_native_resolution_with_portrait_and_reference(self):
        self.make_sources()
        Image.new("RGB", (512, 512), "#d0ae99").save(
            self.art / "portrait.png")
        Image.new("RGB", (900, 720), "white").save(
            self.art / "reference.png")
        doc, saved = import_character_art(
            self.root, self.art, "blue_knight", "Blue Knight")
        self.assertEqual(validate(doc), doc)
        self.assertEqual(doc["size"], [384, 512])
        self.assertEqual(json.loads(saved.read_text()), doc)
        self.assertEqual(set(doc["variants"]["default"]["clips"]), {"idle"})
        self.assertTrue((self.root /
                         doc["variants"]["default"]["expressions"]["portrait"]).is_file())
        self.assertEqual(reference_path(self.root, "blue_knight"),
                         self.root / "assets/character_art/blue_knight/reference.png")
        for direction in DIRECTIONS:
            image = render_frame(doc, "default", "idle", direction, 0, self.root)
            self.assertEqual(image.size, (384, 512))
            self.assertEqual(image.getchannel("A").getbbox()[3], 508)
        self.assertTrue(any(x["code"] == "missing_animation"
                            for x in diagnostics(doc)))
        with tempfile.TemporaryDirectory() as output:
            registry = export_pack(doc, self.root, Path(output))
            self.assertTrue((Path(output) / "atlas.png").is_file())
            self.assertEqual(len([
                e for e in registry["entries"] if e["kind"] == "animation"]), 4)
        with self.assertRaises(CharacterError):
            import_character_art(self.root, self.art, "blue_knight")

    def test_no_resampling_when_alignment_disabled(self):
        self.make_sources()
        doc, _ = import_character_art(
            self.root, self.art, "artist", align_feet=False)
        for direction, facing in (("south", "front"), ("east", "right"),
                                  ("north", "back"), ("west", "left")):
            actual = render_frame(doc, "default", "idle", direction, 0, self.root)
            original = Image.open(self.art / (facing + ".png")).convert("RGBA")
            self.assertEqual(actual.tobytes(), original.tobytes())

    def test_invalid_inputs_do_not_create_recipe(self):
        self.make_sources()
        (self.art / "left.png").unlink()
        with self.assertRaises(CharacterError):
            import_character_art(self.root, self.art, "incomplete")
        self.make_sources(opaque=True)
        with self.assertRaisesRegex(CharacterError, "transparent|Transparent"):
            import_character_art(self.root, self.art, "opaque")
        self.make_sources(copies=True)
        with self.assertRaisesRegex(CharacterError, "directional"):
            import_character_art(self.root, self.art, "duplicated")
        self.make_sources()
        with self.assertRaises(CharacterError):
            import_character_art(self.root, self.art, "../../escape")
        self.assertFalse((self.root / "characters/incomplete.character.json").exists())

    def test_modular_parts_require_four_192_px_pngs(self):
        self.make_sources(size=(192, 192))
        (self.root / "assets/hero_parts/hair").mkdir(parents=True)
        paths = import_part_set(
            self.root, self.art, "front_hair", "artist_fringe")
        self.assertEqual(len(paths), 4)
        self.assertIn("artist_fringe",
                      available_parts(self.root, "front_hair"))
        with self.assertRaises(CharacterError):
            import_part_set(self.root, self.art, "front_hair", "artist_fringe")
        with self.assertRaises(CharacterError):
            import_part_set(self.root, self.art, "nonsense", "artist")

    def test_reference_is_not_playable_art(self):
        concept = self.art / "concept.png"
        Image.new("RGB", (700, 500), "white").save(concept)
        path = import_reference_art(self.root, "storybook_hero", concept)
        self.assertTrue(path.is_file())
        self.assertEqual(path, reference_path(self.root, "storybook_hero"))
        self.assertIsNone(reference_path(self.root, "../../escape"))


if __name__ == "__main__":
    unittest.main()

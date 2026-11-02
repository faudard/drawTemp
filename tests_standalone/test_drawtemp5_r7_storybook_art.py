"""Original storybook art: deterministic PNGs, compatible R7 recipes."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import hashlib
import tempfile
import unittest

from drawtemp.assets.storybook_art import (
    COLLECTION, FAMILIES, DIRECTIONS, STORYBOOK_STARTERS, LOOKS,
    build, render_piece, storybook_starter,
    apply_storybook_look, available_storybook_looks, contact_sheet,
)
from drawtemp.assets.character_parts import available_parts, active_part
from drawtemp.assets.characters import CharacterSession, validate, render_frame

ROOT = Path(__file__).resolve().parents[1]


class OriginalArtTests(unittest.TestCase):
    def test_all_families_are_true_192_rgba_four_facing_art(self):
        from PIL import Image
        for slot, names in FAMILIES.items():
            self.assertGreaterEqual(len(names), 3, slot)
            for name in names:
                for direction in DIRECTIONS:
                    with self.subTest(slot=slot, name=name, facing=direction):
                        result = render_piece(slot, name, direction)
                        self.assertEqual(result.mode, "RGBA")
                        self.assertEqual(result.size, (192, 192))
                        self.assertTrue(result.getchannel("A").getbbox()
                                        or slot in ("eyes", "face")
                                        and direction == "back")
        with self.assertRaises(ValueError):
            render_piece("front_hair", "nonexistent", "front")
        with self.assertRaises(ValueError):
            render_piece("body", "child", "north")

    def test_output_is_complete_reproducible_and_non_destructive(self):
        from PIL import Image
        expected = sum(len(styles) for styles in FAMILIES.values()) * 4
        self.assertEqual(expected, 128)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(build(root), expected)
            first = {}
            for slot, styles in FAMILIES.items():
                for name in styles:
                    self.assertIn(f"{COLLECTION}_{name}",
                                  available_parts(root, slot))
                    for facing in DIRECTIONS:
                        path = (root / "assets" / "hero_parts" / slot /
                                f"{COLLECTION}_{name}_{facing}.png")
                        self.assertTrue(path.is_file())
                        first[str(path)] = hashlib.sha256(
                            path.read_bytes()).hexdigest()
            self.assertEqual(build(root), 0)
            self.assertEqual(build(root, overwrite=True), expected)
            for filename, digest in first.items():
                self.assertEqual(hashlib.sha256(
                    Path(filename).read_bytes()).hexdigest(), digest)

    def test_three_real_body_types_and_twelve_editable_looks(self):
        self.assertEqual(len(STORYBOOK_STARTERS), 3)
        self.assertEqual(len(LOOKS), 12)
        self.assertEqual(set(storybook_starter()["variants"]),
                         {"male", "female", "kid"})
        original = storybook_starter()
        for profile in STORYBOOK_STARTERS:
            self.assertEqual(len(available_storybook_looks(profile)), 4)
        for key, _, profile, changes in LOOKS:
            with self.subTest(look=key):
                session = CharacterSession(original)
                unaffected = {
                    k: deepcopy(v)
                    for k, v in original["variants"].items() if k != profile}
                clips = deepcopy(original["variants"][profile]["clips"])
                session.edit(lambda doc: apply_storybook_look(doc, profile, key))
                doc = session.document
                self.assertEqual(validate(doc), doc)
                for untouched, value in unaffected.items():
                    self.assertEqual(doc["variants"][untouched], value)
                self.assertEqual(doc["variants"][profile]["clips"], clips)
                for slot, style in changes.items():
                    layer = active_part(doc, profile, slot)
                    self.assertEqual(layer["offset"], [0, 0])
                    self.assertTrue(layer["paths"]["south"].endswith(
                        f"storybook_v1_{style}_front.png"))
                self.assertTrue(session.undo())
                self.assertEqual(session.document, original)
                self.assertTrue(session.redo())

    def test_real_runtime_composition_and_contact_sheet(self):
        # Copy the existing transparent source, which is also used by
        # original R7 idle recipes, without changing its pixels.
        from shutil import copyfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            accessory = root / "assets/hero_parts/accessory"
            accessory.mkdir(parents=True)
            for facing in DIRECTIONS:
                copyfile(ROOT / f"assets/hero_parts/accessory/none_{facing}.png",
                         accessory / f"none_{facing}.png")
            build(root)
            doc = storybook_starter()
            for profile in STORYBOOK_STARTERS:
                rendered = []
                for direction in ("south", "north", "east", "west"):
                    image = render_frame(doc, profile, "idle", direction, 0, root)
                    self.assertEqual(image.size, (192, 192))
                    self.assertIsNotNone(image.getchannel("A").getbbox())
                    rendered.append(image.tobytes())
                self.assertNotEqual(rendered[0], rendered[1])
                self.assertNotEqual(rendered[0], rendered[2])
            board = contact_sheet(root, root / "preview.png")
            self.assertTrue(board.is_file())
            from PIL import Image
            with Image.open(board) as sheet:
                self.assertGreaterEqual(sheet.width, 800)


if __name__ == "__main__":
    unittest.main()

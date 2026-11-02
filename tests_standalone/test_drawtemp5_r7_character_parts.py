"""R7 visual character-parts authoring: compatible with the canonical recipe."""
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.character_parts import (
    PART_CATEGORIES, active_part, available_parts, modular_starter,
    set_part, set_part_style,
)
from drawtemp.assets.characters import (
    CharacterError, CharacterSession, diagnostics, export_pack, render_frame,
    starter_library, validate,
)

ROOT = Path(__file__).resolve().parents[1]


class CharacterPartsTests(unittest.TestCase):
    def test_existing_categories_have_directional_variants(self):
        for slot, _ in PART_CATEGORIES:
            self.assertTrue(available_parts(ROOT, slot), slot)
        self.assertIn("classic", available_parts(ROOT, "body"))
        self.assertIn("none", available_parts(ROOT, "accessory"))
        with self.assertRaises(CharacterError):
            available_parts(ROOT, "../characters")

    def test_starter_is_pure_recipe_and_does_not_fake_combat_poses(self):
        hero = modular_starter()
        self.assertEqual(hero, starter_library()["modular_hero"])
        self.assertEqual(hero["size"], [192, 192])
        self.assertEqual(set(hero["variants"]["default"]["clips"]), {"idle"})
        self.assertEqual(set(
            hero["variants"]["default"]["clips"]["idle"]["directions"]),
            {"south", "north", "east", "west"})
        validate(hero)

    def test_selection_color_offset_undo_and_rgba_preview(self):
        session = CharacterSession(modular_starter())
        session.edit(lambda doc: set_part(doc, "default", "hair", "long", ROOT))
        layer = active_part(session.document, "default", "hair")
        self.assertEqual(set(layer["paths"]), {"south", "north", "west", "east"})
        session.edit(lambda doc: set_part_style(
            doc, "default", "hair", tint="#aabbcc",
            opacity=145, offset=[-3, 5]))
        doc = session.document
        self.assertEqual(active_part(doc, "default", "hair")["offset"], [-3, 5])
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            pass  # Pillow is optional for recipe-only standalone installs.
        else:
            for direction in ("south", "north", "east", "west"):
                rendered = render_frame(doc, "default", "idle", direction, 0, ROOT)
                self.assertEqual(rendered.size, (192, 192))
        session.edit(lambda doc: set_part(doc, "default", "hair", "bob", ROOT))
        self.assertEqual(
            active_part(session.document, "default", "hair")["tint"], "#aabbcc")
        self.assertTrue(session.undo())
        self.assertIn("long_front.png", active_part(
            session.document, "default", "hair")["paths"]["south"])
        self.assertTrue(session.redo())
        session.edit(lambda doc: set_part(doc, "default", "hair", None, ROOT))
        self.assertIsNone(active_part(session.document, "default", "hair"))

    def test_invalid_or_incompatible_parts_are_rejected(self):
        initial = modular_starter()
        for slot, name in (("hair", "../../bad"), ("not_a_slot", "classic"),
                           ("hair", "does_not_exist")):
            session = CharacterSession(initial)
            with self.assertRaises(CharacterError):
                session.edit(lambda doc: set_part(
                    doc, "default", slot, name, ROOT))
            self.assertEqual(session.document, initial)
        jeanne = starter_library()["jeanne"]
        with self.assertRaises(CharacterError):
            set_part(jeanne, "historical", "hair", "long", ROOT)

    def test_export_is_readable_by_runtime(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest("Pillow not installed")
        with tempfile.TemporaryDirectory() as tmp:
            registry = export_pack(modular_starter(), ROOT, Path(tmp))
            self.assertTrue((Path(tmp) / "atlas.png").is_file())
            self.assertEqual(len([
                x for x in registry["entries"] if x["kind"] == "animation"]), 4)


if __name__ == "__main__":
    unittest.main()

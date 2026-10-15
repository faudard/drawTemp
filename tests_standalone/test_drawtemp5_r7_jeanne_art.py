"""R7.C art/equipment gates: real distinct costumes, canonical save inputs."""
from pathlib import Path
import json
import tempfile
import unittest

from drawtemp.assets.character_outfits import outfit_from_progress
from drawtemp.assets.characters import DIRECTIONS, diagnostics, render_frame
from drawtemp.assets.jeanne_art import (
    OUTFITS, build_jeanne_art, generate_recipe, render_garment,
)
from drawtemp.assets.character_runtime import CharacterPack

ROOT = Path(__file__).resolve().parents[1]


class JeanneArtTests(unittest.TestCase):
    def test_four_directional_outfits_are_visibly_distinct_without_image_relabel(self):
        from PIL import ImageChops
        screenshots = {}
        for outfit in OUTFITS:
            for direction in DIRECTIONS:
                image = render_garment(outfit, direction)
                self.assertEqual(image.size, (64, 64))
                self.assertEqual(image.mode, "RGBA")
                self.assertIsNotNone(image.getchannel("A").getbbox())
                screenshots[(outfit, direction)] = image
        for direction in DIRECTIONS:
            for outfit in OUTFITS[1:]:
                self.assertIsNotNone(ImageChops.difference(
                    screenshots[("peasant", direction)].convert("RGB"),
                    screenshots[(outfit, direction)].convert("RGB")).getbbox())
        self.assertNotEqual(screenshots[("armor", "south")].tobytes(),
                            screenshots[("armor", "north")].tobytes())
        self.assertNotEqual(screenshots[("apprentice", "east")].tobytes(),
                            screenshots[("apprentice", "west")].tobytes())

    def test_end_to_end_art_generation_and_real_player_runtime(self):
        from PIL import ImageChops
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "jeanne_authoring"
            recipe = build_jeanne_art(ROOT, destination)
            self.assertEqual(set(recipe["variants"]), set(OUTFITS))
            self.assertFalse([p for p in diagnostics(recipe, require_outfits=True)
                              if p["severity"] == "error"])
            self.assertTrue((destination / "runtime/registry.json").is_file())
            self.assertTrue((destination / "jeanne.character.json").is_file())
            self.assertEqual(
                json.loads((destination / "jeanne.character.json").read_text("utf-8")),
                recipe)
            packed = CharacterPack(destination / "runtime")
            self.assertEqual(set(packed.variants), set(OUTFITS))
            self.assertEqual(packed.character_id, "jeanne")
            for direction in DIRECTIONS:
                for action in ("idle", "walk", "attack"):
                    for outfit in OUTFITS:
                        clip = packed.sample(variant=outfit, action=action,
                                             direction=direction, elapsed_ms=0)
                        self.assertEqual(clip["spritePivot"], [32, 63])
                        self.assertEqual(clip["spriteRegion"][2:], [64, 64])
                        self.assertTrue(clip["spriteReady"])
                base = render_frame(recipe, "peasant", "walk", direction, 0,
                                    destination)
                next_step = render_frame(recipe, "peasant", "walk", direction, 1,
                                         destination)
                self.assertIsNotNone(ImageChops.difference(
                    base, next_step).getbbox(), "Walking poses are not distinct")
                armor = render_frame(recipe, "armor", "walk", direction, 0,
                                     destination)
                self.assertIsNotNone(ImageChops.difference(
                    base, armor).getbbox(), "Armor was only renamed")
            reference = (destination / "layers/armor/south.png").read_bytes()
            build_jeanne_art(ROOT, destination)
            self.assertEqual((destination / "layers/armor/south.png").read_bytes(),
                             reference, "Second build must be reproducible")
            with self.assertRaises(ValueError):
                build_jeanne_art(ROOT, ROOT)


class CharacterEquipmentTests(unittest.TestCase):
    def setUp(self):
        self.variants = OUTFITS
        self.content_items = {
            "training_sword": {"slot": "weapon", "bonuses": {}},
            "knights_armor": {"slot": "armor", "bonuses": {}},
            "fake_armor": {"slot": "weapon", "bonuses": {}},
        }

    def outfit(self, *, inventory=None, wounds=(), available=None):
        progress = {"heroes": {"jeanne": {
            "equipment": inventory or {}, "wounds": list(wounds)}}}
        return outfit_from_progress(progress, self.content_items, "jeanne",
                                    available or self.variants)

    def test_peasant_training_armored_wounded_equipment_path(self):
        self.assertEqual(self.outfit(), "peasant")
        self.assertEqual(self.outfit(inventory={"weapon": "training_sword"}), "apprentice")
        self.assertEqual(self.outfit(inventory={"armor": "knights_armor"}), "armor")
        self.assertEqual(self.outfit(inventory={
            "weapon": "training_sword", "armor": "knights_armor"}), "armor")
        self.assertEqual(self.outfit(inventory={"armor": "knights_armor"},
                                     wounds=["arm_injury"]), "wounded")

    def test_only_canonical_equipment_slot_unlocks_costume(self):
        self.assertEqual(self.outfit(inventory={"armor": "fake_armor"}), "peasant")
        self.assertEqual(self.outfit(inventory={"armor": "missing"}), "peasant")
        self.assertEqual(self.outfit(inventory={"weapon": "knights_armor"}), "peasant")
        self.assertEqual(self.outfit(available=("historical",)), "historical")
        self.assertEqual(self.outfit(available=("armor", "peasant")), "peasant")


if __name__ == "__main__":
    unittest.main()

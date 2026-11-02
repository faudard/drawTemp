"""R7 visual character-parts authoring: compatible with the canonical recipe."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.character_parts import (
    PART_CATEGORIES, PROFILE_PRESETS, PROFILE_PARTS, active_part,
    available_parts, ensure_profile, modular_starter, part_paths,
    set_part, set_part_style, upgrade_legacy_hair,
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
        for slot in ("front_hair", "rear_hair"):
            self.assertIn("braids", available_parts(ROOT, slot))
            self.assertEqual(set(part_paths(slot, "braids", ROOT)),
                             {"south", "north", "west", "east"})
        with self.assertRaises(CharacterError):
            available_parts(ROOT, "../characters")

    def test_starter_is_pure_recipe_and_does_not_fake_combat_poses(self):
        hero = modular_starter()
        self.assertEqual(hero, starter_library()["modular_hero"])
        self.assertEqual(hero["size"], [192, 192])
        self.assertEqual(set(hero["variants"]), set(PROFILE_PRESETS))
        for profile in PROFILE_PRESETS:
            self.assertEqual(set(hero["variants"][profile]["clips"]), {"idle"})
            self.assertEqual(set(
                hero["variants"][profile]["clips"]["idle"]["directions"]),
                {"south", "north", "east", "west"})
        validate(hero)

    def test_presets_use_real_variants_and_remain_independent(self):
        session = CharacterSession(modular_starter())
        self.assertEqual(tuple(session.document["variants"]), PROFILE_PRESETS)
        for profile in PROFILE_PRESETS:
            appearance = session.document["variants"][profile]
            self.assertEqual({x["slot"] for x in appearance["layers"]},
                             set(PROFILE_PARTS[profile]))
            for layer in appearance["layers"]:
                parts = available_parts(ROOT, layer["slot"])
                source = Path(layer["paths"]["south"]).stem
                self.assertIn(source[:-len("_front")], parts)
                for path in layer["paths"].values():
                    self.assertTrue((ROOT / path).is_file())
        initial = session.document
        session.edit(lambda doc: set_part(
            doc, "female", "front_hair", "mohawk", ROOT))
        session.edit(lambda doc: set_part_style(
            doc, "kid", "rear_hair", offset=[7, -4], tint="#bbaa77"))
        self.assertEqual(session.document["variants"]["male"],
                         initial["variants"]["male"])
        self.assertEqual(active_part(session.document, "kid", "rear_hair")["offset"],
                         [7, -4])
        self.assertTrue(session.undo())
        self.assertEqual(session.document["variants"]["kid"],
                         initial["variants"]["kid"])
        self.assertTrue(session.redo())
        roundtrip = json.loads(json.dumps(session.document))
        self.assertEqual(validate(roundtrip), session.document)

    def test_old_modular_recipe_can_add_profiles_without_losing_default(self):
        doc = modular_starter()
        old = deepcopy(doc["variants"]["male"])
        old["name"] = "My earlier custom character"
        doc["variants"] = {"default": old}
        session = CharacterSession(doc)
        session.edit(lambda current: ensure_profile(current, "kid"))
        self.assertEqual(session.document["variants"]["default"], old)
        self.assertIn("kid", session.document["variants"])
        self.assertNotIn("female", session.document["variants"])
        with self.assertRaises(CharacterError):
            session.edit(lambda current: ensure_profile(current, "kid"))
        self.assertTrue(session.undo())
        self.assertEqual(session.document["variants"], {"default": old})
        with self.assertRaises(CharacterError):
            ensure_profile(starter_library()["jeanne"], "female")

    def test_selection_color_offset_undo_and_rgba_preview(self):
        session = CharacterSession(modular_starter())
        session.edit(lambda doc: set_part(
            doc, "male", "front_hair", "long", ROOT))
        layer = active_part(session.document, "male", "front_hair")
        self.assertEqual(set(layer["paths"]), {"south", "north", "west", "east"})
        original_rear = deepcopy(
            active_part(session.document, "male", "rear_hair"))
        session.edit(lambda doc: set_part_style(
            doc, "male", "front_hair", tint="#aabbcc",
            opacity=145, offset=[-3, 5]))
        doc = session.document
        self.assertEqual(active_part(doc, "male", "front_hair")["offset"], [-3, 5])
        self.assertEqual(active_part(doc, "male", "rear_hair"), original_rear)
        self.assertLess(
            [x["slot"] for x in doc["variants"]["male"]["layers"]].index("rear_hair"),
            [x["slot"] for x in doc["variants"]["male"]["layers"]].index("head_shape"))
        self.assertGreater(
            [x["slot"] for x in doc["variants"]["male"]["layers"]].index("front_hair"),
            [x["slot"] for x in doc["variants"]["male"]["layers"]].index("eyes"))
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            pass  # Pillow is optional for recipe-only standalone installs.
        else:
            for direction in ("south", "north", "east", "west"):
                rendered = render_frame(doc, "male", "idle", direction, 0, ROOT)
                self.assertEqual(rendered.size, (192, 192))
        session.edit(lambda doc: set_part(doc, "male", "front_hair", "bob", ROOT))
        self.assertEqual(
            active_part(session.document, "male", "front_hair")["tint"], "#aabbcc")
        self.assertTrue(session.undo())
        self.assertIn("long_front.png", active_part(
            session.document, "male", "front_hair")["paths"]["south"])
        self.assertTrue(session.redo())
        session.edit(lambda doc: set_part(doc, "male", "front_hair", None, ROOT))
        self.assertIsNone(active_part(session.document, "male", "front_hair"))
        self.assertEqual(
            active_part(session.document, "male", "rear_hair"), original_rear)

    def test_legacy_split_is_explicit_undoable_and_retains_styles(self):
        doc = modular_starter()
        layers = doc["variants"]["male"]["layers"]
        layers[:] = [layer for layer in layers
                     if layer["slot"] not in ("front_hair", "rear_hair")]
        layers.append({
            "slot": "hair", "paths": part_paths("hair", "braids", ROOT),
            "offset": [5, -6], "tint": "#aabbcc", "opacity": 103,
        })
        session = CharacterSession(doc)
        untouched = deepcopy(session.document)
        session.edit(lambda recipe: upgrade_legacy_hair(recipe, "male", ROOT))
        self.assertIsNone(active_part(session.document, "male", "hair"))
        for slot in ("front_hair", "rear_hair"):
            part = active_part(session.document, "male", slot)
            self.assertEqual(part["offset"], [5, -6])
            self.assertEqual(part["tint"], "#aabbcc")
            self.assertEqual(part["opacity"], 103)
            self.assertIn("braids_front.png", part["paths"]["south"])
        self.assertTrue(session.undo())
        self.assertEqual(session.document, untouched)
        self.assertTrue(session.redo())
        self.assertEqual(validate(session.document), session.document)
        with self.assertRaises(CharacterError):
            session.edit(lambda recipe: upgrade_legacy_hair(recipe, "male", ROOT))

    def test_legacy_front_fringe_mask_does_not_modify_original(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not available")
        from drawtemp.assets.character_parts import split_legacy_hair_front
        source_path = ROOT / "assets/hero_parts/hair/braids_front.png"
        with Image.open(source_path) as source:
            original = source.convert("RGBA")
        before = original.tobytes()
        fringe = split_legacy_hair_front(original)
        self.assertEqual(original.tobytes(), before)
        self.assertEqual(fringe.size, original.size)
        self.assertNotEqual(fringe.getchannel("A").tobytes(),
                            original.getchannel("A").tobytes())

    def test_invalid_or_incompatible_parts_are_rejected(self):
        initial = modular_starter()
        for slot, name in (("hair", "../../bad"), ("not_a_slot", "classic"),
                           ("hair", "does_not_exist")):
            session = CharacterSession(initial)
            with self.assertRaises(CharacterError):
                session.edit(lambda doc: set_part(
                    doc, "male", slot, name, ROOT))
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
                x for x in registry["entries"] if x["kind"] == "animation"]), 12)
            self.assertTrue(any(x["code"] == "missing_animation" for x in
                                json.loads((Path(tmp) / "character.json").read_text(
                                    encoding="utf-8"))["diagnostics"]))
            with self.assertRaises(CharacterError):
                export_pack(modular_starter(), ROOT,
                            Path(tmp) / "strict", strict=True)


if __name__ == "__main__":
    unittest.main()

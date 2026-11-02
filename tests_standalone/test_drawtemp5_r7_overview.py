"""R7 overview: scalable library and actual editable look recipes."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.character_library import (
    discover_character_library, search_characters,
)
from drawtemp.assets.character_looks import (
    DEFAULT_OFFSETS, LOOKS, available_looks, apply_look,
)
from drawtemp.assets.character_parts import (
    PROFILE_PRESETS, modular_starter, active_part,
)
from drawtemp.assets.characters import (
    CharacterError, CharacterSession, starter_library, validate,
)

ROOT = Path(__file__).resolve().parents[1]


class CharacterOverviewTests(unittest.TestCase):
    def test_15_looks_use_real_art_and_preserve_other_profiles(self):
        self.assertEqual(len(available_looks()), 15)
        for profile in PROFILE_PRESETS:
            self.assertEqual(len(available_looks(profile)), 5)
        for look_id, label, profile, changes in LOOKS:
            with self.subTest(look=look_id):
                original = modular_starter()
                other_variants = {
                    key: deepcopy(value)
                    for key, value in original["variants"].items()
                    if key != profile
                }
                animation = deepcopy(original["variants"][profile]["clips"])
                session = CharacterSession(original)
                session.edit(lambda doc: apply_look(doc, profile, look_id, ROOT))
                doc = session.document
                self.assertEqual(validate(doc), doc)
                self.assertEqual(doc["variants"][profile]["clips"], animation)
                for key, value in other_variants.items():
                    self.assertEqual(doc["variants"][key], value)
                for slot, name in changes.items():
                    layer = active_part(doc, profile, slot)
                    self.assertIsNotNone(layer, (slot, label))
                    self.assertTrue(layer["paths"]["south"].endswith(
                        name + "_front.png"))
                    self.assertEqual(
                        layer["offset"], DEFAULT_OFFSETS.get(slot, [0, 0]))
                    for image in layer["paths"].values():
                        self.assertTrue((ROOT / image).is_file())
                self.assertTrue(session.undo())
                self.assertEqual(session.document, original)
                self.assertTrue(session.redo())
                self.assertEqual(session.document, doc)

    def test_look_rejects_incompatible_and_unknown_ids(self):
        modular = modular_starter()
        invalid_id = deepcopy(modular)
        with self.assertRaises(CharacterError):
            apply_look(invalid_id, "male", "made_up", ROOT)
        self.assertEqual(invalid_id, modular)
        jeanne = starter_library()["jeanne"]
        with self.assertRaises(CharacterError):
            apply_look(jeanne, "historical", "male_guard", ROOT)

    def test_library_search_and_project_owned_recipes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "assets/characters"
            path.mkdir(parents=True)
            recipe = modular_starter()
            recipe["name"] = "Forest Archer"
            (path / "forest.character.json").write_text(
                json.dumps(recipe), encoding="utf-8")
            (path / "bad.character.json").write_text(
                "not JSON", encoding="utf-8")
            library = discover_character_library(
                root, {"modular_hero": modular_starter()})
            self.assertEqual(len(library), 2)
            self.assertIn("file:assets/characters/forest.character.json", library)
            self.assertEqual(len(search_characters(library, "FOREST")), 1)
            self.assertEqual(len(search_characters(library, "character missing")), 0)
            self.assertEqual(len(search_characters(library, "")), 2)
            self.assertEqual(library["starter:modular_hero"][1],
                             modular_starter())


if __name__ == "__main__":
    unittest.main()

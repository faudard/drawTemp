"""DrawTemp 5.0 R7: character authoring, asset compatibility and QA."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.characters import (
    DIRECTIONS, CharacterError, CharacterSession, atlas_variant, diagnostics,
    export_pack, frame, render_frame, starter_library, validate,
)
from sporebound.assets import AssetRegistry


ROOT = Path(__file__).resolve().parents[1]


def small_character():
    sample = frame("source.png", duration_ms=100)
    variant = {
        "name": "Jeanne — villageoise",
        "clips": {action: {"loop": action != "attack",
                            "directions": {direction: [deepcopy(sample), deepcopy(sample)]
                                           for direction in DIRECTIONS}}
                  for action in ("idle", "walk", "attack")},
        "layers": [], "expressions": {},
    }
    armor = deepcopy(variant)
    armor["name"] = "Jeanne — armure"
    armor["layers"] = [{
        "slot": "clothing", "paths": {d: "armor.png" for d in DIRECTIONS},
        "offset": [0, 0], "tint": "#ffffff", "opacity": 255,
    }]
    return {
        "version": 1, "id": "jeanne", "name": "Jeanne",
        "size": [4, 4], "pivot": [2, 3],
        "variants": {"peasant": variant, "armor": armor},
    }


class CharacterRecipeTests(unittest.TestCase):
    def test_packaged_jeanne_uses_four_real_atlas_directions(self):
        library = starter_library()
        self.assertEqual(set(library), {"jeanne", "villager", "knight", "archer",
                                        "wolf", "spearman", "ogre"})
        self.assertIn("missing_animation", {x["code"] for x in diagnostics(library["wolf"])})
        jeanne = library["jeanne"]
        self.assertEqual(jeanne["pivot"], [32, 63])
        for action in ("idle", "walk", "attack", "hit", "death"):
            clip = jeanne["variants"]["historical"]["clips"][action]
            self.assertEqual(set(clip["directions"]), set(DIRECTIONS))
            for direction in DIRECTIONS:
                for pose in clip["directions"][direction]:
                    self.assertEqual(pose["region"][2:], [64, 64])
                    self.assertTrue((ROOT / pose["path"]).is_file())
        self.assertTrue(any(i["code"] == "missing_outfit"
                            for i in diagnostics(jeanne, require_outfits=True)))

    def test_bad_asset_paths_and_schema_are_rejected(self):
        sample = small_character()
        for bad in ("../private.png", "/etc/private.png", "C:/abc.png",
                    "source.gif", "dir\\evil.png", "aux.png"):
            doc = deepcopy(sample)
            doc["variants"]["peasant"]["clips"]["walk"]\
               ["directions"]["north"][0]["path"] = bad
            with self.subTest(path=bad), self.assertRaises(CharacterError):
                validate(doc)
        doc = deepcopy(sample)
        doc["variants"]["peasant"]["layers"] = [{
            "slot": "eyes", "paths": {"northeast": "source.png"},
            "offset": [0, 0], "tint": "#ffffff", "opacity": 255,
        }]
        with self.assertRaises(CharacterError):
            validate(doc)
        doc = deepcopy(sample)
        doc["variants"]["peasant"]["clips"]["attack"]\
           ["directions"]["east"][0]["duration_ms"] = 0
        with self.assertRaises(CharacterError):
            validate(doc)

    def test_sessions_are_copy_on_write_and_reject_stale_or_foreign_previews(self):
        original = small_character()
        first = CharacterSession(original)
        preview = first.preview(lambda doc: doc.update(name="Jeanne (edited)"))
        second = CharacterSession(original)
        with self.assertRaises(CharacterError):
            second.commit(preview)
        first.commit(preview)
        self.assertEqual(original["name"], "Jeanne")
        self.assertTrue(first.undo())
        # ABA: reverting visual content does not reinstate an earlier revision.
        with self.assertRaises(CharacterError):
            first.commit(preview)
        self.assertTrue(first.redo())
        self.assertEqual(first.document["name"], "Jeanne (edited)")
        first.edit(lambda doc: doc.update(name="Jeanne 2"))
        self.assertFalse(first.redo())
        detached = first.document
        detached["name"] = "Mutation"
        self.assertEqual(first.document["name"], "Jeanne 2")

    def test_art_qa_does_not_call_different_names_different_outfits(self):
        doc = small_character()
        self.assertFalse([i for i in diagnostics(doc, require_outfits=True)
                          if i["severity"] == "error"])
        doc["variants"]["armor"]["layers"].clear()
        self.assertIn("identical_outfits",
                      {i["code"] for i in diagnostics(doc, require_outfits=True)})
        del doc["variants"]["peasant"]["clips"]["attack"]["directions"]["north"]
        self.assertIn("missing_animation",
                      {i["code"] for i in diagnostics(doc, require_outfits=True)})

    def test_exports_a_registry_v1_with_distinct_outfits_and_frame_timings(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow optional; R7 CI installs art extra")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = Image.new("RGBA", (4, 4), (180, 95, 44, 255))
            image.save(root / "source.png")
            armor = Image.new("RGBA", (4, 4), (0, 0, 255, 64))
            armor.save(root / "armor.png")
            recipe = small_character()
            source_before = (root / "source.png").read_bytes()
            registry = export_pack(recipe, root, root / "pack", strict=True)
            packaged = AssetRegistry(json.loads(
                (root / "pack" / "registry.json").read_text(encoding="utf-8")))
            self.assertEqual(packaged.to_dict(), registry)
            self.assertFalse(packaged.diagnostics(root / "pack"))
            self.assertTrue((root / "pack" / "atlas.png").is_file())
            self.assertTrue((root / "pack" / "character.json").is_file())
            self.assertEqual((root / "source.png").read_bytes(), source_before)
            self.assertEqual(len(registry["bindings"]["animation"]), 24)
            self.assertEqual(len([r for r in registry["entries"]
                                  if r["kind"] == "sprite"]), 48)
            south_peasant = render_frame(recipe, "peasant", "walk", "south", 0, root)
            south_armor = render_frame(recipe, "armor", "walk", "south", 0, root)
            self.assertNotEqual(south_peasant.tobytes(), south_armor.tobytes())
            for entry in registry["entries"]:
                if entry["kind"] == "animation":
                    self.assertEqual([f["duration_ms"] for f in entry["frames"]],
                                     [100, 100])
            # Rebuilding the same atlas cannot change its bytes.
            baseline = (root / "pack" / "atlas.png").read_bytes()
            export_pack(recipe, root, root / "pack", strict=True)
            self.assertEqual((root / "pack" / "atlas.png").read_bytes(), baseline)

    def test_atlas_regions_qa_and_overwrite_protection(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow optional; R7 CI installs art extra")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new("RGBA", (3, 4)).save(root / "source.png")
            Image.new("RGBA", (4, 4)).save(root / "armor.png")
            with self.assertRaises(CharacterError):
                export_pack(small_character(), root, root / "out", strict=True)
            Image.new("RGBA", (4, 4)).save(root / "source.png")
            with self.assertRaises(CharacterError):
                export_pack(small_character(), root, root, strict=True)
            invalid = small_character()
            invalid["variants"]["peasant"]["clips"]["idle"]\
                   ["directions"]["west"][0]["region"] = [4, 0, 4, 4]
            with self.assertRaises(CharacterError):
                export_pack(invalid, root, root / "out", strict=True)


if __name__ == "__main__":
    unittest.main()

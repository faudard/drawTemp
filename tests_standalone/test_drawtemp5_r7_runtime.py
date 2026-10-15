"""R7 stage 2: published sprite packs remain compatible with shared R3/R12."""
import json
from pathlib import Path
import tempfile
import unittest

from drawtemp.assets.characters import CharacterError, export_pack, starter_library
from drawtemp.assets.character_runtime import CharacterPack
from drawtemp.render.iso_scene import Camera, IsoProjection, render_items, scene_from_mission
from drawtemp.sdk.reference import MISSION, reference_project


ROOT = Path(__file__).resolve().parents[1]


class CharacterRuntimeTests(unittest.TestCase):
    def test_jeanne_export_resolves_four_way_frames_and_timing(self):
        try:
            import PIL
        except ImportError:
            self.skipTest("Pillow optional for authoring; installed by R7 CI")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            export_pack(starter_library()["jeanne"], ROOT, path)
            runtime = CharacterPack(path)
            self.assertEqual(runtime.character_id, "jeanne")
            self.assertEqual(runtime.pivot, (32, 63))
            self.assertEqual(runtime.variants, ("historical",))
            for direction in ("south", "north", "east", "west"):
                first = runtime.preview_actor("jeanne", variant="historical",
                                              action="walk", direction=direction,
                                              elapsed_ms=0)
                second = runtime.preview_actor("jeanne", variant="historical",
                                               action="walk", direction=direction,
                                               elapsed_ms=180)
                self.assertTrue(first["spriteReady"])
                self.assertEqual(first["spriteRegion"][2:], [64, 64])
                self.assertNotEqual(first["spriteRegion"], second["spriteRegion"])
                self.assertEqual(
                    first, runtime.preview_actor("jeanne", variant="historical",
                                                 action="walk", direction=direction,
                                                 elapsed_ms=360))
                self.assertTrue(first["spriteUrl"].startswith("file:"))
            self.assertIsNone(runtime.preview_actor("unknown"))
            self.assertIsNone(runtime.preview_actor("jeanne", direction="diagonal"))
            self.assertEqual(runtime.duration("historical", "walk", "south"), 360)
            self.assertEqual(runtime.duration("historical", "run", "south"), 0)
            # End-of-action frames are held, never wrapped.
            last = runtime.preview_actor("jeanne", action="attack", elapsed_ms=999999)
            before = runtime.preview_actor("jeanne", action="attack", elapsed_ms=140)
            self.assertEqual(last, before)
            # Action missing: keep the same direction in idle, no fake mirrored art.
            self.assertEqual(
                runtime.preview_actor("jeanne", action="magic", direction="north"),
                runtime.preview_actor("jeanne", action="idle", direction="north"))

    def test_pack_is_read_only_and_rejects_corrupted_paths(self):
        try:
            import PIL
        except ImportError:
            self.skipTest("Pillow not installed")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            export_pack(starter_library()["jeanne"], ROOT, root)
            before = sorted((str(path.relative_to(root)), path.read_bytes())
                            for path in root.iterdir() if path.is_file())
            CharacterPack(root).sample(variant="historical", action="idle",
                                       direction="west", elapsed_ms=300)
            after = sorted((str(path.relative_to(root)), path.read_bytes())
                           for path in root.iterdir() if path.is_file())
            self.assertEqual(before, after)
            meta_path = root / "character.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["pivot"] = [10000, 10000]
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            with self.assertRaises(CharacterError):
                CharacterPack(root)
            meta["pivot"] = [32, 63]
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            registry_path = root / "registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            next(x for x in registry["entries"] if x["kind"] == "sprite")["path"] = "../escape.png"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaises(ValueError):
                CharacterPack(root)

    def test_shared_scene_projection_retains_direction_without_gameplay_changes(self):
        content, _ = reference_project()
        scene = scene_from_mission(content.missions[MISSION])
        for actor in scene["actors"]:
            self.assertIn(actor["direction"], ("south", "north", "east", "west"))
        original = json.dumps(scene, sort_keys=True)
        camera = Camera()
        rows = render_items(scene, camera, IsoProjection())
        self.assertTrue(rows)
        for row in rows:
            if row["kind"] == "actor":
                self.assertIn(row["direction"], ("south", "north", "east", "west"))
        self.assertEqual(json.dumps(scene, sort_keys=True), original)


if __name__ == "__main__":
    unittest.main()

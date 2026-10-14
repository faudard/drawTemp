"""Regression tests for the derived wolf animation kit."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_wolf_animation_kit import CLIPS, SOURCE_NAMES, build


class WolfKitTests(unittest.TestCase):
    def test_clip_contract(self):
        self.assertGreaterEqual(len(CLIPS), 10)
        for key, (loop, frames) in CLIPS.items():
            self.assertIsInstance(loop, bool)
            self.assertTrue(frames, key)
            for pose, ms, x, y, scale in frames:
                self.assertIn(pose, SOURCE_NAMES)
                self.assertGreater(ms, 0)
                self.assertGreater(scale, .9)
                self.assertLess(scale, 1.1)

    def test_generates_playable_registry_and_unique_frames(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is an optional authoring dependency")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            for pose in SOURCE_NAMES:
                image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
                for x in range(30, 65):
                    for y in range(25, 75):
                        image.putpixel((x, y), (110, 100, 91, 255))
                image.save(source / f"{pose}.png")
            count, clips = build(source, output)
            registry = json.loads((output / "registry.json").read_text())
            kit = json.loads((output / "kit.json").read_text())
            sprites = [e for e in registry["entries"] if e["kind"] == "sprite"]
            animations = [e for e in registry["entries"] if e["kind"] == "animation"]
            self.assertEqual(count, len(registry["entries"]))
            self.assertEqual(clips, len(CLIPS))
            self.assertEqual(len(animations), clips)
            self.assertEqual(len(sprites), sum(len(p) for _, p in CLIPS.values()))
            self.assertEqual(len({s["id"] for s in sprites}), len(sprites))
            self.assertEqual(kit["frame_count"], len(sprites))
            ids = {s["id"] for s in sprites}
            for sprite in sprites:
                with Image.open(output / sprite["path"]) as image:
                    self.assertEqual(image.size, (96, 96))
                    self.assertEqual(image.mode, "RGBA")
            for clip in animations:
                self.assertTrue(clip["frames"])
                self.assertTrue(all(f["sprite"] in ids for f in clip["frames"]))
            self.assertTrue((source / "idle.png").exists())

    def test_reject_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                build(Path(tmp), Path(tmp) / "output")


if __name__ == "__main__":
    unittest.main()

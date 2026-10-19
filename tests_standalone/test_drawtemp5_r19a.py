"""R19.A art checks use authored synthetic images, never a release certificate."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from drawtemp.assets.art_gate import audit_character, audit_watercolor_rights
from drawtemp.assets.characters import ACTIONS, DIRECTIONS, frame

try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipUnless(Image is not None, "Requires Pillow art extra")
class R19AnimationGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        clips = {}
        for ai, action in enumerate(ACTIONS):
            directions = {}
            for di, direction in enumerate(DIRECTIONS):
                frames = []
                for fi in range(2):
                    relative = f"art/{action}_{direction}_{fi}.png"
                    target = self.root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    image = Image.new("RGBA", (8, 8),
                                      ((ai * 23 + 9) % 255,
                                       (di * 61 + 8) % 255, fi * 101 + 10, 255))
                    image.save(target)
                    frames.append(frame(relative, duration_ms=120))
                directions[direction] = frames
            clips[action] = {"loop": action in ("idle", "walk", "run"),
                             "directions": directions}
        self.recipe = {
            "version": 1, "id": "hero", "name": "Hero",
            "size": [8, 8], "pivot": [4, 7],
            "variants": {"original": {"name": "Original", "clips": clips,
                                      "layers": [], "expressions": {}}},
        }

    @staticmethod
    def codes(result):
        return {item["code"] for item in result["issues"]}

    def test_full_distinct_character(self):
        result = audit_character(self.recipe, self.root)
        self.assertEqual(result["status"], "passed_structural_pixel", result["issues"])
        self.assertEqual(result["frames_checked"], 72)
        self.assertEqual(result["human_art_approval"], "not_assessed")
        self.assertEqual(result["redistribution_rights"], "not_assessed")

    def test_missing_action_fails(self):
        del self.recipe["variants"]["original"]["clips"]["magic"]
        self.assertIn("missing_action", self.codes(audit_character(self.recipe, self.root)))

    def test_recycled_action_and_direction_fail(self):
        clips = self.recipe["variants"]["original"]["clips"]
        clips["run"]["directions"]["south"] = list(clips["walk"]["directions"]["south"])
        clips["run"]["directions"]["north"] = list(clips["run"]["directions"]["south"])
        report = audit_character(self.recipe, self.root)
        self.assertIn("recycled_action", self.codes(report))
        self.assertIn("recycled_direction", self.codes(report))

    def test_static_or_same_pixels_fail(self):
        clips = self.recipe["variants"]["original"]["clips"]
        frames = clips["attack"]["directions"]["east"]
        frames[1]["path"] = frames[0]["path"]
        clips["block"]["directions"]["west"] = clips["block"]["directions"]["west"][:1]
        report = audit_character(self.recipe, self.root)
        self.assertIn("duplicate_pixels", self.codes(report))
        self.assertIn("static_clip", self.codes(report))

    def test_path_escape_region_and_symlink_fail(self):
        sample = self.recipe["variants"]["original"]["clips"]["idle"]["directions"]["south"][0]
        sample["path"] = "../outside.png"
        self.assertIn("invalid_frame", self.codes(audit_character(self.recipe, self.root)))
        sample["path"] = "art/idle_south_0.png"
        sample["region"] = [3, 3, 8, 8]
        self.assertIn("invalid_frame", self.codes(audit_character(self.recipe, self.root)))
        sample["region"] = None
        target = self.root / sample["path"]
        target.unlink()
        with tempfile.TemporaryDirectory() as external:
            other = Path(external) / "other.png"
            Image.new("RGBA", (8, 8)).save(other)
            try:
                target.symlink_to(other)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            self.assertIn("invalid_frame", self.codes(audit_character(self.recipe, self.root)))

    def test_cli_report(self):
        path = self.root / "hero.character.json"
        path.write_text(json.dumps(self.recipe), encoding="utf-8")
        report = self.root / "audit.json"
        proc = subprocess.run([
            sys.executable, "-m", "drawtemp.assets.art_gate",
            "--recipe", str(path), "--project-root", str(self.root),
            "--report", str(report)],
            capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(report.read_text())["status"],
                         "passed_structural_pixel")
        self.assertEqual(json.loads(proc.stdout)["studio_player_parity"], "not_assessed")

    def test_animations_never_grant_rights(self):
        self.assertEqual(audit_character(self.recipe, self.root)["status"],
                         "passed_structural_pixel")
        self.assertEqual(audit_watercolor_rights(self.root)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()

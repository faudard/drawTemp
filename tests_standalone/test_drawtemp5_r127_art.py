"""R12.7 art contract: certified Jeanne atlas through canonical R4 resolver.

These tests intentionally use the packaged, already-approved art/manifest,
not test-generated sprites or fake Qt assets.
"""
from importlib.resources import files
from pathlib import Path
import unittest

from drawtemp.assets.runtime import PresentationAssets
from drawtemp.core import Content, GameProject
from drawtemp.player.qt_app import build_controller
from drawtemp.render.iso_scene import scene_from_exploration


class R127ArtContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = files("sporebound").joinpath("content")
        cls.content = Content.load(folder.joinpath("jeanne.json"))
        cls.project = GameProject.load(folder.joinpath("jeanne.game.json"), cls.content)
        cls.assets = PresentationAssets.for_project(
            cls.project, Path(str(folder.joinpath("jeanne.game.json"))))

    def test_real_jeanne_atlas_bindings_for_all_four_directions(self):
        for direction in ("south", "north", "east", "west"):
            for pose, milliseconds, expected_row in (
                    ("idle", 0, "idle_0"), ("idle", 310, "idle_1"),
                    ("move", 0, "move_0"), ("move", 180, "move_1"),
                    ("attack", 0, "attack_0"), ("attack", 180, "attack_1"),
                    ("hit", 0, "hit_0")):
                with self.subTest(direction=direction, pose=pose,
                                  frame=expected_row):
                    frame = self.assets.actor_frame(
                        "jeanne", direction=direction, pose=pose,
                        elapsed_ms=milliseconds)
                    self.assertEqual(frame["assetId"],
                                     f"jeanne_{direction}_{expected_row}")
                    self.assertEqual((frame["frameWidth"], frame["frameHeight"]),
                                     (64, 64))
                    self.assertTrue(Path(frame["imageUrl"].removeprefix("file://")).is_file())
                    self.assertEqual(frame["pivotX"], 32)
                    self.assertEqual(frame["pivotY"], 64)
        self.assertTrue(self.assets.has_animations)

    def test_no_unsupported_pose_art_is_invented(self):
        self.assertIsNone(self.assets.actor_frame("unbound_npc", pose="attack"))
        # The known actor falls back to idle for optional non-authored poses.
        self.assertEqual(
            self.assets.actor_frame("jeanne", direction="north", pose="dance")["assetId"],
            "jeanne_north_idle_0",
        )

    def test_idle_renderer_receives_atlas_without_gameplay_changes(self):
        game = build_controller(reference=False)
        game.new_game()
        stage = game.session.snapshot()
        assert stage.exploration is not None
        scene = scene_from_exploration(stage.exploration, revision=stage.revision)
        rows = [
            {"kind": "actor", "id": "jeanne", "team": "player",
             "direction": "south", "pose": "idle", "x": 1, "y": 5},
            {"kind": "actor", "id": "unknown_enemy", "team": "enemy", "x": 2, "y": 5},
        ]
        before = game.session.recording()
        resolved = self.assets.decorate(rows, elapsed_ms=0)
        self.assertEqual(resolved[0]["assetId"], "jeanne_south_idle_0")
        self.assertFalse("imageUrl" in resolved[1])
        resolved = self.assets.decorate(rows, elapsed_ms=330)
        self.assertEqual(resolved[0]["assetId"], "jeanne_south_idle_1")
        self.assertEqual(before, game.session.recording())
        self.assertEqual(scene["actors"][0]["id"], "jeanne")


if __name__ == "__main__":
    unittest.main()

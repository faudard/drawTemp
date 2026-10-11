"""3.7.5: four-direction Jeanne atlas is portable, deterministic and headless."""
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy

from sporebound.assets import AssetRegistry
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.visual_motion import animation_sprite_id


CONTENT = Path(__file__).resolve().parents[1] / "sporebound" / "content"


class JeanneArtGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT / "jeanne.json")
        cls.project = GameProject.load(CONTENT / "jeanne.game.json", cls.content)
        cls.registry = cls.project.asset_registry()

    def test_gated_files_resolve_and_have_valid_regions(self):
        self.assertEqual(self.registry.diagnostics(CONTENT), [])
        atlas = CONTENT / "art/jeanne/jeanne_atlas.png"
        portrait = CONTENT / "art/jeanne/jeanne_portrait.png"
        for path, dimensions in ((atlas, (256, 512)), (portrait, (64, 64))):
            data = path.read_bytes()[:24]
            self.assertEqual(data[:8], bytes((137, 80, 78, 71, 13, 10, 26, 10)))
            self.assertEqual(struct.unpack(">II", data[16:24]), dimensions)

    def test_all_directions_and_actions_bind_without_display(self):
        for direction in ("south", "north", "east", "west"):
            for action in ("idle", "move", "attack", "hit", "defeat"):
                name = f"jeanne_{action}_{direction}"
                spec = self.registry.binding("animation", name)
                self.assertIsNotNone(spec, name)
                self.assertEqual(
                    animation_sprite_id(self.registry, "jeanne", "player",
                                        action, direction, 0), spec["frames"][0]["sprite"])
                for frame in spec["frames"]:
                    entry = self.registry.require_reference(frame["sprite"], "sprite")
                    self.assertEqual(entry["region"][2:], [64, 64])
        self.assertIsNotNone(self.registry.binding("portrait", "Jeanne"))
        self.assertEqual(self.registry.binding("sprite", "jeanne")["id"],
                         "jeanne_south_idle_0")

    def test_act_one_story_survives_atlas_integration(self):
        scenes = {scene["id"] for scene in self.project.story["scenes"]}
        self.assertIn("sc_a1_camp", scenes)
        self.assertIn("sc_a1_fin", scenes)
        self.assertIn("a1_05_vaucouleurs", self.content.missions)
        self.assertIn("a1_05_vaucouleurs", self.project.story["after_mission"])
        self.assertTrue(self.project.battle_support)
        self.assertGreaterEqual(len(self.registry.to_dict()["entries"]), 50)

    def test_no_asset_dependency_on_tactical_engine(self):
        from sporebound.game_session import GameSession
        session = GameSession.new(self.content, self.project, "jeanne")
        # The authored introduction still starts in exploration; art is cosmetic.
        self.assertEqual(session.active_scene()["id"], "sc_p0_champs")
        self.assertIsNone(session.active_battle)

    def test_invalid_region_rejected_before_renderer(self):
        base = {"version": 1, "entries": [
            {"id": "a", "kind": "sprite", "path": "atlas.png", "region": [0, 0, 64, 64]}],
            "bindings": {}}
        for region in ([0, 0, 0, 64], [0, 0, -1, 64], [0, 0, True, 64],
                       [0, 0, 64], "0,0,64,64"):
            data = deepcopy(base)
            data["entries"][0]["region"] = region
            with self.subTest(region=region), self.assertRaises(RuleError):
                AssetRegistry(data)
        with TemporaryDirectory() as folder:
            data = deepcopy(base)
            data["entries"][0]["path"] = "art.png"
            data["entries"][0]["region"] = [250, 500, 64, 64]
            (Path(folder) / "art.png").write_bytes(
                (CONTENT / "art/jeanne/jeanne_atlas.png").read_bytes())
            issues = AssetRegistry(data).diagnostics(Path(folder))
            self.assertIn("exceeds atlas bounds", issues[0]["message"])


if __name__ == "__main__":
    unittest.main()

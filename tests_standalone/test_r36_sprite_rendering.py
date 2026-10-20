"""R36.C1: R28 PNG atlas rendering through the existing R4 resolver."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.assets.r36_runtime import R36PresentationAssets, MAX_CACHED_SPRITES
from drawtemp.render.iso_scene import (
    Camera, TopDownProjection, render_items, scene_from_action,
)
from sporebound.action_runtime import ActionRuntime
from sporebound.assets import AssetRegistry
from tests_standalone.test_drawtemp5_r4_assets import rgba_png
from tests_standalone.test_r36_action_actor_binding import bound_project
from tests_standalone.test_r36_committed_fx import encounter_scene


def write_sprite_art(root):
    art = root / "art"
    art.mkdir(exist_ok=True)
    (art / "s_idle.png").write_bytes(rgba_png(16, 32))
    (art / "s_attack.png").write_bytes(rgba_png(16, 32))
    (art / "s_hit.png").write_bytes(rgba_png(16, 32))


def decorated_actor(assets, frame):
    runtime = ActionRuntime(encounter_scene())
    scene = scene_from_action(runtime, animation_frames={"hero": frame})
    raw = render_items(scene, Camera(), TopDownProjection())
    result = assets.decorate(raw)
    return runtime, next(row for row in result if row["kind"] == "actor"
                         and row["id"] == "hero"), raw


class R36SpriteResolverTests(unittest.TestCase):
    def test_resolves_real_png_and_tick_driven_sprite_ids(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_sprite_art(root)
            project = bound_project()
            assets = R36PresentationAssets(
                AssetRegistry(project["assets"]), root)
            self.assertFalse(assets.has_animations)
            idle = {"state": "idle", "sprite": "s_idle", "frame_index": 0}
            runtime, row, raw = decorated_actor(assets, idle)
            self.assertEqual(row["assetId"], "s_idle")
            self.assertEqual((row["frameWidth"], row["frameHeight"]), (16, 32))
            self.assertEqual((row["atlasX"], row["atlasY"]), (0, 0))
            self.assertEqual((row["pivotX"], row["pivotY"]), (8, 32))
            self.assertTrue(row["imageUrl"].startswith("file:"))
            self.assertTrue(row["spriteReady"])
            self.assertEqual(assets.decorate(raw)[0]["kind"], raw[0]["kind"])
            self.assertEqual(assets.diagnostics()["resolved"], 1)
            self.assertGreaterEqual(assets.diagnostics()["cache_hits"], 1)
            self.assertEqual(runtime.tick, 0)
            self.assertEqual(runtime.recording(), ActionRuntime(
                encounter_scene()).recording())
            attack = {"state": "attack", "sprite": "s_attack", "frame_index": 0}
            _, attack_row, _ = decorated_actor(assets, attack)
            self.assertEqual(attack_row["assetId"], "s_attack")
            self.assertNotEqual(attack_row["imageUrl"], row["imageUrl"])

    def test_preserves_atlas_regions_and_existing_r4_annotations(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            write_sprite_art(root)
            manifest = deepcopy(bound_project()["assets"])
            sprite = next(entry for entry in manifest["entries"]
                          if entry["id"] == "s_idle")
            sprite["region"] = [4, 5, 7, 14]
            assets = R36PresentationAssets(AssetRegistry(manifest), root, {
                "version": 1, "sprites": {
                    "s_idle": {
                        "pivot": [3, 13], "footprint": [1, 1],
                    },
                },
            })
            _, row, _ = decorated_actor(
                assets, {"state": "idle", "sprite": "s_idle", "frame_index": 0})
            self.assertEqual((row["atlasX"], row["atlasY"]), (4, 5))
            self.assertEqual((row["frameWidth"], row["frameHeight"]), (7, 14))
            self.assertEqual((row["pivotX"], row["pivotY"]), (3, 13))

    def test_missing_corrupt_or_outside_png_falls_back_without_gameplay_change(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = deepcopy(bound_project()["assets"])
            assets = R36PresentationAssets(AssetRegistry(manifest), root)
            idle = {"state": "idle", "sprite": "s_idle", "frame_index": 0}
            runtime, row, _ = decorated_actor(assets, idle)
            self.assertIn("assetError", row)
            self.assertNotIn("imageUrl", row)
            write_sprite_art(root)
            _, row, _ = decorated_actor(assets, idle)
            self.assertIn("imageUrl", row)
            # A changed file is revalidated; never display a stale cached PNG.
            (root / "art/s_idle.png").write_bytes(b"not-a-png")
            _, row, _ = decorated_actor(assets, idle)
            self.assertIn("assetError", row)
            self.assertNotIn("imageUrl", row)
            self.assertEqual(runtime.recording(),
                             ActionRuntime(encounter_scene()).recording())

            manifest = deepcopy(bound_project()["assets"])
            first = next(x for x in manifest["entries"] if x["id"] == "s_idle")
            first["region"] = [15, 0, 12, 12]
            (root / "art/s_idle.png").write_bytes(rgba_png(16, 32))
            invalid_region = R36PresentationAssets(AssetRegistry(manifest), root)
            _, row, _ = decorated_actor(invalid_region, idle)
            self.assertIn("assetError", row)
            self.assertNotIn("imageUrl", row)

    def test_no_new_renderer_cache_for_legacy_actors(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            assets = R36PresentationAssets(
                AssetRegistry(bound_project()["assets"]), root)
            runtime = ActionRuntime(encounter_scene())
            raw = render_items(scene_from_action(runtime),
                               Camera(), TopDownProjection())
            decorated = assets.decorate(raw, elapsed_ms=1000)
            self.assertEqual(len(decorated), len(raw))
            self.assertFalse(any("imageUrl" in row for row in decorated
                                 if row["kind"] == "actor"))


if __name__ == "__main__":
    unittest.main()

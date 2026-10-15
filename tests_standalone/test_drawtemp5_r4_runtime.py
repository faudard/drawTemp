"""R4.B integration: real project atlas → one R3 scene → Qt Studio and Player.

Headless assertions deliberately do not claim GPU certification.
"""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.assets.atlas import DirectionalLayout, plan_directional_import
from drawtemp.assets.project import import_into_project
from drawtemp.assets.runtime import PresentationAssets
from drawtemp.core import Content, GameProject
from drawtemp.player.qt_app import build_controller, scene_for_player
from drawtemp.render.iso_scene import Camera, render_items, scene_from_mission
from drawtemp.sdk.reference import MISSION, reference_project
from tests_standalone.test_drawtemp5_r4_assets import rgba_png

ROOT = Path(__file__).resolve().parents[1]


def imported_jeanne(folder):
    root = Path(folder)
    content, project = reference_project()
    content_path = root / "jeanne.json"
    project_path = root / "jeanne.game.json"
    content_path.write_text(__import__("json").dumps(content.to_dict()), encoding="utf-8")
    project.save(project_path, content)
    atlas = root / "source.png"
    atlas.write_bytes(rgba_png(256, 128))
    plan = plan_directional_import(
        project.asset_registry(), atlas, "jeanne",
        DirectionalLayout((64, 64), {"idle": (0, 1)}, pivot=(32, 60)),
        binding_prefix="jeanne", license_id="CC0-1.0")
    import_into_project(project_path, content, plan)
    reopened = GameProject.load(project_path, content)
    return content_path, project_path, content, reopened


class R4RuntimeIntegrationTests(unittest.TestCase):
    def test_one_manifest_binds_jeanne_in_both_client_scenes(self):
        with TemporaryDirectory() as tmp:
            content_path, project_path, content, project = imported_jeanne(tmp)
            art = PresentationAssets.for_project(project, project_path)
            scene = scene_from_mission(content.missions[MISSION])
            rows = render_items(scene, Camera())
            decorated = art.decorate(rows, elapsed_ms=0)
            jeanne = next(row for row in decorated
                          if row["kind"] == "actor" and row["id"] == "jeanne")
            self.assertEqual(jeanne["assetId"], "jeanne.south.idle.0")
            self.assertEqual((jeanne["pivotX"], jeanne["pivotY"]), (32, 60))
            self.assertEqual((jeanne["frameWidth"], jeanne["frameHeight"]), (64, 64))
            self.assertEqual((jeanne["atlasX"], jeanne["atlasY"]), (0, 0))
            self.assertTrue(jeanne["imageUrl"].startswith("file:"))
            self.assertTrue(art.has_animations)
            next_row = next(row for row in art.decorate(rows, elapsed_ms=120)
                            if row["kind"] == "actor" and row["id"] == "jeanne")
            self.assertEqual(next_row["assetId"], "jeanne.south.idle.1")
            self.assertEqual(next_row["atlasY"], 64)
            self.assertEqual(art.decorate(rows, elapsed_ms=240), decorated)
            self.assertFalse(any("imageUrl" in row for row in decorated
                                 if row["kind"] != "actor"))
            self.assertEqual(render_items(scene, Camera()), rows)

            # Player consumes the same GameProject and exact R3 projection.
            ctrl = build_controller(content_path=content_path, project_path=project_path,
                                    save_dir=Path(tmp) / "saves")
            self.assertEqual(ctrl.asset_project_path, project_path)
            player = PresentationAssets.for_project(ctrl.project, ctrl.asset_project_path)
            self.assertEqual(player.decorate(render_items(scene_for_player(ctrl), Camera())),
                             decorated)
            # Save/reload preserves imported IDs without rewriting content.
            ctrl.new_game()
            ctrl.save(1)
            ctrl.load(1)
            reloaded = GameProject.load(project_path, content)
            self.assertEqual(reloaded.asset_registry().to_dict(),
                             project.asset_registry().to_dict())

    def test_missing_bound_sprite_is_visible_error_and_no_silent_asset_rebinding(self):
        with TemporaryDirectory() as tmp:
            _, project_path, content, project = imported_jeanne(tmp)
            art = PresentationAssets.for_project(project, project_path)
            scene = scene_from_mission(content.missions[MISSION])
            rows = render_items(scene, Camera())
            actor = next(row for row in rows if row["kind"] == "actor"
                         and row["id"] == "jeanne")
            self.assertIn("imageUrl", art.decorate([actor])[0])
            atlas = Path(tmp) / "assets/imported/jeanne.png"
            atlas.unlink()
            invalid = art.decorate([actor])[0]
            self.assertIn("assetError", invalid)
            self.assertNotIn("imageUrl", invalid)
            self.assertEqual(actor, next(row for row in rows if row["kind"] == "actor"
                                          and row["id"] == "jeanne"))
            self.assertIsNone(art.actor_frame("unbound"))
            with self.assertRaises(ValueError):
                art.actor_frame("jeanne", direction="diagonal")
            with self.assertRaises(ValueError):
                art.decorate([actor], elapsed_ms=-1)

    def test_relative_paths_and_static_sprite_binding(self):
        with TemporaryDirectory() as tmp:
            content_path, project_path, content, project = imported_jeanne(tmp)
            current = Path.cwd()
            try:
                os.chdir(Path(tmp).parent)
                runtime = PresentationAssets.for_project(project, project_path)
                frame = runtime.actor_frame("jeanne")
                self.assertTrue(frame["imageUrl"].startswith(project_path.parent.as_uri()))
            finally:
                os.chdir(current)
            with self.assertRaises(ValueError):
                build_controller(project_path=project_path)
            with self.assertRaises(ValueError):
                build_controller(reference=True, content_path=content_path,
                                 project_path=project_path)

    def test_canonical_viewport_is_used_by_both_and_no_secondary_painter(self):
        qml = (ROOT / "drawtemp/render/IsoViewport.qml").read_text(encoding="utf-8")
        self.assertIn("sourceClipRect", qml)
        self.assertIn("renderer.advanceVisual(125)", qml)
        self.assertIn("actor.imageUrl", qml)
        self.assertNotIn("Canvas {", qml)


if __name__ == "__main__":
    unittest.main()

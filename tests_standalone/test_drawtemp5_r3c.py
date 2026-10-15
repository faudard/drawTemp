"""R3.C headless composition, cutaway, motion and Qt integration regression."""
from copy import deepcopy
import importlib.util
import os
import unittest

from drawtemp.render.iso_scene import (Camera, IsoProjection, fingerprint, pick,
                                       render_items, scene_from_mission)
from drawtemp.render.visual_compositor import (
    automatic_cutaway, actor_visual_position, building_surfaces, top_building_hit,
)
from drawtemp.sdk.reference import MISSION, reference_project


def house_scene():
    content, _ = reference_project()
    scene = scene_from_mission(content.missions[MISSION])
    scene["structures"] = [{
        "id": "r3c-house", "name": "Maison", "anchor": [2, 1],
        "turns": 0, "door_slot": 0
    }]
    for actor in scene["actors"]:
        actor["x"], actor["y"] = 0, 0
    return scene


class SharedCompositorTests(unittest.TestCase):
    def test_canonical_structure_scene_data_remains_detached(self):
        content, _ = reference_project()
        mission = deepcopy(content.missions[MISSION])
        mission.structures.append({
            "id": "r3c-house", "name": "Maison", "anchor": [2, 1],
            "turns": 0, "door_slot": 0
        })
        s = scene_from_mission(mission)
        before = deepcopy(mission.structures)
        s["structures"][0]["anchor"][0] = 7
        self.assertEqual(mission.structures, before)
        self.assertIn("interior_floors", s)

    def test_roof_occlusion_and_floor_visibility(self):
        scene = house_scene()
        p = IsoProjection()
        normal = building_surfaces(scene, p)
        self.assertTrue(any(s["part"] == "roof" for s in normal))
        self.assertTrue(any(s["part"] == "wall" for s in normal))
        self.assertEqual(automatic_cutaway(scene), ())
        scene["actors"][0]["x"], scene["actors"][0]["y"] = 3, 2
        self.assertEqual(automatic_cutaway(scene), ("r3c-house",))
        cut = building_surfaces(scene, p)
        self.assertFalse(any(s["part"] == "roof" for s in cut))
        # Dead actors must not force a cutaway.
        scene["actors"][0]["alive"] = False
        self.assertEqual(automatic_cutaway(scene), ())
        self.assertEqual(automatic_cutaway(scene, selected=(3, 2)), ("r3c-house",))
        scene["interior_floors"] = [{
            "structure_id": "r3c-house", "level": 1,
            "tiles": [{"pos": [0, 0], "surface": "stone"}]
        }]
        floors = building_surfaces(scene, p, active_level=1)
        self.assertEqual(len([s for s in floors if s["part"] == "floor"]), 1)
        self.assertFalse(any(s["part"] == "roof" for s in floors))

    def test_building_surface_picking_camera_zoom_and_depth(self):
        scene = house_scene()
        p = IsoProjection()
        for zoom in (.5, 1, 2.6):
            camera = Camera(width=1024, height=768, zoom=zoom)
            camera.center(*p.project(3, 2))
            rows = render_items(scene, camera)
            roof = next(r for r in rows if r["kind"] == "building" and r["part"] == "roof")
            cx = sum(q[0] for q in roof["vertices"]) / 4
            cy = sum(q[1] for q in roof["vertices"]) / 4
            screen = camera.screen(cx, cy)
            hit = top_building_hit(rows, camera, *screen)
            self.assertEqual(hit["structure_id"], "r3c-house")
            self.assertEqual(hit["part"], "roof")
            self.assertEqual(pick(scene, camera, *screen)["kind"], "building")
            self.assertEqual(rows, sorted(rows, key=lambda row: (row["zOrder"], row["id"])))
        # Selecting a cell under this roof removes its roof surface.
        rows = render_items(scene, camera, selected=(3, 2))
        self.assertFalse(any(r["kind"] == "building" and r["part"] == "roof" for r in rows))

    def test_move_and_attack_use_actual_sprite_footpoint_no_core_mutation(self):
        scene = house_scene()
        scene["actors"][0]["x"], scene["actors"][0]["y"] = 4, 2
        actor = scene["actors"][0]
        from drawtemp.render.tile_chunks import TileChunkIndex
        heights = TileChunkIndex(scene).elevations
        baseline = fingerprint(scene)
        clip = {"kind": "move", "actor": actor["id"],
                "start": [2, 2], "end": [4, 2]}
        pts = [actor_visual_position(actor, clip, t, heights,
                                     scene["width"], scene["height"], IsoProjection())
               for t in (0, .5, 1)]
        self.assertEqual([round(p["worldX"], 3) for p in pts], [2, 3, 4])
        self.assertEqual([p["kind"] for p in pts], ["move"] * 3)
        attack = dict(clip, kind="attack")
        self.assertEqual(actor_visual_position(actor, attack, 0, heights,
                                               scene["width"], scene["height"],
                                               IsoProjection())["worldX"], 2)
        self.assertEqual(actor_visual_position(actor, attack, 1, heights,
                                               scene["width"], scene["height"],
                                               IsoProjection())["worldX"], 2)
        self.assertIsNone(actor_visual_position(actor, dict(clip, actor="unknown"), .5,
                                                heights, scene["width"], scene["height"],
                                                IsoProjection()))
        self.assertIsNone(actor_visual_position(actor, clip, float("nan"),
                                                heights, scene["width"], scene["height"],
                                                IsoProjection()))
        self.assertEqual(fingerprint(scene), baseline)

    def test_player_uses_only_shared_renderer_character_node(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        board = (root / "drawtemp/render/TacticalBoard.qml").read_text()
        viewport = (root / "drawtemp/render/IsoViewport.qml").read_text()
        self.assertNotIn("id: motionGhost", board)
        self.assertIn("activeVisualClip:", board)
        self.assertIn("renderer.motionPoint", viewport)
        self.assertIn("id: buildingComponent", viewport)
        self.assertNotIn("Canvas {", viewport)


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "PySide6 optional")
class QtR3CSmoke(unittest.TestCase):
    def test_qml_runtime_shared_cutaway_and_pose(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtGui import QGuiApplication
        from drawtemp.render.qt_viewport import create_view
        app = QGuiApplication.instance() or QGuiApplication([])
        scene = house_scene()
        view, controller = create_view(scene)
        try:
            self.assertIsNotNone(view.rootObject())
            self.assertEqual(controller.autoCutawayStructures, [])
            self.assertTrue(any(row["kind"] == "building" for row in controller.items))
            actor = scene["actors"][0]
            result = controller.motionPoint({
                "actor": actor["id"], "kind": "move",
                "start": [0, 0], "end": [2, 1]}, .5)
            self.assertTrue(isinstance(result["sx"], float))
            controller.setActiveLevel(1)
            self.assertEqual(controller.autoCutawayStructures, ["r3c-house"])
            controller.replace_scene(deepcopy(scene))
            self.assertEqual(controller.autoCutawayStructures, ["r3c-house"])
        finally:
            view.close()


if __name__ == "__main__":
    unittest.main()

"""PR3: persistent visual layer stack, independent of tactical terrain."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.visual_layer_authoring import VisualLayerStudio
from drawtemp.render.iso_scene import (
    Camera, IsoProjection, TopDownProjection, render_items, scene_from_mission,
)
from sporebound.visual_layers import (
    VISUAL_NS, MAX_LAYERS, attach_visual_layers, projected_layer_rows,
    validate_visual_layers, visual_image_key,
)


class VisualLayerTests(unittest.TestCase):
    def setUp(self):
        self.map = MapStudio.reference()
        self.map.create("visual_test", "Visual map", 6, 6)
        self.visual = VisualLayerStudio(self.map)

    def test_legacy_document_is_unchanged_without_visual_extension(self):
        before = self.map.snapshot()
        self.assertEqual(self.visual.layers(), [])
        self.assertEqual(self.map.snapshot(), before)
        self.assertNotIn(VISUAL_NS, before["project"].get("extensions", {}))

    def test_stack_mixed_planes_and_actor_depth_order(self):
        self.visual.create("grass_details", "Ground Details", plane="below")
        self.visual.create("roof", "Above Actors", plane="above")
        self.visual.paint("grass_details", [(2, 2)], material="stone")
        self.visual.paint("roof", [(2, 2)], material="cobble",
                          mask=[255, 64, 0, 255])
        scene = self.scene()
        rows = [r for r in render_items(scene, Camera(900, 700),
                                        TopDownProjection())
                if r["kind"] == "visual-layer"]
        self.assertEqual(len(rows), 2)
        self.assertLess(rows[0]["zOrder"], 2 * 100 + 60)
        self.assertGreater(rows[1]["zOrder"], 2 * 100 + 60)
        self.assertEqual(rows[1]["mask"], [255, 64, 0, 255])
        self.assertEqual(rows[1]["visualKey"], visual_image_key(
            "cobble", [255, 64, 0, 255], (2 * 17 + 2 * 29) & 1))
        self.assertFalse(any(r["kind"] == "visual-layer"
                             for r in render_items(scene, Camera(900, 700),
                                                   IsoProjection())))

    def scene(self):
        snap = self.map.snapshot()
        content = Content.from_dict(snap["content"])
        return attach_visual_layers(
            scene_from_mission(content.missions[self.map.mission_id]),
            snap["project"].get("extensions", {}))

    def test_reorder_opacity_visibility_and_locks_are_undoable(self):
        self.visual.create("one", "One")
        self.visual.create("two", "Two")
        self.visual.paint("one", [(1, 1)], material="sand")
        self.visual.paint("two", [(1, 1)], material="stone")
        self.visual.reorder("one", +1)
        self.assertEqual([r["id"] for r in self.visual.layers()], ["two", "one"])
        self.map.undo()
        self.assertEqual([r["id"] for r in self.visual.layers()], ["one", "two"])
        self.visual.configure("one", visible=False, opacity=33, locked=True)
        self.assertEqual(self.visual.layers()[0]["opacity"], 33)
        self.assertEqual(len([r for r in self.scene()["visual_layers"] if r["visible"]]), 1)
        with self.assertRaises(Exception):
            self.visual.paint("one", [(2, 2)], material="grass")
        with self.assertRaises(Exception):
            self.visual.remove("one")
        self.visual.configure("one", locked=False, visible=True)
        self.assertEqual(self.visual.layers()[0]["cells"][0]["material"], "sand")

    def test_mask_eraser_do_not_rewrite_base_terrain(self):
        before_content = deepcopy(self.map.snapshot()["content"])
        self.visual.create("decor", "Decor")
        self.visual.paint("decor", [(1, 1), (2, 2)], material="dirt")
        self.visual.paint("decor", [(1, 1), (2, 2)], mask=[0, 255, 0, 128],
                          operation="mask")
        self.assertEqual(self.visual.layers()[0]["cells"][0]["mask"],
                         [0, 255, 0, 128])
        self.visual.paint("decor", [(1, 1)], operation="erase")
        self.assertEqual(len(self.visual.layers()[0]["cells"]), 1)
        self.map.undo()
        self.assertEqual(len(self.visual.layers()[0]["cells"]), 2)
        self.assertEqual(self.map.snapshot()["content"], before_content)

    def test_invalid_strokes_are_rejected_atomically(self):
        self.visual.create("decor", "Decor")
        previous = self.map.snapshot()
        for kwargs in (
            {"cells": [(6, 1)]},
            {"cells": [(-1, 1)]},
            {"cells": [(1, 1)], "mask": [1, 2, 3]},
            {"cells": [(1, 1)], "mask": [1, 2, 3, 256]},
            {"cells": [(1, 1)], "material": "remote.png"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(Exception):
                self.visual.paint("decor", **kwargs)
            self.assertEqual(self.map.snapshot(), previous)

    def test_canonical_validator_rejects_invalid_mask_duplicate_and_unknown_map(self):
        self.visual.create("decor", "Decor")
        self.visual.paint("decor", [(2, 2)], material="grass")
        content = Content.from_dict(self.map.snapshot()["content"])
        project = self.map.snapshot()["project"]
        cloned = deepcopy(project)
        cloned["extensions"][VISUAL_NS]["data"]["missions"]["visual_test"][0][
            "cells"][0]["mask"] = [255, 255, 256, 255]
        with self.assertRaises(Exception):
            GameProject.from_dict(cloned, content)
        duplicated = deepcopy(project)
        cells = duplicated["extensions"][VISUAL_NS]["data"]["missions"][
            "visual_test"][0]["cells"]
        cells.append(deepcopy(cells[0]))
        with self.assertRaises(Exception):
            GameProject.from_dict(duplicated, content)
        unknown = deepcopy(project)
        unknown["extensions"][VISUAL_NS]["data"]["missions"]["unknown"] = []
        with self.assertRaises(Exception):
            GameProject.from_dict(unknown, content)

    def test_player_projection_reads_the_same_canonical_graphics(self):
        # Player must read the authored project extension, not the editor dock
        # or its user-local mapbuilder-view.json preferences.
        from types import SimpleNamespace
        from drawtemp.player.qt_app import scene_for_player

        first_mid = self.map.map_ids()[0]
        self.map.select_map(first_mid)
        self.visual.create("above", "Above", plane="above")
        self.visual.paint("above", [(2, 2)], material="rock",
                          mask=[255, 50, 0, 255])
        snapshot = self.map.snapshot()
        content = Content.from_dict(snapshot["content"])
        project = GameProject.from_dict(snapshot["project"], content)
        detached = scene_for_player(SimpleNamespace(
            content=content, project=project, session=None))
        self.assertEqual(detached["mission"], first_mid)
        self.assertEqual(detached["visual_layers"][0]["id"], "above")
        self.assertEqual(detached["visual_layers"][0]["cells"][0]["mask"],
                         [255, 50, 0, 255])
        self.assertEqual(detached["visual_layers"], attach_visual_layers(
            scene_from_mission(content.missions[first_mid]),
            project.extensions)["visual_layers"])

    def test_save_reload_roundtrip_and_no_sidecar(self):
        self.visual.create("details", "Flower Details")
        self.visual.paint("details", [(2, 3)], material="sand",
                          mask=[12, 34, 56, 78])
        with TemporaryDirectory() as folder:
            path = Path(folder) / "layers.json"
            self.map.save_as(path)
            loaded = MapStudio.open(path)
            rows = VisualLayerStudio(loaded).layers()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["cells"][0]["mask"], [12, 34, 56, 78])
            self.assertFalse(path.with_suffix(".visual-layers.json").exists())

    def test_remove_last_layer_restores_missing_extension(self):
        self.visual.create("decoration", "Decoration")
        self.visual.remove("decoration")
        self.assertNotIn(VISUAL_NS, self.map.snapshot()["project"].get("extensions", {}))
        self.map.undo()
        self.assertEqual(self.visual.layers()[0]["id"], "decoration")

    def test_masks_have_bounded_deterministic_sprite_urls(self):
        self.assertEqual(len(visual_image_key("dirt", [0, 127, 255, 42])), 11)
        self.assertEqual(visual_image_key("dirt", [0, 127, 255, 42]),
                         "v10007fff2a")
        with self.assertRaises(Exception):
            visual_image_key("grass", [1, 2, 3, 999])


if __name__ == "__main__":
    unittest.main()

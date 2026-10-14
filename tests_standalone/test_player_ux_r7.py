"""R7 Player UX policies are deterministic and independent of Tk/Studio."""
from dataclasses import replace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.iso_battle_view import anchored_iso_zoom, hit_test_battle, viewport_shift
from sporebound.iso_map import IsoGeometry
from sporebound.model import Content
from sporebound.player_ux import (
    KeyBindings, PresentationState, clamp_selection, combat_hud, zoom_to,
    ZOOM_PRESETS,
)
from sporebound.presentation import Camera, battle_frame


class PlayerUXR7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)

    def test_key_remap_is_atomic_and_collision_free(self):
        keys = KeyBindings()
        keys.replace({"execute": "<F1>", "end": "<F2>"})
        self.assertEqual(keys.get("execute"), "<F1>")
        before = keys.items()
        with self.assertRaises(ValueError):
            keys.replace({"cancel": "<F1>"})
        self.assertEqual(keys.items(), before)
        with self.assertRaises(ValueError):
            keys.replace({"execute": "<Invalid>"})
        with self.assertRaises(ValueError):
            keys.replace({"teleport": "<F4>"})
        self.assertEqual(keys.items(), before)

    def test_presentation_invalidates_stale_callbacks(self):
        state = PresentationState()
        old = state.transition("battle")
        self.assertTrue(state.current(old))
        overlay = state.begin_overlay("cinematic")
        self.assertFalse(state.current(old))
        self.assertTrue(state.current(overlay))
        next_screen = state.transition("campaign")
        self.assertIsNone(state.overlay)
        self.assertFalse(state.current(overlay))
        self.assertTrue(state.current(next_screen))

    def test_camera_presets_anchor_and_keyboard_bounds(self):
        camera = Camera(52, 11, -15)
        anchor = (290, 140)
        world = ((anchor[0] - camera.offset_x) / camera.cell_size,
                 (anchor[1] - camera.offset_y) / camera.cell_size)
        for size in ZOOM_PRESETS:
            resized = zoom_to(camera, size, anchor)
            self.assertEqual(resized.cell_size, size)
            self.assertAlmostEqual(
                (anchor[0] - resized.offset_x) / resized.cell_size, world[0])
            self.assertAlmostEqual(
                (anchor[1] - resized.offset_y) / resized.cell_size, world[1])
        self.assertEqual(clamp_selection((-9, 500), 8, 4), (0, 3))
        with self.assertRaises(ValueError):
            zoom_to(camera, 15)

    def test_iso_presets_keep_same_picked_tile(self):
        battle = Battle(self.content, "garden", seed=3)
        camera = Camera(54, 8, 8)
        viewport = (900, 700)
        cell = (2, 2)
        geo = IsoGeometry(battle.board, camera.cell_size)
        shift = viewport_shift(geo, camera, viewport)
        point = tuple(a + b for a, b in zip(geo.center(cell), shift))
        self.assertEqual(hit_test_battle(battle.board, camera, viewport, point), cell)
        for size in ZOOM_PRESETS:
            zoomed = anchored_iso_zoom(battle.board, camera, viewport,
                                      0, point, size=size)
            self.assertEqual(zoomed.cell_size, size)
            self.assertEqual(hit_test_battle(battle.board, zoomed, viewport, point),
                             cell)

    def test_combat_hud_uses_engine_projections_without_mutation(self):
        battle = Battle(self.content, "garden", seed=11)
        before = battle.digest()
        frame = battle_frame(battle, (2, 2))
        hud = combat_hud(frame, battle.mission.objective, (2, 2))
        self.assertEqual(hud.objective, battle.mission.objective)
        self.assertEqual(len(hud.roster), len(frame.actors))
        self.assertEqual(len(hud.timeline), len(frame.timeline))
        self.assertEqual(before, battle.digest())
        self.assertEqual(hud, combat_hud(frame, battle.mission.objective, (2, 2)))
        with self.assertRaises(ValueError):
            combat_hud(frame, cell=(frame.width, 0))

    def test_multicell_actors_are_read_from_footprints(self):
        battle = Battle(self.content, "garden", seed=1)
        frame = battle_frame(battle)
        hero = replace(frame.actors[0], pos=(1, 1), footprint=(2, 2))
        shown = replace(frame, actors=(hero,), selected=(2, 2))
        hud = combat_hud(shown, "reach the gate", (2, 2))
        self.assertIn(hero.name, hud.selection_summary)


if __name__ == "__main__":
    unittest.main()

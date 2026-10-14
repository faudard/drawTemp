"""3.7.32J — real Tk animated environment sheets in Editor and Player."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.engine import Battle
from sporebound.environment_atlas import FRAME_COUNT, FRAME_SIZE, KINDS
from sporebound.iso_battle_view import IsoBattleCanvas
from sporebound.iso_environment_atlas import IsoEnvironmentAtlas
from sporebound.iso_map import render_isometric
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame
from sporebound.terrain_ambient import TICK_MS, TerrainAmbientAnimator


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a real Xvfb/Tk display')
class EnvironmentAtlasGuiTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)

    def mission(self):
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'env_atlas_gui', 'Environment atlas', 16, 16)
        mission = next(m for m in data['missions'] if m['id'] == 'env_atlas_gui')
        mission['board']['tiles'].extend((
            {'pos': [8, 8], 'feature': 'reeds'},
            {'pos': [9, 8], 'surface': 'water', 'blocked': True},
            {'pos': [8, 9], 'feature': 'tree'},
        ))
        return Content.from_dict(data).missions['env_atlas_gui']

    def test_png_frames_correct_dimensions_and_cache_at_three_zooms(self):
        import tkinter as tk
        canvas = tk.Canvas(self.root)
        art = IsoEnvironmentAtlas(canvas)
        for zoom in (24, 54, 96):
            for kind in KINDS:
                for frame in range(FRAME_COUNT):
                    with self.subTest(zoom=zoom, kind=kind, frame=frame):
                        image = art.frame(kind, zoom, frame)
                        self.assertIsNotNone(image)
                        width = max(1, round(FRAME_SIZE*zoom/54))
                        self.assertEqual((image.width(), image.height()), (width, width))
                        self.assertIs(image, art.frame(kind, zoom, frame))
        self.assertFalse(art._unavailable)
        self.assertEqual(len(art._sources), len(KINDS))
        self.assertEqual(len(art._frames), 3*len(KINDS)*FRAME_COUNT)

    def test_shared_renderer_image_only_ticks_and_vector_fallback(self):
        import tkinter as tk
        canvas, fallback = tk.Canvas(self.root), tk.Canvas(self.root)
        art = IsoEnvironmentAtlas(canvas)
        mission = self.mission()
        args = dict(cell_size=54, layers={}, selected_cell=(0, 0),
                    selected_tiles=())
        render_isometric(canvas, mission.board, mission, mission.units,
                         ambient_atlas=art, **args)
        sprites = canvas.find_withtag('iso_ambient')
        self.assertGreater(len(sprites), 0)
        self.assertTrue(all(canvas.type(item) == 'image' for item in sprites))
        animator = TerrainAmbientAnimator()
        self.assertEqual(animator.capture(canvas), len(sprites))
        before = {i: canvas.itemcget(i, 'image') for i in sprites}
        original_positions = {i: tuple(canvas.coords(i)) for i in sprites}
        stable_ids = canvas.find_all()
        frames = []
        for time_step in range(8):
            animator.tick(canvas, time_step*TICK_MS, atlas=art, cell_size=54)
            self.assertEqual(canvas.find_all(), stable_ids)
            self.assertEqual(
                {i: tuple(canvas.coords(i)) for i in sprites}, original_positions)
            frames.append(tuple(canvas.itemcget(i, 'image') for i in sprites))
        self.assertGreaterEqual(len(set(frames)), 4)
        animator.restore(canvas)
        self.assertEqual(
            {i: canvas.itemcget(i, 'image') for i in sprites}, before)

        render_isometric(fallback, mission.board, mission, mission.units, **args)
        self.assertTrue(fallback.find_withtag('iso_ambient'))
        self.assertTrue(all(fallback.type(i) != 'image'
                            for i in fallback.find_withtag('iso_ambient')))

    def test_retained_editor_undo_redraw_restores_raster_handles(self):
        import tkinter as tk
        canvas = tk.Canvas(self.root)
        art = IsoEnvironmentAtlas(canvas)
        scene = self.mission()
        editor = EditorRenderCache(canvas)
        options = dict(cell_size=54, layers={}, selected_cell=(0, 0),
                       selected_tiles=(), ambient_atlas=art)
        editor.draw(scene.board, scene, scene.units, **options)
        animator = TerrainAmbientAnimator()
        animator.capture(canvas)
        sprite_ids = tuple(canvas.find_withtag('iso_ambient'))
        baseline = tuple(canvas.itemcget(i, 'image') for i in sprite_ids)
        animator.tick(canvas, 5*TICK_MS, atlas=art, cell_size=54)
        animator.restore(canvas)
        editor.draw(scene.board, scene, scene.units, **options)
        self.assertEqual(tuple(canvas.find_withtag('iso_ambient')), sprite_ids)
        self.assertEqual(
            tuple(canvas.itemcget(i, 'image') for i in sprite_ids), baseline)
        self.assertEqual(editor.stats['created'], 0)
        self.assertEqual(editor.stats['updated'], 0)

    def test_player_idle_frames_never_rebuild_static_scene(self):
        import tkinter as tk
        canvas = tk.Canvas(self.root)
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'env_battle', 'Animated environment', 16, 16)
        mission = next(m for m in data['missions'] if m['id'] == 'env_battle')
        mission['board']['tiles'].append({'pos': [8, 8], 'feature': 'reeds'})
        battle = Battle(Content.from_dict(data), 'env_battle', seed=37)
        renderer = IsoBattleCanvas(canvas)
        frame = battle_frame(battle, (8, 8))
        camera = Camera(54, 0, 0)
        digest = battle.digest()
        renderer.draw(battle, frame, camera, ambient_clock_ms=0)
        self.assertTrue(renderer.animates_when_idle)
        sprites = canvas.find_withtag('iso_ambient')
        self.assertTrue(sprites)
        self.assertTrue(all(canvas.type(item) == 'image' for item in sprites))
        ids = canvas.find_all()
        for stamp in range(1, FRAME_COUNT):
            renderer.draw(battle, frame, camera,
                          ambient_clock_ms=stamp*TICK_MS)
            self.assertEqual(renderer._scene_rebuilds, 1)
            self.assertEqual(canvas.find_all(), ids)
        self.assertEqual(battle.digest(), digest)
        renderer.dispose()
        self.assertFalse(renderer.animates_when_idle)


if __name__ == '__main__':
    unittest.main()

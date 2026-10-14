"""3.7.32I — real Tk/Player ambient motion, cache and visual opt-out."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.engine import Battle
from sporebound.iso_battle_view import IsoBattleCanvas
from sporebound.iso_map import IsoTerrainAtlas, render_isometric
from sporebound.model import Content, Tile
from sporebound.presentation import Camera, battle_frame
from sporebound.terrain_ambient import (
    TICK_MS, TerrainAmbientAnimator,
)


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires real Tk/Xvfb')
class TerrainAmbientGuiTests(unittest.TestCase):
    @staticmethod
    def scene():
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'ambient_art', 'Ambient art', 16, 16)
        mission = Content.from_dict(data).missions['ambient_art']
        mission.board.tiles[(8, 8)] = Tile(feature='reeds')
        mission.board.tiles[(9, 8)] = Tile(surface='water', blocked=True)
        mission.board.tiles[(8, 9)] = Tile(feature='tree')
        return mission

    def test_canvas_only_ticks_preserve_item_identity_and_restore(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        canvas = tk.Canvas(root)
        scene = self.scene()
        atlas = IsoTerrainAtlas(canvas)
        options = dict(cell_size=54, layers={}, atlas=atlas,
                       selected_cell=(0, 0), selected_tiles=())
        render_isometric(canvas, scene.board, scene, scene.units, **options)
        animator = TerrainAmbientAnimator()
        self.assertGreater(animator.capture(canvas), 0)
        ids = tuple(canvas.find_all())
        ambient_ids = tuple(canvas.find_withtag('iso_ambient'))
        original = {item: tuple(canvas.coords(item)) for item in ambient_ids}
        snapshots = []
        for i in range(8):
            animator.tick(canvas, i*TICK_MS)
            snapshots.append(tuple(tuple(canvas.coords(j)) for j in ambient_ids))
            self.assertEqual(tuple(canvas.find_all()), ids)
        self.assertGreater(len(set(snapshots)), 2)
        animator.restore(canvas)
        self.assertEqual(
            {item: tuple(canvas.coords(item)) for item in ambient_ids}, original)
        # A new command buffer matches canonical static renderer coordinates.
        other = tk.Canvas(root)
        render_isometric(other, scene.board, scene, scene.units,
                         cell_size=54, layers={},
                         selected_cell=(0, 0), selected_tiles=())
        canonical = [tuple(other.coords(i))
                     for i in other.find_withtag('iso_ambient')]
        self.assertEqual([tuple(canvas.coords(i)) for i in ambient_ids],
                         canonical)
        render_isometric(canvas, scene.board, scene, scene.units,
                         **{**options, 'layers': {'Ambiance': False}})
        self.assertFalse(canvas.find_withtag('iso_ambient'))

    def test_player_idle_ticks_only_update_terrain_and_no_new_battle_turn(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        canvas = tk.Canvas(root)
        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'ambient_battle', 'Ambient battle', 16, 16)
        mission = next(m for m in data['missions'] if m['id'] == 'ambient_battle')
        mission['board']['tiles'].append({'pos': [8, 8],
                                          'feature': 'reeds',
                                          'surface': 'grass'})
        content = Content.from_dict(data)
        battle = Battle(content, 'ambient_battle', seed=42)
        renderer = IsoBattleCanvas(canvas)
        camera = Camera(54, 0, 0)
        frame = battle_frame(battle, (8, 8))
        renderer.draw(battle, frame, camera, ambient_clock_ms=0)
        self.assertTrue(renderer.animates_when_idle)
        static_ids = tuple(canvas.find_all())
        first_pos = {item: tuple(canvas.coords(item))
                     for item in canvas.find_withtag('iso_ambient')}
        result = battle.result
        for t in (TICK_MS, 2*TICK_MS, 3*TICK_MS):
            renderer.draw(battle, frame, camera, ambient_clock_ms=t)
            self.assertEqual(renderer._scene_rebuilds, 1)
            self.assertEqual(tuple(canvas.find_all()), static_ids)
        self.assertNotEqual(first_pos,
                            {item: tuple(canvas.coords(item))
                             for item in canvas.find_withtag('iso_ambient')})
        self.assertEqual(battle.result, result)
        self.assertEqual(renderer._actor_only_frames, 3)
        # Switching to the flat Player mode destroys the iso items while
        # retaining the same battle/frame identity: ISO must rebuild.
        canvas.delete('all')
        canvas.create_oval(0, 0, 12, 12, tags='actor')
        renderer.draw(battle, frame, camera, ambient_clock_ms=4*TICK_MS)
        self.assertEqual(renderer._scene_rebuilds, 2)
        self.assertTrue(canvas.find_withtag('iso_ambient'))
        renderer.dispose()
        self.assertFalse(renderer.animates_when_idle)

    def test_retained_editor_does_not_accumulate_offsets_on_refresh(self):
        import tkinter as tk
        root = tk.Tk()
        self.addCleanup(root.destroy)
        canvas = tk.Canvas(root)
        renderer = EditorRenderCache(canvas)
        scene = self.scene()
        animator = TerrainAmbientAnimator()
        params = dict(cell_size=24, layers={}, selected_cell=(0, 0),
                      selected_tiles=())
        renderer.draw(scene.board, scene, scene.units, **params)
        animator.capture(canvas)
        first = {i: tuple(canvas.coords(i)) for i in canvas.find_withtag('iso_ambient')}
        animator.tick(canvas, 5*TICK_MS)
        animator.restore(canvas)
        renderer.draw(scene.board, scene, scene.units, **params)
        animator.capture(canvas)
        self.assertEqual(first, {
            i: tuple(canvas.coords(i)) for i in canvas.find_withtag('iso_ambient')
        })
        self.assertEqual(renderer.stats['created'], 0)
        self.assertEqual(renderer.stats['updated'], 0)


if __name__ == '__main__':
    unittest.main()

"""Real Tk parity: cached Studio scene versus the original full renderer."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.iso_map import render_isometric, IsoGeometry, IsoTerrainAtlas
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_fortification_atlas import IsoFortificationAtlas
from sporebound.iso_actor_atlas import IsoActorAtlas
from sporebound.iso_props import IsoPropAtlas
from sporebound.model import Content
from examples.fortified_village_3717a import build_village_document, MISSION_ID


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1', 'Requires Tk display')
class EditorRenderCacheTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.canvas = tk.Canvas(self.root)
        self.reference = tk.Canvas(self.root)
        self.renderer = EditorRenderCache(self.canvas)
        self.doc = build_village_document(Content.load(DEFAULT_CONTENT))
        self.options = dict(cell_size=32, layers={}, selected_cell=(0, 0),
                            selected_tiles=set())

    def snapshot(self, canvas):
        return [(canvas.type(i), canvas.coords(i),
                 {k: v[-1] for k, v in canvas.itemconfigure(i).items()})
                for i in canvas.find_all()]

    def check_scene(self):
        mission = Content.from_dict(self.doc.data).missions[MISSION_ID]
        geo = self.renderer.draw(mission.board, mission, mission.units, **self.options)
        render_isometric(self.reference, mission.board, mission, mission.units,
                         **self.options)
        self.assertEqual(self.snapshot(self.canvas), self.snapshot(self.reference))
        self.assertEqual(self.canvas.cget('scrollregion'), self.reference.cget('scrollregion'))
        reference_geo = IsoGeometry(mission.board, self.options['cell_size'])
        for cell in ((0, 0), (3, 3), (10, 10)):
            self.assertEqual(geo.hit_test(*geo.center(cell)),
                             reference_geo.hit_test(*geo.center(cell)))
        return geo

    def test_selection_cutaway_layers_and_noop(self):
        self.check_scene()
        ids = self.canvas.find_all()
        self.check_scene()
        self.assertEqual(self.canvas.find_all(), ids)
        self.assertEqual(self.renderer.stats['created'], 0)
        self.assertEqual(self.renderer.stats['updated'], 0)
        self.assertFalse(self.renderer.stats['geometry_rebuilt'])
        for selected in ((3, 3), (4, 4), (20, 3), (0, 0)):
            self.options['selected_cell'] = selected
            self.check_scene()
        self.options['selected_tiles'] = {(x, y) for x in range(12) for y in range(10)}
        self.check_scene()
        for layer in ('Terrain', 'Relief', 'Décors', 'Bâtiments', 'Toitures',
                      'Unités', 'Objets', 'Déploiement', 'Objectifs'):
            self.options['layers'][layer] = False
            self.check_scene()
            self.options['layers'][layer] = True
            self.check_scene()
        self.options['layers'].update({'Bâtiments': False, 'Toitures': False})
        self.check_scene()
        self.options['layers'] = {}
        self.options['selected_tiles'] = set()
        self.check_scene()

    def test_paint_height_zoom_undo_redo_and_mode_reset(self):
        geo = self.check_scene()
        self.doc.paint_many(MISSION_ID, [(10, 10)], 'surface:water')
        self.assertIs(self.check_scene(), geo)
        self.doc.paint_many(MISSION_ID, [(10, 10)], 'height+')
        self.check_scene()
        self.assertTrue(self.renderer.stats['geometry_rebuilt'])
        self.doc.undo()
        self.check_scene()
        self.doc.redo()
        self.check_scene()
        self.options['cell_size'] = 54
        self.check_scene()
        self.assertTrue(self.renderer.stats['geometry_rebuilt'])
        self.renderer.invalidate()
        self.canvas.create_rectangle(0, 0, 10, 10)
        # The flat view invalidates before drawing. Clear its items on return.
        self.check_scene()

    def test_png_atlases_and_roof_cutaway(self):
        self.options.update(atlas=IsoTerrainAtlas(self.canvas),
                            prop_atlas=IsoPropAtlas(self.canvas),
                            building_atlas=IsoBuildingAtlas(self.canvas),
                            fortification_atlas=IsoFortificationAtlas(self.canvas),
                            actor_atlas=IsoActorAtlas(self.canvas))
        self.check_scene()
        self.assertTrue(self.canvas.find_withtag('architecture_sprite'))
        for cell in ((3, 3), (4, 4), (0, 0)):
            self.options['selected_cell'] = cell
            self.check_scene()
        self.options['cell_size'] = 54
        self.check_scene()

    def test_large_scene_fallback_and_return_to_retained(self):
        self.check_scene()
        self.renderer.max_retained_cells = 1
        geo = self.check_scene()
        self.assertEqual(self.renderer.stats['mode'], 'geometry')
        self.assertEqual(self.renderer._items, {})
        self.assertIs(self.check_scene(), geo)
        self.renderer.max_retained_cells = 4096
        self.check_scene()
        self.assertEqual(self.renderer.stats['mode'], 'retained')

    def test_large_noop_and_selection_match_full_canvas(self):
        # Force the exact large-map branch on a small, known scene so
        # complete item/type/coordinate/configuration parity is practical.
        self.renderer.max_retained_cells = 1
        self.check_scene()
        self.assertEqual(self.renderer.stats['fast_path'], 'full')
        original_ids = self.canvas.find_all()

        self.check_scene()
        self.assertEqual(self.renderer.stats['fast_path'], 'noop')
        self.assertEqual(self.canvas.find_all(), original_ids)

        self.options['selected_cell'] = (25, 19)
        self.check_scene()
        self.assertEqual(self.renderer.stats['fast_path'], 'selection')
        self.options['selected_tiles'] = {(0, 0), (12, 10), (25, 19)}
        self.check_scene()
        self.assertEqual(self.renderer.stats['fast_path'], 'selection')

        # An edit in-place must invalidate the scene even when Content and
        # the geometry dimensions remain exactly the same.
        mission = next(m for m in self.doc.data['missions'] if m['id'] == MISSION_ID)
        mission['units'][0]['name'] = 'Repainted unit'
        self.check_scene()
        self.assertEqual(self.renderer.stats['fast_path'], 'full')
        self.doc.paint_many(MISSION_ID, [(10, 10)], 'surface:water')
        self.check_scene()
        self.assertEqual(self.renderer.stats['fast_path'], 'full')
        self.check_scene()
        self.assertEqual(self.renderer.stats['fast_path'], 'noop')

        # Canvas items drawn by other UI code must not survive an unexpected
        # refresh as an undetected cached frame.
        self.canvas.create_rectangle(0, 0, 5, 5, tags='external')
        self.check_scene()
        self.assertEqual(self.renderer.stats['fast_path'], 'full')

    def test_large_selection_crossing_roof_forces_repaint(self):
        self.renderer.max_retained_cells = 1
        self.check_scene()
        buildings = [instance for instance in
                     self.renderer.geometry.architecture_instances
                     if instance.name in ('Maison', 'Tour', 'Ruines')]
        self.assertTrue(buildings)
        building = buildings[0]
        outside = next(cell for cell in self.renderer.geometry.draw_order
                       if cell not in building.cells)
        inside = next(iter(building.cells))
        self.options['selected_cell'] = outside
        self.check_scene()
        self.options['selected_cell'] = inside
        self.check_scene()
        self.assertEqual(self.renderer.stats['fast_path'], 'full')

    def test_actor_and_structure_edits(self):
        self.check_scene()
        mission = next(m for m in self.doc.data['missions'] if m['id'] == MISSION_ID)
        mission['units'][0]['name'] = 'Renamed'
        mission['units'][0]['pos'] = [4, 4]
        self.check_scene()
        mission['structures'] = []
        self.check_scene()
        self.doc.paint_many(MISSION_ID, [(3, 3)], 'surface:grass')
        self.check_scene()


if __name__ == '__main__':
    unittest.main()

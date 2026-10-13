"""Tk contract for 3.7.19C palette (requires Tk/Xvfb, not headless CI)."""
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.entity_placement import palette_entities
from sporebound.iso_actor_atlas import IsoActorAtlas
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_fortification_atlas import IsoFortificationAtlas
from sporebound.iso_map import IsoTerrainAtlas
from sporebound.iso_props import IsoPropAtlas
from sporebound.model import Content
from sporebound.studio_asset_palette import AssetPalette


@unittest.skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
                     'Requires a real Tk display')
class EntityPaletteGuiTests(unittest.TestCase):
    def test_actor_pose_and_facing_object_controls_and_vector_fallback(self):
        import tkinter as tk
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root)
            data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                     'palette_gui', 'Village', 12, 12)
            choices = []
            palette = None

            def choose(entry, turns):
                choices.append((entry.id, turns, palette.placement_settings()))
                return True

            palette = AssetPalette(
                root, terrain=IsoTerrainAtlas(canvas),
                props=IsoPropAtlas(canvas),
                buildings=IsoBuildingAtlas(canvas),
                fortifications=IsoFortificationAtlas(canvas),
                actors=IsoActorAtlas(canvas),
                content=lambda: data, mission=lambda: 'palette_gui',
                entities=lambda: palette_entities(data, 'palette_gui'),
                cell_size=lambda: 54, choose=choose)
            root.update()
            palette.category.set('Acteurs')
            root.update()
            actor = next(entry for entry in palette.entries.values()
                         if entry.id.startswith('actor:unit:'))
            palette.tree.selection_set(actor.id)
            palette.select()
            self.assertFalse(palette.entity_frame.winfo_manager() == '')
            self.assertFalse(palette.rotate_button.instate(['!disabled']))
            palette.entity_team.set('enemy')
            palette.entity_facing.set('north')
            palette.entity_pose.set('move')
            palette.scale.set(54)
            palette.preview()
            self.assertIn('Instance jouable', palette.detail.get())
            self.assertEqual(palette.preview_image.width(), 64)
            palette.use()
            self.assertEqual(choices[-1][2]['facing'], 'north')
            self.assertEqual(choices[-1][2]['team'], 'enemy')
            palette.show()
            palette.category.set('Interactions')
            root.update()
            palette.tree.selection_set('object:switch')
            palette.select()
            self.assertEqual(palette.preview_image, None)
            self.assertIn('Marqueur tactique', palette.detail.get())
            self.assertTrue(palette.entity_rows['Porte liée (ID)'].winfo_manager())
            palette.entity_link.set('gate_main')
            palette.use()
            self.assertEqual(choices[-1][2]['link'], 'gate_main')
            palette.show()
            palette.category.set('Sols')
            root.update()
            self.assertEqual(palette.entity_frame.winfo_manager(), '')
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()

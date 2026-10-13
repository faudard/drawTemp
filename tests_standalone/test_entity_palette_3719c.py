"""3.7.19C — mission actor and interactive-object placement gates."""
import os
from copy import deepcopy
from unittest import TestCase, skipUnless

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.entity_palette import entity_entries, place_entity
from sporebound.model import Content, RuleError


class EntityPaletteTests(TestCase):
    MID = 'entities_3719c'

    def setUp(self):
        raw = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                self.MID, 'Placement', 20, 20)
        self.doc = Document(Content.from_dict(raw))

    def row(self):
        return next(m for m in self.doc.data['missions'] if m['id'] == self.MID)

    def test_existing_actor_is_a_reusable_mission_template(self):
        entries = entity_entries(self.doc.data, self.MID)
        self.assertTrue(any(e.kind == 'actor' for e in entries))
        self.assertTrue(any(e.id == 'object:switch' for e in entries))
        source = self.row()['units'][0]
        self.doc.replace(place_entity(self.doc.data, self.MID,
                                      'actor:' + source['id'], (8, 8),
                                      facing='north'))
        units = self.row()['units']
        copy = units[-1]
        self.assertEqual(copy['id'], 'actor_1')
        self.assertEqual(copy['pos'], [8, 8])
        self.assertEqual(copy['facing'], [0, -1])
        self.assertEqual(copy['team'], source['team'])
        self.assertEqual(copy['weapon'], source['weapon'])
        self.assertEqual(source['pos'], units[0]['pos'])
        self.doc.undo()
        self.assertEqual(len(self.row()['units']), 2)
        self.doc.redo()
        self.assertEqual(len(self.row()['units']), 3)
        self.assertEqual(len(Content.from_dict(self.doc.data).missions[self.MID].units), 3)

    def test_interactive_door_switch_passage_and_unique_ids(self):
        self.doc.replace(place_entity(self.doc.data, self.MID,
                                      'object:door', (8, 8)))
        self.doc.replace(place_entity(self.doc.data, self.MID,
                                      'object:door', (9, 8)))
        self.doc.replace(place_entity(self.doc.data, self.MID,
                                      'object:switch', (7, 8),
                                      link='door_1'))
        self.doc.replace(place_entity(self.doc.data, self.MID,
                                      'object:passage', (6, 8),
                                      destination=(4, 4)))
        objects = self.row()['objects']
        self.assertEqual([o['id'] for o in objects],
                         ['door_1', 'door_2', 'switch_1', 'passage_1'])
        self.assertEqual(objects[2]['link'], 'door_1')
        self.assertEqual(objects[3]['destination'], [4, 4])
        reopened = Content.from_dict(self.doc.data).to_dict()
        self.assertEqual(next(m for m in reopened['missions']
                              if m['id'] == self.MID)['objects'], objects)

    def test_failed_placement_preserves_data_and_history(self):
        before = deepcopy(self.doc.data)
        undo_size = len(self.doc.undo_stack)
        actions = (
            lambda: place_entity(self.doc.data, self.MID, 'object:pot', (6, 6)),
            lambda: place_entity(self.doc.data, self.MID, 'actor:missing', (6, 6)),
            lambda: place_entity(self.doc.data, self.MID, 'object:switch', (6, 6),
                                 link='missing'),
            lambda: place_entity(self.doc.data, self.MID, 'object:chest', (1, 18)),
            lambda: place_entity(self.doc.data, self.MID, 'object:passage', (6, 6)),
            lambda: place_entity(self.doc.data, self.MID, 'object:door', (20, 20)),
        )
        for operation in actions:
            with self.subTest(operation=operation), self.assertRaises(RuleError):
                self.doc.replace(operation())
            self.assertEqual(self.doc.data, before)
            self.assertEqual(len(self.doc.undo_stack), undo_size)


@skipUnless(os.environ.get('SPOREBOUND_GUI_SMOKE') == '1',
            'Requires Tk display or Xvfb')
class EntityPaletteGUITests(TestCase):
    def test_actor_pose_preview_and_link_controls(self):
        import tkinter as tk
        from sporebound.iso_actor_atlas import IsoActorAtlas
        from sporebound.studio_entity_palette import EntityPalette

        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'palette_gui', 'Acteurs', 16, 16)
        root = tk.Tk()
        try:
            stage = tk.Canvas(root, width=100, height=100)
            stage.pack()
            selected = []
            palette = EntityPalette(
                root, snapshot=lambda: (data, 'palette_gui'),
                actors=IsoActorAtlas(stage),
                choose=lambda *values: selected.append(values) or True,
                cell_size=lambda: 54)
            root.update()
            actor_entry = next(e.id for e in palette.entries.values()
                               if e.kind == 'actor')
            palette.tree.selection_set(actor_entry)
            palette.preview()
            palette.facing.set('west')
            palette.moving.set(True)
            palette.preview()
            self.assertEqual(palette.facing.get(), 'west')
            self.assertIsNotNone(palette.preview_image)
            palette.use()
            self.assertEqual(selected[-1][0].id, actor_entry)
            self.assertEqual(selected[-1][1], 'west')
            palette.show()
            palette.tree.selection_set('object:door')
            palette.preview()
            self.assertEqual(palette.facing_box.cget('state'), 'disabled')
            self.assertEqual(palette.link_box.cget('state'), 'disabled')
        finally:
            root.destroy()

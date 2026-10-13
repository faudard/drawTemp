"""3.7.19C — mission actor and interactive-object placement gates."""
import os
from copy import deepcopy
from unittest import TestCase, skipUnless

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.actor_catalog import create_archetype
from sporebound.editor import Document
from sporebound.entity_palette import (entity_entries, place_entity,
                                      preview_entity_placement, preview_passage_source,
                                      OBJECT_PROP_HINTS)
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
        self.assertEqual(tuple(copy['pos']), (8, 8))
        self.assertEqual(tuple(copy['facing']), (0, -1))
        self.assertEqual(copy['team'], source['team'])
        self.assertEqual(copy['weapon'], source['weapon'])
        self.assertEqual(source['pos'], units[0]['pos'])
        self.doc.undo()
        self.assertEqual(len(self.row()['units']), 2)
        self.doc.redo()
        self.assertEqual(len(self.row()['units']), 3)
        self.assertEqual(len(Content.from_dict(self.doc.data).missions[self.MID].units), 3)

    def test_installed_bestiary_archetype_is_directly_placeable(self):
        self.doc.replace(create_archetype(
            self.doc.data, 'forest_wolf', kind='monster', max_hp=28,
            attack=7, speed=13))
        entries = entity_entries(self.doc.data, self.MID)
        entry = next(e for e in entries if e.id == 'archetype:forest_wolf')
        self.assertEqual(entry.kind, 'archetype')
        self.assertEqual(entry.team, 'enemy')
        feedback = preview_entity_placement(
            self.doc.data, self.MID, entry.id, (8, 8), team='player')
        self.assertTrue(feedback.allowed, feedback.reason)
        self.doc.replace(place_entity(self.doc.data, self.MID, entry.id,
                                      (8, 8), facing='east', team='player'))
        unit = self.row()['units'][-1]
        self.assertEqual(unit['archetype'], 'forest_wolf')
        self.assertEqual(unit['team'], 'player')
        self.assertEqual(tuple(unit['pos']), (8, 8))
        self.assertEqual(tuple(unit['facing']), (1, 0))
        self.doc.undo()
        self.assertEqual(len(self.row()['units']), 2)
        with self.assertRaises(RuleError):
            place_entity(self.doc.data, self.MID, entry.id, (8, 8), team='neutral')

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
        self.assertEqual(tuple(objects[3]['destination']), (4, 4))
        reopened = Content.from_dict(self.doc.data).to_dict()
        self.assertEqual(next(m for m in reopened['missions']
                              if m['id'] == self.MID)['objects'], objects)

    def test_hover_preview_is_authoritative_and_immutable(self):
        original = deepcopy(self.doc.data)
        source = self.row()['units'][0]
        actor_id = 'actor:' + source['id']
        good = preview_entity_placement(self.doc.data, self.MID, actor_id, (8, 8))
        self.assertTrue(good.allowed)
        self.assertEqual(good.cells, ((8, 8),))
        self.assertFalse(preview_entity_placement(
            self.doc.data, self.MID, actor_id, tuple(source['pos'])).allowed)
        self.assertFalse(preview_entity_placement(
            self.doc.data, self.MID, 'object:switch', (8, 8),
            link='missing').allowed)
        self.assertFalse(preview_entity_placement(
            self.doc.data, self.MID, 'object:chest', (30, 30)).allowed)
        self.assertEqual(self.doc.data, original)

    def test_visual_object_hints_reuse_existing_prop_atlas(self):
        from sporebound.iso_props import PROP_NAMES
        self.assertEqual(set(OBJECT_PROP_HINTS), {
            'door', 'switch', 'chest', 'ram', 'catapult', 'passage', 'defense'})
        self.assertTrue(set(OBJECT_PROP_HINTS.values()) <= set(PROP_NAMES))

    def test_passage_two_click_checks_and_atomic_commit(self):
        unchanged = deepcopy(self.doc.data)
        source = (8, 8)
        self.assertTrue(preview_passage_source(
            self.doc.data, self.MID, source).allowed)
        self.assertFalse(preview_passage_source(
            self.doc.data, self.MID, (1, 18)).allowed)
        self.assertFalse(preview_passage_source(
            self.doc.data, self.MID, (30, 0)).allowed)
        self.assertEqual(self.doc.data, unchanged, 'First click is not an edit')
        for destination in (source, (30, 0)):
            rejected = preview_entity_placement(
                self.doc.data, self.MID, 'object:passage', source,
                destination=destination)
            self.assertFalse(rejected.allowed)
        checked = preview_entity_placement(
            self.doc.data, self.MID, 'object:passage', source,
            destination=(12, 8))
        self.assertTrue(checked.allowed, checked.reason)
        self.doc.replace(place_entity(
            self.doc.data, self.MID, 'object:passage', source,
            destination=(12, 8)))
        self.assertEqual(self.row()['objects'][-1]['kind'], 'passage')
        self.assertEqual(tuple(self.row()['objects'][-1]['destination']), (12, 8))
        self.doc.undo()
        self.assertEqual(self.doc.data, unchanged)
        self.doc.redo()
        self.assertEqual(self.row()['objects'][-1]['id'], 'passage_1')

    def test_dedicated_png_atlas_metadata(self):
        from struct import unpack
        from sporebound.iso_object_atlas import (
            OBJECT_SPRITE_NAMES, OBJECT_FRAME, DEFAULT_OBJECT_ATLAS)
        self.assertEqual(len(OBJECT_SPRITE_NAMES), 7)
        self.assertEqual(set(OBJECT_SPRITE_NAMES), set(OBJECT_PROP_HINTS))
        data = DEFAULT_OBJECT_ATLAS.read_bytes()
        self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
        width, height = unpack('>II', data[16:24])
        self.assertEqual((width, height),
                         (OBJECT_FRAME[0] * len(OBJECT_SPRITE_NAMES),
                          OBJECT_FRAME[1]))
        self.assertLess(len(data), 100_000)

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
    def test_real_isometric_object_pngs_at_three_zoom_levels(self):
        import tkinter as tk
        from sporebound.iso_map import render_isometric
        from sporebound.iso_object_atlas import IsoObjectAtlas
        raw = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                'object_atlas_gui', 'Objects', 20, 20)
        for kind, cell, extra in (
            ('door', (6, 6), {}),
            ('switch', (7, 6), {'link': 'door_1'}),
            ('chest', (8, 6), {}),
            ('passage', (9, 6), {'destination': (11, 6)}),
            ('defense', (10, 6), {}),
        ):
            raw = place_entity(raw, 'object_atlas_gui',
                               'object:' + kind, cell, **extra)
        root = tk.Tk()
        try:
            canvas = tk.Canvas(root, width=900, height=650)
            canvas.pack()
            root.update()
            atlas = IsoObjectAtlas(canvas)
            for zoom in (24, 54, 96):
                mission = Content.from_dict(raw).missions['object_atlas_gui']
                render_isometric(
                    canvas, mission.board, mission, mission.units,
                    cell_size=zoom, layers={'Objets': True, 'Terrain': True},
                    selected_cell=(0, 0), selected_tiles=(),
                    object_atlas=atlas)
                self.assertEqual(len(canvas.find_withtag('iso_object_sprite')), 5)
                for kind in ('door', 'switch', 'chest', 'passage', 'defense'):
                    image = atlas.sprite(kind, zoom)
                    self.assertIsNotNone(image)
                    self.assertIs(image, atlas.sprite(kind, zoom))
        finally:
            root.destroy()

    def test_actor_pose_preview_and_link_controls(self):
        import tkinter as tk
        from sporebound.iso_actor_atlas import IsoActorAtlas
        from sporebound.iso_props import IsoPropAtlas
        from sporebound.iso_object_atlas import IsoObjectAtlas
        from sporebound.studio_entity_palette import EntityPalette

        data = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                                 'palette_gui', 'Acteurs', 16, 16)
        data = create_archetype(data, 'forest_wolf', kind='monster')
        root = tk.Tk()
        try:
            stage = tk.Canvas(root, width=100, height=100)
            stage.pack()
            selected = []
            palette = EntityPalette(
                root, snapshot=lambda: (data, 'palette_gui'),
                actors=IsoActorAtlas(stage), props=IsoPropAtlas(stage),
                objects=IsoObjectAtlas(stage),
                choose=lambda *values: selected.append(values) or True,
                cell_size=lambda: 54)
            root.update()
            actor_entry = next(e.id for e in palette.entries.values()
                               if e.kind == 'actor')
            self.assertTrue(palette.tree.item(actor_entry, 'image'))
            self.assertTrue(palette.tree.item('object:chest', 'image'))
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
            palette.tree.selection_set('archetype:forest_wolf')
            palette.on_selection()
            self.assertEqual(palette.team_box.cget('state'), 'readonly')
            palette.team.set('player')
            palette.use()
            self.assertEqual(selected[-1][0].id, 'archetype:forest_wolf')
            self.assertEqual(selected[-1][4], 'player')
            palette.show()
            palette.tree.selection_set('object:door')
            palette.preview()
            self.assertIsNotNone(palette.preview_image)
            self.assertEqual(palette.facing_box.cget('state'), 'disabled')
            self.assertEqual(palette.link_box.cget('state'), 'disabled')
        finally:
            root.destroy()

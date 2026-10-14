"""3.7.32C headless gates: layer locks, sparse tiles, sidecar roundtrip."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_structures import place_structure
from sporebound.interior_levels import add_interior_floor
from sporebound.map_layer_workspace import (
    LAYERS, changed_layers, default_view, empty_views, ensure_unlocked,
    load_views, save_views, update_view, view_for, view_sidecar_path)
from sporebound.model import Content, RuleError


class MapLayerWorkspaceTests(unittest.TestCase):
    MID = 'layer_workspace_4c'

    def setUp(self):
        base = Content.load(DEFAULT_CONTENT).to_dict()
        self.data = add_blank_mission(base, self.MID, 'Layer workspace', 16, 16)

    def _doc(self, views):
        doc = Document(Content.from_dict(self.data))
        doc.edit_policy = lambda before, after: ensure_unlocked(before, after, views)
        return doc

    def test_missing_sidecar_defaults_to_noninvasive_view(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'content.json'
            states = load_views(path)
            self.assertEqual(states, empty_views())
            view = view_for(states, self.MID)
            self.assertEqual(set(view['visible']), set(LAYERS))
            self.assertTrue(all(view['visible'].values()))
            self.assertFalse(any(view['locked'].values()))
            self.assertEqual(view['active_level'], 0)
            self.assertEqual(view['projection'], '2d')
            self.assertFalse(view_sidecar_path(path).exists())

    def test_mission_scoped_view_roundtrip_and_deepcopy(self):
        views = update_view(empty_views(), self.MID,
                            visible={'Terrain': False, 'Étages': False},
                            locked={'Bâtiments': True, 'Toitures': True},
                            active_level=2, interiors=True, projection='iso')
        views = update_view(views, 'other_mission',
                            visible={'Objets': False}, active_level=1)
        original = deepcopy(views)
        selected = view_for(views, self.MID)
        selected['locked']['Bâtiments'] = False
        self.assertEqual(views, original)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'map.json'
            save_views(path, views)
            restored = load_views(path)
            self.assertEqual(restored, views)
            self.assertFalse(view_for(restored, self.MID)['visible']['Étages'])
            self.assertTrue(view_for(restored, self.MID)['locked']['Bâtiments'])
            self.assertEqual(view_for(restored, self.MID)['projection'], 'iso')
            self.assertEqual(view_for(restored, 'other_mission')['projection'], '2d')
            self.assertFalse(view_for(restored, 'other_mission')['visible']['Objets'])
            self.assertTrue(view_for(restored, 'other_mission')['visible']['Terrain'])
            self.assertFalse(path.exists())  # Sidecar cannot rewrite gameplay content.

    def test_legacy_v1_sidecar_without_projection_is_migrated_on_read(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'mission.json'
            legacy = update_view(empty_views(), self.MID,
                                 visible={'Terrain': False})
            del legacy['missions'][self.MID]['projection']
            view_sidecar_path(path).write_text(
                json.dumps(legacy), encoding='utf-8')
            loaded = load_views(path)
            self.assertEqual(view_for(loaded, self.MID)['projection'], '2d')
            self.assertFalse(view_for(loaded, self.MID)['visible']['Terrain'])
            self.assertNotIn('projection', legacy['missions'][self.MID])
            self.assertFalse(path.exists())
            save_views(path, loaded)
            self.assertEqual(view_for(load_views(path), self.MID)['projection'], '2d')

    def test_projection_rejects_invalid_modes_without_changing_other_missions(self):
        original = update_view(empty_views(), self.MID, projection='iso')
        for value in ('isometric', '', False, 1):
            with self.subTest(value=value), self.assertRaises(RuleError):
                update_view(original, 'another_mission', projection=value)
        self.assertEqual(view_for(original, self.MID)['projection'], 'iso')
        self.assertEqual(view_for(original, 'another_mission')['projection'], '2d')

    def test_invalid_sidecar_is_rejected_without_modifying_content(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'mission.json'
            path.write_text('game content is preserved', encoding='utf-8')
            viewpath = view_sidecar_path(path)
            viewpath.write_text('{"kind":"unknown"}', encoding='utf-8')
            with self.assertRaises(RuleError):
                load_views(path)
            self.assertEqual(path.read_text(encoding='utf-8'),
                             'game content is preserved')
            with self.assertRaises(RuleError):
                save_views(path, {'kind': 'invalid'})
            self.assertEqual(viewpath.read_text(encoding='utf-8'),
                             '{"kind":"unknown"}')

    def test_invalid_levels_unknown_layers_and_non_boolean_values(self):
        for modification in (
            {'visible': {'Terrain': 0}},
            {'locked': {'UI': True}},
            {'active_level': True},
            {'active_level': 4},
            {'interiors': 'yes'},
        ):
            with self.subTest(modification=modification), self.assertRaises(RuleError):
                update_view(empty_views(), self.MID, **modification)

    def test_terrain_lock_rejects_without_history_but_decor_edit_succeeds(self):
        views = update_view(empty_views(), self.MID, locked={'Terrain': True})
        doc = self._doc(views)
        history = len(doc.undo_stack)
        before = deepcopy(doc.data)
        with self.assertRaisesRegex(RuleError, 'Terrain'):
            doc.paint_many(self.MID, [(4, 4)], 'surface:cobble')
        self.assertEqual(doc.data, before)
        self.assertEqual(len(doc.undo_stack), history)
        doc.paint_many(self.MID, [(4, 4)], 'feature:tree')
        self.assertEqual(len(doc.undo_stack), history + 1)
        self.assertEqual(Content.from_dict(doc.data).missions[self.MID].board.tile((4, 4)).feature, 'tree')
        doc.undo()  # Locks should not disable undo/redo.
        self.assertEqual(doc.data, before)
        doc.redo()

    def test_height_and_decor_locks_are_independent_of_terrain(self):
        views = update_view(empty_views(), self.MID,
                            locked={'Relief': True, 'Décors': True})
        doc = self._doc(views)
        doc.paint_many(self.MID, [(5, 5)], 'surface:stone')
        initial = deepcopy(doc.data)
        for brush in ('height+', 'feature:tree', 'wall'):
            # 'wall' only changes blocked and is a legal terrain operation.
            if brush == 'wall':
                doc.paint_many(self.MID, [(5, 5)], brush)
                break
            with self.assertRaises(RuleError):
                doc.paint_many(self.MID, [(5, 5)], brush)
        self.assertEqual(Content.from_dict(doc.data).missions[self.MID].board.tile((5, 5)).height, 0)
        self.assertEqual(Content.from_dict(doc.data).missions[self.MID].board.tile((5, 5)).feature, '')

    def test_structure_and_floor_locks_are_isolated(self):
        with_house = place_structure(self.data, self.MID, 'Maison', (4, 4))
        doc = Document(Content.from_dict(with_house))
        views = update_view(empty_views(), self.MID,
                            locked={'Bâtiments': True})
        doc.edit_policy = lambda before, after: ensure_unlocked(before, after, views)
        previous = deepcopy(doc.data)
        with self.assertRaisesRegex(RuleError, 'Bâtiments'):
            doc.replace(place_structure(doc.data, self.MID, 'Tour', (9, 4)))
        self.assertEqual(doc.data, previous)
        self.assertFalse(doc.undo_stack)
        sid = next(m for m in doc.data['missions'] if m['id'] == self.MID)['structures'][0]['id']
        # Existing house's interior uses the separate Étages layer.
        doc.replace(add_interior_floor(doc.data, self.MID, sid, 1))
        self.assertEqual(len(doc.undo_stack), 1)
        views = update_view(views, self.MID,
                            locked={'Bâtiments': False, 'Étages': True})
        previous = deepcopy(doc.data)
        with self.assertRaisesRegex(RuleError, 'Étages'):
            doc.replace(add_interior_floor(doc.data, self.MID, sid, 2))
        self.assertEqual(doc.data, previous)

    def test_locked_roof_detects_customization_without_parallel_model(self):
        source = deepcopy(self.data)
        other = deepcopy(source)
        first = next(m for m in source['missions'] if m['id'] == self.MID)
        second = next(m for m in other['missions'] if m['id'] == self.MID)
        first['structures'] = [{'id': 's1', 'appearance': {'roof': 'tuiles'}}]
        second['structures'] = [{'id': 's1', 'appearance': {'roof': 'ardoise'}}]
        self.assertIn('Toitures', changed_layers(source, other)[self.MID])
        views = update_view(empty_views(), self.MID, locked={'Toitures': True})
        with self.assertRaisesRegex(RuleError, 'Toitures'):
            ensure_unlocked(source, other, views)

    def test_visibility_never_modifies_content_or_disables_editing(self):
        views = update_view(empty_views(), self.MID,
                            visible={'Terrain': False, 'Bâtiments': False,
                                     'Étages': False}, active_level=0)
        doc = self._doc(views)
        doc.paint_many(self.MID, [(4, 4)], 'surface:stone')
        self.assertEqual(Content.from_dict(doc.data).missions[self.MID].board.tile((4, 4)).surface,
                         'stone')
        self.assertFalse(view_for(views, self.MID)['visible']['Terrain'])


if __name__ == '__main__':
    unittest.main()

"""3.7.20B: authored multi-deck interiors, compatibility and deterministic replay."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.interior_levels import (
    add_interior_floor, delete_interior_floor, edit_interior_tile,
    floor_absolute_cells, floor_hit_test, projected_floor_polygon)
from sporebound.iso_architecture import architecture_instances, draw_architecture
from sporebound.iso_map import IsoGeometry
from sporebound.iso_structures import place_structure, remove_structure
from sporebound.model import Content, RuleError


class StackedInteriorTests(unittest.TestCase):
    MID = 'stacked_interiors_3720b'

    def setUp(self):
        content = Content.load(DEFAULT_CONTENT)
        data = add_blank_mission(content.to_dict(), self.MID,
                                 'Maisons superposées', 16, 16)
        self.doc = Document(Content.from_dict(data))
        self.doc.replace(place_structure(
            self.doc.data, self.MID, 'Maison', (3, 3)))
        self.sid = self.scene().structures[0]['id']

    def scene(self):
        return Content.from_dict(self.doc.data).missions[self.MID]

    def create(self, level=1):
        self.doc.replace(add_interior_floor(
            self.doc.data, self.MID, self.sid, level))

    def test_two_decks_have_stable_local_cells_and_are_serialized(self):
        self.create(1)
        self.create(2)
        scene = self.scene()
        self.assertEqual([f['level'] for f in scene.interior_floors], [1, 2])
        self.assertEqual(len(scene.interior_floors[0]['tiles']), 4)
        data = deepcopy(self.doc.data)
        self.assertEqual(Content.from_dict(data).to_dict(), data)
        self.doc.undo()
        self.assertEqual(len(self.scene().interior_floors), 1)
        self.doc.redo()
        self.assertEqual(self.doc.data, data)
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'mission.json'
            self.doc.save(path)
            reopened = Content.load(path)
            self.assertEqual(reopened.to_dict(), data)

    def test_floor_changes_leave_ground_combat_state_unchanged(self):
        before = self.doc.playtest(self.MID, seed=22).digest()
        ground = deepcopy(self.scene().board.tiles)
        self.create()
        self.doc.replace(edit_interior_tile(
            self.doc.data, self.MID, self.sid, 1, (4, 4),
            surface='cobble', feature='crate'))
        self.doc.replace(edit_interior_tile(
            self.doc.data, self.MID, self.sid, 1, (5, 4), present=False))
        scene = self.scene()
        tiles = scene.interior_floors[0]['tiles']
        self.assertIn({'pos': [1, 1], 'surface': 'cobble',
                       'feature': 'crate'}, tiles)
        self.assertNotIn([2, 1], [tile['pos'] for tile in tiles])
        self.assertEqual(scene.board.tiles, ground)
        self.assertEqual(self.doc.playtest(self.MID, seed=22).digest(), before)
        self.doc.replace(edit_interior_tile(
            self.doc.data, self.MID, self.sid, 1, (5, 4), present=True))
        self.assertIn([2, 1], [tile['pos'] for tile in self.scene().interior_floors[0]['tiles']])

    def test_invalid_edits_reject_atomically(self):
        self.create()
        before = deepcopy(self.doc.data)
        for action in (
            lambda: add_interior_floor(before, self.MID, self.sid, 1),
            lambda: add_interior_floor(before, self.MID, self.sid, 4),
            lambda: edit_interior_tile(before, self.MID, self.sid, 1,
                                       (15, 15), feature='crate'),
            lambda: edit_interior_tile(before, self.MID, self.sid, 1,
                                       (4, 4), feature='fire'),
            lambda: edit_interior_tile(before, self.MID, self.sid, 2,
                                       (4, 4), feature='crate'),
        ):
            with self.subTest(action=action), self.assertRaises(RuleError):
                action()
        self.assertEqual(self.doc.data, before)

    def test_schema_rejects_orphan_duplicate_and_outside_tiles(self):
        self.create()
        original = deepcopy(self.doc.data)
        for mutate in (
            lambda floor: floor.update(structure_id='missing'),
            lambda floor: floor.update(level=0),
            lambda floor: floor['tiles'].append(deepcopy(floor['tiles'][0])),
            lambda floor: floor['tiles'][0].update(pos=[99, 99]),
            lambda floor: floor['tiles'][0].update(surface='water'),
        ):
            data = deepcopy(original)
            floor = next(m for m in data['missions'] if m['id'] == self.MID)['interior_floors'][0]
            mutate(floor)
            with self.subTest(floor=floor), self.assertRaises(RuleError):
                Content.from_dict(data)

    def test_structure_deletion_cascades_upper_decks(self):
        self.create(1)
        self.create(2)
        self.doc.replace(remove_structure(self.doc.data, self.MID, (4, 4)))
        self.assertEqual(self.scene().structures, [])
        self.assertEqual(self.scene().interior_floors, [])
        self.doc.undo()
        self.assertEqual(len(self.scene().interior_floors), 2)

    def test_raised_projection_and_hole_hit_test(self):
        self.create()
        scene = self.scene()
        building = architecture_instances(scene.board, scene.structures)[0]
        geometry = IsoGeometry(scene.board, 54)
        floor = scene.interior_floors[0]
        cell = (4, 4)
        corners = projected_floor_polygon(geometry, cell, 1)
        center = tuple(sum(p[i] for p in corners) / 4 for i in (0, 1))
        self.assertEqual(floor_hit_test(geometry, building, floor, *center), cell)
        self.doc.replace(edit_interior_tile(
            self.doc.data, self.MID, self.sid, 1, cell, present=False))
        hole = self.scene().interior_floors[0]
        # Hole is still pickable for restoration.
        self.assertEqual(floor_hit_test(geometry, building, hole, *center), cell)
        self.assertIsNone(floor_hit_test(geometry, building, hole, -9999, -9999))

    def test_selected_deck_is_visible_but_not_part_of_battle(self):
        self.create(1)
        self.create(2)
        scene = self.scene()
        geometry = IsoGeometry(scene.board, 54)
        canvas = MagicMock()
        draw_architecture(
            canvas, geometry, scene.board, [], None,
            {'Bâtiments': True, 'Toitures': True, 'Intérieurs': True,
             'Étage actif': 2},
            structures=scene.structures,
            interior_floors=scene.interior_floors)
        self.assertGreater(canvas.create_polygon.call_count, 0)
        self.assertTrue(any('architecture_floor_2' in call.kwargs.get('tags', ())
                            for call in canvas.create_polygon.call_args_list))
        self.assertTrue(any('architecture_floor_1' in call.kwargs.get('tags', ())
                            for call in canvas.create_polygon.call_args_list))


if __name__ == '__main__':
    unittest.main()

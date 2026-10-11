"""3.7.12: atomic multi-cell structures, rotations and legacy compatibility."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import Document
from sporebound.iso_structures import (
    STRUCTURE_NAMES, place_structure, structure_footprint,
    structure_template, validate_structure_placement)
from sporebound.model import Content, RuleError


class StructureAuthoringTests(unittest.TestCase):
    def setUp(self):
        original = Content.load(DEFAULT_CONTENT).to_dict()
        self.mid = 'structure_sandbox'
        self.doc = Document(Content.from_dict(add_blank_mission(
            original, self.mid, 'Construction', 12, 12)))

    def mission(self):
        return next(m for m in self.doc.data['missions'] if m['id'] == self.mid)

    def board(self):
        return Content.from_dict(self.doc.data).missions[self.mid].board

    def test_catalogue_rotations_and_terrain_contracts(self):
        self.assertEqual(set(STRUCTURE_NAMES),
                         {'Maison', 'Tour', 'Rempart', 'Escalier', 'Pont', 'Ruines'})
        for name in STRUCTURE_NAMES:
            original = structure_template(name)
            self.assertEqual(len(original.offsets),
                             original.width * original.height)
            self.assertEqual(original.goals, ())
            self.assertEqual(len(set(original.offsets)), len(original.offsets))
            rotated = structure_template(name, 1)
            self.assertEqual((rotated.width, rotated.height),
                             (original.height, original.width))
            self.assertEqual(
                structure_template(name, 2).width, original.width)
            self.assertEqual(
                structure_template(name, 3).height, original.width)
            self.assertEqual(
                sorted((tuple(sorted(tile.items())) for tile
                        in structure_template(name, 3).terrain)),
                sorted((tuple(sorted(tile.items())) for tile
                        in original.terrain)))
        self.assertEqual(structure_template('Escalier', 0).height, 4)
        for name, turns in [('???', 0), ('Maison', True), ('Maison', -1),
                            ('Maison', 4)]:
            with self.subTest(name=name, turns=turns), self.assertRaises(RuleError):
                structure_template(name, turns)

    def test_maison_has_walkable_entrance_and_saves_with_single_undo(self):
        before = deepcopy(self.doc.data)
        original_stack = len(self.doc.undo_stack)
        new = place_structure(self.doc.data, self.mid, 'Maison', (3, 3))
        self.assertEqual(before, self.doc.data)
        self.doc.replace(new)
        self.assertEqual(len(self.doc.undo_stack), original_stack + 1)
        board = self.board()
        self.assertTrue(board.tile((3, 3)).blocked)
        self.assertEqual(board.tile((3, 3)).feature, 'stone_wall')
        self.assertFalse(board.tile((4, 5)).blocked)  # The entrance
        self.assertEqual(board.tile((4, 5)).surface, 'cobble')
        self.assertEqual(board.tile((4, 4)).surface, 'stone')
        self.assertEqual(board.tile((7, 5)).surface, 'grass')
        self.doc.undo()
        self.assertEqual(before, self.doc.data)
        self.doc.redo()
        self.assertTrue(self.board().tile((3, 3)).blocked)

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'structures.json'
            self.doc.save(path)
            reopened = Content.load(path)
            self.assertEqual(reopened.missions[self.mid].board.tile((4, 5)).surface,
                             'cobble')
            self.assertFalse(reopened.missions[self.mid].board.tile((4, 5)).blocked)
            payload = json.loads(path.read_text(encoding='utf-8'))
            tile = next(t for t in payload['missions'][-1]['board']['tiles']
                        if t['pos'] == [4, 5])
            self.assertNotIn('structure_id', tile)

    def test_rempart_rotation_and_stairs_preserve_other_tiles(self):
        before = deepcopy(self.doc.data)
        rotated = structure_template('Rempart', 1)
        self.assertEqual((rotated.width, rotated.height), (1, 5))
        self.assertEqual(structure_footprint(rotated, (3, 3)),
                         tuple((3, y) for y in range(3, 8)))
        self.doc.replace(place_structure(self.doc.data, self.mid,
                                         'Rempart', (3, 3), 1))
        self.assertTrue(all(self.board().tile((3, y)).blocked
                            for y in range(3, 8)))
        self.doc.replace(place_structure(self.doc.data, self.mid,
                                         'Escalier', (5, 3)))
        heights = [[self.board().tile((x, y)).height for x in (5, 6)]
                   for y in range(3, 7)]
        self.assertEqual(heights, [[0, 0], [1, 1], [2, 2], [3, 3]])
        self.assertEqual(self.board().tile((4, 4)).surface, 'grass')
        self.doc.undo()
        self.doc.undo()
        self.assertEqual(before, self.doc.data)

    def test_collision_and_boundary_fail_without_modification(self):
        self.doc.paint_many(self.mid, [(8, 8)], 'goal')
        before = deepcopy(self.doc.data)
        undo, redo = deepcopy(self.doc.undo_stack), deepcopy(self.doc.redo_stack)
        player = next(u for u in self.mission()['units'] if u['team'] == 'player')
        for name, pos in [('Maison', (11, 11)), ('Rempart', (1, 10)),
                          ('Maison', tuple(player['pos'])), ('Pont', (8, 8)),
                          ('Tour', (6, 6))]:
            if name == 'Tour' and pos == (6, 6):
                # Valid placement, checked separately below.
                continue
            with self.subTest(name=name, pos=pos), self.assertRaises(RuleError):
                place_structure(self.doc.data, self.mid, name, pos)
            self.assertEqual(self.doc.data, before)
            self.assertEqual(self.doc.undo_stack, undo)
            self.assertEqual(self.doc.redo_stack, redo)
        clip = structure_template('Pont')
        for anchor in [(True, 4), (-1, 0), ('4', 4), (11, 3)]:
            with self.subTest(anchor=anchor), self.assertRaises(RuleError):
                validate_structure_placement(self.doc.data, self.mid, clip, anchor)

    def test_object_overlap_and_deployment_are_rejected(self):
        with_obj = add_object(self.doc.data, self.mid,
                              'crates', 'chest', (5, 5))
        self.doc.replace(with_obj)
        before = deepcopy(self.doc.data)
        with self.assertRaises(RuleError):
            place_structure(self.doc.data, self.mid, 'Maison', (4, 4))
        self.assertEqual(self.doc.data, before)
        from sporebound.map_authoring import paint_deployment
        self.doc.replace(paint_deployment(self.doc.data, self.mid,
                                          'attackers', [(4, 4)]))
        # A rempart in the authored spawn zone must not invalidate deployment.
        with self.assertRaises(RuleError):
            place_structure(self.doc.data, self.mid, 'Rempart', (4, 4))
        bridge = structure_template('Pont')
        self.assertTrue(bridge.terrain)
        self.assertTrue(all(not t['blocked'] for t in bridge.terrain))


if __name__ == '__main__':
    unittest.main()

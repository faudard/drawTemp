"""Map Editor 3.0 headless contracts: clipboard, zoning and atomic edits."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission, add_object
from sporebound.editor import Document
from sporebound.map_authoring import (cells_in_rectangle, copy_terrain,
                                     move_object, move_unit, paint_deployment,
                                     paste_terrain, selected_cells)
from sporebound.model import Content, RuleError


class MapAuthoringTests(unittest.TestCase):
    def setUp(self):
        from sporebound.model import Content
        base = Content.load(DEFAULT_CONTENT).to_dict()
        self.data = add_blank_mission(base, 'castle_canvas', 'Assaut — brouillon', 12, 12)
        self.mid = 'castle_canvas'

    def mission(self, data):
        return Content.from_dict(data).missions[self.mid]

    def test_rectangle_and_selection_are_canonical(self):
        cells = cells_in_rectangle(self.data, self.mid, (3, 4), (2, 2))
        self.assertEqual(len(cells), 6)
        self.assertEqual(cells[0], (2, 2))
        self.assertEqual(cells[-1], (3, 4))
        self.assertEqual(selected_cells(self.data, self.mid,
                                        [(3, 3), (2, 2), (2, 2)]),
                         ((2, 2), (3, 3)))
        for invalid in ([(-1, 0)], [(True, 2)], [(12, 0)], []):
            with self.subTest(invalid=invalid), self.assertRaises(RuleError):
                selected_cells(self.data, self.mid, invalid)

    def test_sparse_clipboard_snapshots_terrain_and_goals(self):
        doc = Document(Content.from_dict(self.data))
        doc.paint_many(self.mid, [(2, 2)], 'hazard')
        doc.paint_many(self.mid, [(3, 3)], 'height+')
        doc.paint_many(self.mid, [(3, 3)], 'goal')
        before = deepcopy(doc.data)
        selection = [(2, 2), (3, 3)]
        copied = copy_terrain(doc.data, self.mid, selection)
        self.assertEqual((copied.width, copied.height), (2, 2))
        updated = paste_terrain(doc.data, self.mid, copied, (6, 6))
        self.assertEqual(doc.data, before)
        board = self.mission(updated).board
        self.assertEqual(board.tile((6, 6)).hazard, 4)
        self.assertEqual(board.tile((7, 7)).height, 1)
        self.assertEqual(board.tile((7, 6)).height, 0)
        self.assertIn((7, 7), self.mission(updated).goal)
        self.assertIn((3, 3), self.mission(updated).goal)
        # Mutating the source after copying does not alter clipboard contents.
        doc.paint_many(self.mid, [(2, 2)], 'erase')
        repeated = paste_terrain(doc.data, self.mid, copied, (8, 8))
        self.assertEqual(self.mission(repeated).board.tile((8, 8)).hazard, 4)

    def test_paste_replaces_only_footprint_and_is_single_undo(self):
        doc = Document(Content.from_dict(self.data))
        doc.paint_many(self.mid, [(2, 2)], 'cover')
        clipboard = copy_terrain(doc.data, self.mid, [(2, 2)])
        doc.paint_many(self.mid, [(6, 6)], 'hazard')
        previous = deepcopy(doc.data)
        doc.replace(paste_terrain(doc.data, self.mid, clipboard, (6, 6)))
        self.assertEqual(self.mission(doc.data).board.tile((6, 6)).cover, 20)
        self.assertEqual(self.mission(doc.data).board.tile((6, 6)).hazard, 0)
        doc.undo()
        self.assertEqual(doc.data, previous)
        doc.redo()
        self.assertEqual(self.mission(doc.data).board.tile((6, 6)).cover, 20)

    def test_paste_rejects_boundary_and_illegal_blocking_without_mutating(self):
        doc = Document(Content.from_dict(self.data))
        doc.paint_many(self.mid, [(2, 2)], 'wall')
        copied = copy_terrain(doc.data, self.mid, [(2, 2), (3, 3)])
        before = deepcopy(doc.data)
        for target in ((11, 11), (1, 10), (-1, 0), (True, 2)):
            with self.subTest(target=target), self.assertRaises(RuleError):
                paste_terrain(doc.data, self.mid, copied, target)
            self.assertEqual(doc.data, before)

    def test_unit_and_object_repositioning_validated(self):
        mission = self.mission(self.data)
        uid = next(u.id for u in mission.units if u.team == 'player')
        moved = move_unit(self.data, self.mid, uid, (3, 6))
        self.assertEqual(next(u.pos for u in self.mission(moved).units if u.id == uid),
                         (3, 6))
        original = deepcopy(self.data)
        enemy_cell = next(u.pos for u in mission.units if u.team == 'enemy')
        with self.assertRaises(RuleError):
            move_unit(self.data, self.mid, uid, enemy_cell)
        self.assertEqual(self.data, original)
        new = add_object(self.data, self.mid, 'supply', 'chest', (4, 4))
        updated = move_object(new, self.mid, 'supply', (5, 5))
        self.assertEqual(next(o for o in self.mission(updated).objects
                              if o['id'] == 'supply')['pos'], [5, 5])
        self.assertEqual(next(o for o in self.mission(new).objects
                              if o['id'] == 'supply')['pos'], [4, 4])
        with self.assertRaises(RuleError):
            move_object(new, self.mid, 'supply', (12, 12))

    def test_deployment_zone_preserves_spawns_and_rejects_blocking(self):
        before = deepcopy(self.data)
        updated = paint_deployment(self.data, self.mid, 'attackers', [(3, 6)])
        zone = self.mission(updated).deployment[0]
        self.assertIn([3, 6], zone['cells'])
        self.assertIn([1, 10], zone['cells'])
        self.assertEqual(self.data, before)
        with self.assertRaises(RuleError):
            paint_deployment(updated, self.mid, 'attackers', [(1, 10)], erase=True)
        self.assertEqual(self.data, before)
        updated = paint_deployment(updated, self.mid, 'attackers', [(3, 6)], erase=True)
        self.assertNotIn([3, 6], self.mission(updated).deployment[0]['cells'])
        updated = paint_deployment(updated, self.mid, 'attackers', [(1, 10)], erase=True)
        self.assertEqual(self.mission(updated).deployment, [])

    def test_deployment_rejects_cells_on_walls(self):
        doc = Document(Content.from_dict(self.data))
        doc.paint_many(self.mid, [(5, 5)], 'wall')
        snapshot = deepcopy(doc.data)
        with self.assertRaises(RuleError):
            paint_deployment(doc.data, self.mid, 'attackers', [(5, 5)])
        self.assertEqual(snapshot, doc.data)


if __name__ == '__main__':
    unittest.main()

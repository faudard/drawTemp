"""3.7.32E: conservative dirty terrain planner on valid Content."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.editor_dirty_tiles import affected_terrain_cells
from sporebound.iso_map import IsoGeometry
from sporebound.model import Content


class DirtyTilePlannerTests(unittest.TestCase):
    def scene(self, size=128):
        raw = add_blank_mission(
            Content.load(DEFAULT_CONTENT).to_dict(), 'dirty_map',
            'Terrain', size, size)
        doc = Document(Content.from_dict(raw))
        return doc, Content.from_dict(doc.data).missions['dirty_map']

    def affected(self, before, after):
        geo = IsoGeometry(before.board, 54)
        geo.architecture_instances = ()
        return affected_terrain_cells(before, after, geometry=geo)

    def test_one_tile_and_neighbors_all_map_sizes(self):
        for size in (32, 64, 128):
            with self.subTest(size=size):
                doc, before = self.scene(size)
                doc.paint_many('dirty_map', [(10, 10)], 'surface:water')
                after = Content.from_dict(doc.data).missions['dirty_map']
                self.assertEqual(self.affected(before, after), {
                    (x, y) for x in (9, 10, 11)
                    for y in (9, 10, 11)})
                self.assertNotEqual(before.board.tile((10, 10)),
                                    after.board.tile((10, 10)))
                # A repeated identical paint does not need a redraw.
                self.assertEqual(self.affected(after, after), frozenset())

    def test_border_clipping_multi_tile_union(self):
        doc, before = self.scene()
        doc.paint_many('dirty_map', [(0, 0), (1, 0)], 'surface:water')
        after = Content.from_dict(doc.data).missions['dirty_map']
        affected = self.affected(before, after)
        self.assertEqual(affected, {
            (x, y) for x in range(3) for y in range(2)})

    def test_undo_redo_and_non_visual_changes(self):
        doc, old = self.scene()
        doc.paint_many('dirty_map', [(7, 7)], 'surface:water')
        painted = Content.from_dict(doc.data).missions['dirty_map']
        doc.undo()
        restored = Content.from_dict(doc.data).missions['dirty_map']
        self.assertEqual(self.affected(painted, restored),
                         {(x, y) for x in (6, 7, 8) for y in (6, 7, 8)})
        doc.redo()
        repainted = Content.from_dict(doc.data).missions['dirty_map']
        self.assertEqual(self.affected(restored, repainted),
                         {(x, y) for x in (6, 7, 8) for y in (6, 7, 8)})

    def test_depth_occlusion_and_large_edits_force_full_repaint(self):
        doc, old = self.scene()
        doc.paint_many('dirty_map', [(10, 10)], 'height+')
        raised = Content.from_dict(doc.data).missions['dirty_map']
        self.assertIsNone(self.affected(old, raised))
        doc.undo()
        doc.paint_many('dirty_map', [(10, 10)], 'feature:tree')
        with_prop = Content.from_dict(doc.data).missions['dirty_map']
        self.assertEqual(self.affected(old, with_prop),
                         {(x, y) for x in (9, 10, 11)
                          for y in (9, 10, 11)})
        doc.undo()
        doc.paint_many('dirty_map', [(x, 12) for x in range(50)],
                       'surface:water')
        many = Content.from_dict(doc.data).missions['dirty_map']
        self.assertIsNone(self.affected(old, many))
        actor = deepcopy(old)
        actor.units.append(
            Content.load(DEFAULT_CONTENT).missions['garden'].units[0])
        self.assertIsNone(self.affected(old, actor))
        geo = IsoGeometry(old.board, 54)
        geo.architecture_instances = (object(),)
        self.assertIsNone(affected_terrain_cells(old, old, geometry=geo))

    def test_geometry_identity_guards_stale_render_state(self):
        doc, old = self.scene()
        doc.paint_many('dirty_map', [(4, 4)], 'surface:water')
        new = Content.from_dict(doc.data).missions['dirty_map']
        wrong = IsoGeometry(new.board, 54)
        self.assertIsNone(
            affected_terrain_cells(old, new, geometry=wrong))


if __name__ == '__main__':
    unittest.main()

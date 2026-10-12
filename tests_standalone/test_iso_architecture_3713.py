"""3.7.13 buildings: derived facade detection, roof cutaway, door/pivot safety."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.iso_architecture import (
    ARCHITECTURE_NAMES, PIVOTS, architecture_instances, architecture_outline,
    draw_architecture, placement_origin, roof_cutaway)
from sporebound.iso_map import IsoGeometry
from sporebound.iso_structures import (
    door_slots, place_structure, structure_template)
from sporebound.model import Content, RuleError


class FakeCanvas:
    def __init__(self):
        self.items = []

    def create_polygon(self, *points, **options):
        self.items.append(('polygon', options))
        return len(self.items)

    def create_line(self, *points, **options):
        self.items.append(('line', options))
        return len(self.items)

    def create_rectangle(self, *points, **options):
        self.items.append(('rectangle', options))
        return len(self.items)

    def create_oval(self, *points, **options):
        self.items.append(('oval', options))
        return len(self.items)

    def tag_raise(self, *args):
        self.items.append(('raise', {'tags': args}))

    def count_tag(self, tag):
        return sum(tag in options.get('tags', ()) for _, options in self.items)


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        source = Content.load(DEFAULT_CONTENT).to_dict()
        self.mid = 'architectural_test'
        self.doc = Document(Content.from_dict(add_blank_mission(
            source, self.mid, 'Toitures', 12, 12)))

    def board(self):
        return Content.from_dict(self.doc.data).missions[self.mid].board

    def test_legacy_map_has_no_inferred_roofs(self):
        self.assertEqual(architecture_instances(self.board()), ())
        self.assertEqual(PIVOTS, ('Coin', 'Centre', 'Porte'))
        self.assertEqual(ARCHITECTURE_NAMES, ('Maison', 'Tour', 'Ruines'))

    def test_house_and_tower_are_recognized_after_save_reload(self):
        self.doc.replace(place_structure(self.doc.data, self.mid,
                                         'Maison', (3, 3), door_slot=1))
        houses = architecture_instances(self.board())
        self.assertEqual(len(houses), 1)
        house = houses[0]
        self.assertEqual((house.name, house.anchor, house.entry),
                         ('Maison', (3, 3), (5, 5)))
        self.assertEqual(house.door_slot, 1)
        self.assertEqual(len(house.cells), 12)
        geo = IsoGeometry(self.board(), 54)
        corners, peak = architecture_outline(geo, house)
        self.assertEqual(len(corners), 4)
        self.assertLess(peak[1], max(point[1] for point in corners))

        with TemporaryDirectory() as tmp:
            target = Path(tmp) / 'reopen.json'
            self.doc.save(target)
            reopened = Content.load(target).missions[self.mid].board
            self.assertEqual(architecture_instances(reopened), houses)
            self.assertEqual(reopened.tile((5, 5)).surface, 'cobble')

    def test_rotated_house_pivot_follows_door_and_center(self):
        clip = structure_template('Maison', 1, door_slot=1)
        self.assertEqual((clip.width, clip.height), (3, 4))
        self.assertEqual(placement_origin(clip, (8, 8), 'Coin'), (8, 8))
        self.assertEqual(placement_origin(clip, (8, 8), 'Centre'), (7, 7))
        entry = next(pos for pos, tile in zip(clip.offsets, clip.terrain)
                     if tile.get('surface') == 'cobble')
        expected_anchor = (8-entry[0], 8-entry[1])
        self.assertEqual(placement_origin(clip, (8, 8), 'Porte'),
                         expected_anchor)
        self.doc.replace(place_structure(self.doc.data, self.mid,
                                         'Maison', (3, 3), 1, door_slot=1))
        instances = architecture_instances(self.board())
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].entry,
                         (3+entry[0], 3+entry[1]))

    def test_cutaway_shows_selected_cell_or_occupied_unit(self):
        self.doc.replace(place_structure(self.doc.data, self.mid,
                                         'Maison', (3, 3)))
        instance = architecture_instances(self.board())[0]
        self.assertFalse(roof_cutaway(instance, (0, 0), ()))
        self.assertTrue(roof_cutaway(instance, (4, 4), ()))
        actor = SimpleNamespace(pos=(4, 4), footprint=(1, 1), alive=True)
        self.assertTrue(roof_cutaway(instance, (0, 0), (actor,)))
        actor.alive = False
        self.assertFalse(roof_cutaway(instance, (0, 0), (actor,)))

        geo = IsoGeometry(self.board(), 54)
        canvas = FakeCanvas()
        draw_architecture(canvas, geo, self.board(), (), (0, 0),
                          {'Bâtiments': True, 'Toitures': True})
        self.assertGreater(canvas.count_tag('architecture_roof'), 0)
        self.assertGreater(canvas.count_tag('architecture_door'), 0)
        self.assertEqual(canvas.count_tag('architecture_cutaway'), 0)
        self.assertEqual(canvas.items[-1], ('raise', {'tags': ('selection',)}))

        canvas = FakeCanvas()
        draw_architecture(canvas, geo, self.board(), (actor,), (4, 4),
                          {'Bâtiments': True, 'Toitures': True})
        self.assertEqual(canvas.count_tag('architecture_roof'), 0)
        self.assertGreater(canvas.count_tag('architecture_cutaway'), 0)

        canvas = FakeCanvas()
        draw_architecture(canvas, geo, self.board(), (), (0, 0),
                          {'Bâtiments': False, 'Toitures': False})
        self.assertFalse(canvas.items)

    def test_editing_stamped_wall_removes_derived_roof_without_new_schema(self):
        self.doc.replace(place_structure(self.doc.data, self.mid,
                                         'Maison', (3, 3)))
        self.assertEqual(len(architecture_instances(self.board())), 1)
        self.doc.paint_many(self.mid, [(3, 3)], 'feature-erase')
        self.assertEqual(architecture_instances(self.board()), ())
        self.doc.undo()
        self.assertEqual(len(architecture_instances(self.board())), 1)

    def test_door_variant_and_invalid_pivot_reject_cleanly(self):
        self.assertEqual(len(door_slots('Maison')), 2)
        self.assertEqual(len(door_slots('Tour')), 1)
        self.assertEqual(len(door_slots('Rempart')), 1)
        for value in ('Porte', 'Coin', 'Centre'):
            self.assertIn(value, PIVOTS)
        clip = structure_template('Rempart')
        for cursor, pivot in [((3, 3), 'Porte'), ((True, 3), 'Coin'),
                              ((3, 3), 'East')]:
            with self.subTest(pivot=pivot), self.assertRaises(RuleError):
                placement_origin(clip, cursor, pivot)
        before = deepcopy(self.doc.data)
        with self.assertRaises(RuleError):
            place_structure(self.doc.data, self.mid, 'Tour', (3, 3),
                            door_slot=1)
        self.assertEqual(self.doc.data, before)


if __name__ == '__main__':
    unittest.main()

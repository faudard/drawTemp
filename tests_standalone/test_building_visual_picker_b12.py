"""B1.2 picking contract: only rendered canonical building parts are selectable."""
import unittest

from sporebound.building_visual_picker import pick_building_part
from sporebound.iso_architecture import ArchitectureInstance


class _Canvas:
    def __init__(self, items):
        self.items = items

    def find_overlapping(self, *_args):
        return tuple(self.items)

    def gettags(self, item):
        return self.items[item]


class _Geo:
    cell_size = 54
    step = 13
    half_width = 54
    half_height = 27
    origin_x = 350
    origin_y = 120

    def __init__(self, instances):
        self.architecture_instances = instances

    def center(self, cell):
        x, y = cell
        return (self.origin_x + (x-y)*self.half_width,
                self.origin_y + (x+y)*self.half_height)


def _house(ident='maison_1', anchor=(4, 4), *, appearance=None):
    cells = frozenset((x, y) for x in range(anchor[0], anchor[0]+4)
                      for y in range(anchor[1], anchor[1]+3))
    return ArchitectureInstance('Maison', anchor, 0, 0, 4, 3,
                                cells, (anchor[0]+1, anchor[1]+2),
                                ident, appearance)


class VisualBuildingPickerTests(unittest.TestCase):
    def test_roof_pick_keeps_canonical_identity(self):
        instance = _house()
        geo = _Geo((instance,))
        canvas = _Canvas({1: ('architecture', 'architecture_roof',
                              'architecture_instance_0')})
        result = pick_building_part(canvas, geo, 400, 180)
        self.assertEqual((result.structure_id, result.anchor, result.cell,
                          result.part),
                         ('maison_1', (4, 4), (4, 4), 'roof'))

    def test_window_item_resolves_persisted_wall_cell(self):
        instance = _house(appearance={
            'facade': 'pierre', 'roof': 'tuiles', 'windows': [[0, 1]]
        })
        geo = _Geo((instance,))
        canvas = _Canvas({1: ('architecture', 'architecture_window',
                              'architecture_instance_0')})
        x, y = geo.center((4, 5))
        result = pick_building_part(canvas, geo, x, y-48)
        self.assertEqual((result.part, result.cell), ('window', (4, 5)))

    def test_facade_chooses_real_exterior_wall_not_floor_or_door(self):
        instance = _house()
        geo = _Geo((instance,))
        canvas = _Canvas({1: ('architecture', 'architecture_facade',
                              'architecture_instance_0')})
        x, y = geo.center((4, 5))
        result = pick_building_part(canvas, geo, x, y-48)
        self.assertEqual((result.part, result.cell), ('facade', (4, 5)))

    def test_single_sprite_click_on_door_uses_projected_entry(self):
        instance = _house()
        geo = _Geo((instance,))
        dx, dy = instance.entry
        x = geo.origin_x + (dx-dy) * geo.half_width
        y = geo.origin_y + (dx+dy) * geo.half_height - geo.cell_size*.2
        canvas = _Canvas({1: ('architecture', 'architecture_sprite',
                              'architecture_instance_0')})
        selected = pick_building_part(canvas, geo, x, y)
        self.assertEqual((selected.part, selected.cell),
                         ('door', instance.entry))

    def test_single_sprite_click_on_roof_selects_roof(self):
        from sporebound.iso_architecture import architecture_outline
        instance = _house()
        geo = _Geo((instance,))
        roof, _ = architecture_outline(geo, instance)
        px = sum(p[0] for p in roof) / 4
        py = sum(p[1] for p in roof) / 4
        canvas = _Canvas({1: ('architecture', 'architecture_sprite',
                              'architecture_instance_0')})
        selected = pick_building_part(canvas, geo, px, py)
        self.assertEqual(selected.part, 'roof')

    def test_door_selects_existing_entry_not_new_passage(self):
        instance = _house()
        canvas = _Canvas({1: ('architecture', 'architecture_door',
                              'architecture_instance_0')})
        result = pick_building_part(canvas, _Geo((instance,)), 300, 180)
        self.assertEqual((result.part, result.cell), ('door', (5, 6)))

    def test_painter_order_selects_front_building(self):
        first = _house('rear')
        second = _house('front', (10, 10))
        canvas = _Canvas({
            1: ('architecture', 'architecture_roof',
                'architecture_instance_0'),
            2: ('architecture', 'architecture_roof',
                'architecture_instance_1')})
        result = pick_building_part(canvas, _Geo((first, second)), 300, 180)
        self.assertEqual(result.structure_id, 'front')

    def test_no_matching_architecture_does_not_pick_actors_or_props(self):
        instance = _house()
        geo = _Geo((instance,))
        canvas = _Canvas({1: ('unit', 'actor'), 2: ('decoration',)})
        self.assertIsNone(pick_building_part(canvas, geo, 0, 0))
        self.assertIsNone(pick_building_part(
            canvas, geo, 0, 0, fallback_cell=(15, 15)))

    def test_ground_fallback_resolves_wall_and_open_door(self):
        instance = _house()
        geo = _Geo((instance,))
        canvas = _Canvas({})
        self.assertEqual(pick_building_part(
            canvas, geo, 0, 0, fallback_cell=(4, 5)).part, 'facade')
        self.assertEqual(pick_building_part(
            canvas, geo, 0, 0, fallback_cell=(5, 6)).part, 'door')

    def test_invalid_instance_tag_never_selects_unrelated_asset(self):
        instance = _house()
        canvas = _Canvas({1: ('architecture', 'architecture_roof',
                              'architecture_instance_17')})
        self.assertIsNone(pick_building_part(canvas, _Geo((instance,)),
                                             220, 80))


if __name__ == '__main__':
    unittest.main()

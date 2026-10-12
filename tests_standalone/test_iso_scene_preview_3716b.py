"""Keep map-hover sprites aligned with the same atlas anchors as real stamps."""
import subprocess
import sys
import unittest

from sporebound.iso_architecture import (
    ARCHITECTURE_NAMES, SCENERY_NAMES, placement_origin,
    preview_structure_sprite_position)
from sporebound.iso_building_atlas import building_sprite_top_left
from sporebound.iso_fortification_atlas import fortification_sprite_top_left
from sporebound.iso_structures import (
    STRUCTURE_NAMES, door_slots, structure_footprint, structure_template)


class SimpleGeometry:
    cell_size = 54
    half_width = 54
    half_height = 27
    origin_x = 650
    origin_y = 155
    step = 13


class IsoScenePreviewTests(unittest.TestCase):
    def test_all_presets_and_orientations_reuse_real_frame_coordinates(self):
        geo = SimpleGeometry()
        for name in STRUCTURE_NAMES:
            for turns in range(4):
                for slot in range(len(door_slots(name))):
                    with self.subTest(name=name, turns=turns, door=slot):
                        clip = structure_template(name, turns, door_slot=slot)
                        anchor = (6, 9)
                        instance, position = preview_structure_sprite_position(
                            geo, name, anchor, turns, door_slot=slot)
                        self.assertEqual((instance.width, instance.height),
                                         (clip.width, clip.height))
                        self.assertEqual(instance.cells,
                                         frozenset(structure_footprint(clip, anchor)))
                        self.assertEqual(instance.turns, turns)
                        self.assertEqual(instance.door_slot, slot)
                        actual = (building_sprite_top_left(geo, instance)
                                  if name in ARCHITECTURE_NAMES
                                  else fortification_sprite_top_left(geo, instance))
                        self.assertEqual(position, actual)
                        self.assertEqual(len(position), 2)
                        self.assertIn(name, ARCHITECTURE_NAMES + SCENERY_NAMES)

    def test_door_pivot_and_alternate_entry_match_preview(self):
        geo = SimpleGeometry()
        for slot in (0, 1):
            clip = structure_template('Maison', 1, door_slot=slot)
            cursor = (11, 11)
            anchor = placement_origin(clip, cursor, 'Porte')
            instance, _ = preview_structure_sprite_position(
                geo, 'Maison', anchor, 1, door_slot=slot)
            self.assertEqual(instance.entry, cursor)

    def test_no_tk_or_pillow_is_loaded(self):
        subprocess.run([
            sys.executable, '-c',
            'import sys; from sporebound.iso_architecture import '
            'preview_structure_sprite_position; '
            'assert "tkinter" not in sys.modules; '
            'assert "PIL" not in sys.modules'
        ], check=True)

    def test_rejects_invalid_anchor_without_side_effect(self):
        from sporebound.model import RuleError
        with self.assertRaises(RuleError):
            preview_structure_sprite_position(SimpleGeometry(), 'Maison',
                                              (True, 3))


if __name__ == '__main__':
    unittest.main()

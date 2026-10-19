"""Map Builder 4.0B — authored facade, roof and exterior openings.

Exercises the existing Content/Document path and shared ISO renderer headlessly.
"""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.building_visuals import (
    building_appearance, edit_building_appearance, exterior_wall_cells,
    set_building_window)
from sporebound.editor import Document
from sporebound.interior_levels import add_interior_floor, edit_interior_tile
from sporebound.iso_architecture import draw_architecture
from sporebound.iso_map import IsoGeometry
from sporebound.iso_structures import edit_structure, place_structure
from sporebound.level_navigation import add_level_link
from sporebound.model import Content, RuleError


class _Canvas:
    def __init__(self):
        self.items = []

    def __getattr__(self, name):
        if name.startswith('create_'):
            def record(*args, **kwargs):
                self.items.append((name, args, kwargs))
            return record
        if name == 'tag_raise':
            return lambda *_: None
        raise AttributeError(name)


class BuildingVisualsTests(unittest.TestCase):
    MID = 'visual_architecture_b'

    def setUp(self):
        raw = Content.load(DEFAULT_CONTENT).to_dict()
        raw = add_blank_mission(raw, self.MID, 'Visual architecture', 16, 16)
        self.data = place_structure(raw, self.MID, 'Maison', (4, 4))
        self.sid = self.scene().structures[0]['id']

    def scene(self, payload=None):
        return Content.from_dict(payload or self.data).missions[self.MID]

    def row(self, payload=None):
        mission = next(m for m in (payload or self.data)['missions']
                       if m['id'] == self.MID)
        return mission['structures'][0]

    def test_facade_roof_edit_persists_without_tactical_changes(self):
        before = deepcopy(self.data)
        after = edit_building_appearance(self.data, self.MID, self.sid,
                                         facade='brique', roof='ardoise')
        self.assertEqual(self.row(after)['appearance'],
                         {'facade': 'brique', 'roof': 'ardoise', 'windows': []})
        self.assertEqual(self.scene(after).board, self.scene(before).board)
        self.assertEqual(self.data, before)
        doc = Document(Content.from_dict(self.data))
        doc.replace(after)
        doc.undo()
        self.assertEqual(doc.data, before)
        doc.redo()
        self.assertEqual(self.row(doc.data)['appearance']['roof'], 'ardoise')
        self.assertEqual(Content.from_dict(after).to_dict(), after)

    def test_window_is_visual_and_cannot_cut_a_door_or_floor(self):
        self.assertIn((0, 1), exterior_wall_cells(self.row()))
        before_board = self.scene().board
        after = set_building_window(self.data, self.MID, self.sid, (4, 5))
        self.assertEqual(self.row(after)['appearance']['windows'], [[0, 1]])
        self.assertEqual(self.scene(after).board, before_board)
        self.assertEqual(
            self.row(set_building_window(after, self.MID, self.sid, (4, 5)))['appearance']['windows'],
            [[0, 1]])
        removed = set_building_window(after, self.MID, self.sid, (4, 5),
                                      present=False)
        self.assertEqual(self.row(removed)['appearance']['windows'], [])
        for cell in ((5, 6), (5, 5), (0, 0), (True, 2)):
            with self.subTest(cell=cell), self.assertRaises(RuleError):
                set_building_window(self.data, self.MID, self.sid, cell)

    def test_rotation_preserves_window_in_new_local_orientation(self):
        windowed = set_building_window(self.data, self.MID, self.sid, (4, 5))
        rotated = edit_structure(windowed, self.MID, (4, 4), quarter_turns=1)
        self.assertEqual(self.row(rotated)['turns'], 1)
        self.assertEqual(self.row(rotated)['appearance']['windows'], [[1, 0]])
        self.assertEqual(self.row(rotated)['id'], self.sid)
        moved = edit_structure(rotated, self.MID, (4, 4), anchor=(7, 7))
        self.assertEqual(self.row(moved)['appearance']['windows'], [[1, 0]])
        self.assertEqual(self.row(moved)['id'], self.sid)

    def test_invalid_payload_is_rejected_by_content(self):
        styled = edit_building_appearance(self.data, self.MID, self.sid,
                                          facade='torchis', roof='plat')
        for key, value in [('facade', 'neon'), ('roof', 'opaque'),
                           ('windows', [[1, 2]]),
                           ('windows', [[0, 1], [0, 1]])]:
            with self.subTest(key=key, value=value):
                broken = deepcopy(styled)
                self.row(broken)['appearance'][key] = value
                with self.assertRaises(RuleError):
                    Content.from_dict(broken)
        original = deepcopy(styled)
        with self.assertRaises(RuleError):
            edit_building_appearance(styled, self.MID, self.sid, roof='glass')
        self.assertEqual(styled, original)

    def test_existing_upper_deck_and_stairs_remain_usable(self):
        with_floor = add_interior_floor(self.data, self.MID, self.sid, 1)
        furnished = edit_interior_tile(
            with_floor, self.MID, self.sid, 1, (5, 5), feature='crate')
        # Crates are intentionally non-walkable on upper decks; the stair
        # must use the Maison walkable entry, not the furnished crate cell.
        connected = add_level_link(furnished, self.MID,
                                   [0, 5, 6], [1, 5, 6])
        styled = edit_building_appearance(connected, self.MID, self.sid,
                                          facade='torchis', roof='plat')
        self.assertIn('crate', [t['feature'] for t in self.scene(styled).interior_floors[0]['tiles']])
        self.assertEqual(len(self.scene(styled).level_links), 1)
        self.assertEqual(self.scene(styled).board, self.scene(connected).board)

    def test_shared_renderer_draws_custom_windows_and_flat_roof(self):
        after = set_building_window(self.data, self.MID, self.sid, (4, 5))
        after = edit_building_appearance(after, self.MID, self.sid,
                                         facade='brique', roof='plat')
        scene = self.scene(after)
        canvas = _Canvas()
        draw_architecture(canvas, IsoGeometry(scene.board, 54), scene.board, [],
                          selected_cell=None,
                          layers={'Bâtiments': True, 'Toitures': True},
                          structures=scene.structures, atlas=None)
        tags = [item[2].get('tags', ()) for item in canvas.items]
        self.assertTrue(any('architecture_window' in row for row in tags))
        self.assertTrue(any('architecture_flat_roof' in row for row in tags))


if __name__ == '__main__':
    unittest.main()

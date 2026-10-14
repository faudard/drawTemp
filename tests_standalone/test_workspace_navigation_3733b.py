"""3.7.33B — identity-based Workspace navigation and selection without Tk."""
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_object
from sporebound.editor_groups import create_editor_group
from sporebound.model import Content, RuleError
from sporebound.workspace_navigation import (
    NavigationHistory, map_selection_key, navigation_target)


class WorkspaceNavigationTests(unittest.TestCase):
    def setUp(self):
        self.data = Content.load(DEFAULT_CONTENT).to_dict()
        self.mission = next(m for m in self.data['missions'] if m['id'] == 'garden')

    def test_select_actor_object_tile_group_with_stable_resource_ids(self):
        actor = self.mission['units'][0]
        actor_id = map_selection_key(self.data, 'garden', actor['pos'])
        self.assertEqual(actor_id, 'map_actor:garden/' + actor['id'])
        self.assertEqual(navigation_target(self.data, actor_id),
                         ('garden', tuple(actor['pos'])))
        obj = next(o for o in self.mission['objects']
                   if tuple(o['pos']) not in
                   [tuple(a['pos']) for a in self.mission['units']])
        key = map_selection_key(self.data, 'garden', obj['pos'])
        self.assertEqual(key, 'map_object:garden/' + obj['id'])
        self.assertEqual(navigation_target(self.data, key),
                         ('garden', tuple(obj['pos'])))
        chosen = next(cell for cell in Content.from_dict(self.data)
                      .missions['garden'].board.cells()
                      if not any(tuple(u['pos']) == cell for u in
                                 self.mission['units'])
                      and not any(tuple(o['pos']) == cell for o in
                                  self.mission['objects']))
        tile = map_selection_key(self.data, 'garden', chosen)
        self.assertEqual(tile, f'map_tile:garden/{chosen[0]},{chosen[1]}')
        self.assertEqual(navigation_target(self.data, tile), ('garden', chosen))
        grouped = create_editor_group(self.data, 'garden', 'Forteresse',
                                      cells=(chosen,))
        self.assertEqual(map_selection_key(
            grouped, 'garden', chosen, group_id='group_1'),
            'editor_group:garden/group_1')
        self.assertEqual(navigation_target(
            grouped, 'editor_group:garden/group_1'), ('garden', chosen))

    def test_history_dedup_forward_truncation_and_bound(self):
        history = NavigationHistory(limit=3)
        self.assertTrue(history.record('mission:garden'))
        self.assertFalse(history.record('mission:garden'))
        history.record('map_actor:garden/a')
        history.record('map_object:garden/b')
        self.assertTrue(history.can_back)
        self.assertEqual(history.traverse(-1, lambda _: True),
                         'map_actor:garden/a')
        self.assertEqual(history.traverse(-1, lambda _: True), 'mission:garden')
        self.assertFalse(history.can_back)
        self.assertEqual(history.traverse(1, lambda _: True), 'map_actor:garden/a')
        history.record('map_object:garden/c')
        self.assertFalse(history.can_forward)
        history.record('map_tile:garden/3,3')
        self.assertEqual(history.traverse(-1, lambda _: True),
                         'map_object:garden/c')
        self.assertEqual(history.traverse(-1, lambda _: True),
                         'map_actor:garden/a')
        self.assertFalse(history.can_back)
        history.reset()
        self.assertEqual(history.current, '')

    def test_missing_resources_are_skipped_without_mutation(self):
        h = NavigationHistory()
        h.record('mission:garden')
        h.record('map_actor:garden/missing')
        h.record('map_tile:garden/3,3')
        h.record('map_object:garden/missing')
        valid = lambda key: self._valid(key)
        self.assertEqual(h.traverse(-1, valid), 'map_tile:garden/3,3')
        self.assertEqual(h.traverse(-1, valid), 'mission:garden')
        self.assertFalse(h.traverse(-1, valid))
        self.assertEqual(h.current, 'mission:garden')
        self.assertEqual(h.traverse(1, valid), 'map_tile:garden/3,3')

    def _valid(self, key):
        try:
            navigation_target(self.data, key)
            return True
        except RuleError:
            return False

    def test_reject_stale_group_and_out_of_bounds_tile(self):
        with self.assertRaises(RuleError):
            navigation_target(self.data, 'editor_group:garden/missing')
        with self.assertRaises(RuleError):
            navigation_target(self.data, 'map_tile:garden/999,999')
        with self.assertRaises(RuleError):
            map_selection_key(self.data, 'garden', (-1, 0))
        with self.assertRaises(RuleError):
            map_selection_key(self.data, 'garden', (2, 2),
                              group_id='nonexistent')
        with self.assertRaises(ValueError):
            NavigationHistory(limit=1)


if __name__ == '__main__':
    unittest.main()

"""3.6.2: true runtime entry mapping, bounded indexes and safe focus paths."""
from copy import deepcopy
import unittest

from sporebound.model import RuleError
from sporebound.story_graph_navigation import (
    entry_scene_ids, navigation_diagnostics, search_narrative,
    shortest_occurrence)
from tests_standalone.test_visual_branch_graph_36 import VisualBranchGraphTests


class StoryGraphNavigationTests(unittest.TestCase):
    def setUp(self):
        fixture = VisualBranchGraphTests()
        fixture.setUp()
        self.data, project = fixture.build()
        self.story = deepcopy(project.story)
        self.root = 'v36_dialogue'

    def test_entries_from_all_four_runtime_route_families(self):
        self.story['entry_scenes'] = {'main': self.root}
        self.story['after_mission'] = {'garden': 'v36_final'}
        self.story['after_strategic_event'] = {
            'siege/wave': 'v36_parley_scene'}
        expected = [self.root, 'v36_final', 'v36_parley_scene']
        self.assertEqual(entry_scene_ids(self.story), sorted(expected))
        diagnostic = navigation_diagnostics(self.story)
        self.assertEqual(diagnostic['missing_entries'], [])
        self.assertEqual(
            {x['scene_id'] for x in diagnostic['structurally_unreachable']},
            {'v36_orphan'})
        orphan = next(x for x in diagnostic['records']
                      if x['scene_id'] == 'v36_orphan')
        self.assertEqual(orphan['status'], 'unreferenced')
        self.assertEqual(orphan['incoming'], 0)

    def test_disconnected_subgraph_is_separate_from_unreferenced_draft(self):
        self.story['scenes'].append({
            'id': 'draft_child', 'title': 'Suite brouillon',
            'speaker': '', 'text': '',
            'choices': [{'id': 'end', 'label': 'Terminer'}]})
        orphan = next(s for s in self.story['scenes']
                      if s['id'] == 'v36_orphan')
        orphan['choices'][0]['next_scene'] = 'draft_child'
        statuses = {r['scene_id']: r['status']
                    for r in navigation_diagnostics(self.story)['records']}
        self.assertEqual(statuses['v36_orphan'], 'unreferenced')
        self.assertEqual(statuses['draft_child'], 'disconnected')
        self.assertEqual(statuses['v36_dialogue'], 'reachable')

    def test_conditional_only_route_is_not_reported_as_dead(self):
        self.story['scenes'].append({
            'id': 'flag_only', 'title': 'Issue secrète',
            'speaker': 'Jeanne', 'text': 'Condition satisfied?',
            'choices': [{'id': 'end', 'label': 'Terminer'}]})
        scene = next(s for s in self.story['scenes']
                     if s['id'] == self.root)
        scene['choices'][2]['next_scene'] = 'flag_only'
        scene['choices'][2]['when'] = {'flag': 'peace', 'eq': True}
        statuses = {r['scene_id']: r['status']
                    for r in navigation_diagnostics(self.story)['records']}
        self.assertEqual(statuses['flag_only'], 'conditional_only')
        diagnostic = navigation_diagnostics(self.story)
        self.assertNotIn(
            'flag_only',
            {row['scene_id'] for row in diagnostic['structurally_unreachable']})
        hits = search_narrative(self.story, self.data, 'garden',
                                'issue', kind='scenes')['results']
        self.assertIn('flag_only', [r['scene_id'] for r in hits])

    def test_search_accents_filters_events_choices_text_and_status(self):
        cases = [
            ('À la porte', 'scenes', 'v36_dialogue'),
            ('negocier', 'choices', 'v36_dialogue/parley'),
            ('v36_assault', 'events', 'v36_assault'),
            ('Scène isolée', 'issues', 'v36_orphan'),
            ('Attendre', 'all', 'v36_dialogue/wait'),
        ]
        for needle, filter_kind, expected in cases:
            with self.subTest(needle=needle):
                found = search_narrative(
                    self.story, self.data, 'garden', needle,
                    kind=filter_kind)
                self.assertIn(expected, [r['id'] for r in found['results']])
        empty = search_narrative(
            self.story, self.data, 'garden', '', max_results=2)
        self.assertEqual(len(empty['results']), 2)
        self.assertTrue(empty['truncated'])
        self.assertGreater(empty['matches'], 2)
        for invalid in (
            {'kind': 'unknown'},
            {'query': 'x'*161},
            {'max_results': 0},
            {'mission_id': 'bad'},
        ):
            options = dict(mission_id='garden')
            options.update(invalid)
            with self.subTest(invalid=invalid):
                with self.assertRaises(RuleError):
                    search_narrative(
                        self.story, self.data, **options)

    def test_shortest_path_canonical_shared_scene_and_unreachable(self):
        self.assertEqual(
            shortest_occurrence(self.story, self.root, 'v36_assault_scene'),
            (self.root, 'assault'))
        self.assertEqual(
            shortest_occurrence(self.story, self.root, 'v36_parley_scene'),
            (self.root, 'parley'))
        self.assertEqual(
            shortest_occurrence(self.story, self.root, 'v36_orphan'), None)
        self.assertEqual(
            shortest_occurrence(self.story, self.root, self.root),
            (self.root,))
        with self.assertRaises(RuleError):
            shortest_occurrence(self.story, 'missing', self.root)
        with self.assertRaises(RuleError):
            shortest_occurrence(
                self.story, self.root, 'v36_assault_scene',
                max_depth=-1)

    def test_large_graph_bounded_cycle_safe_and_deterministic(self):
        length = 1200
        scenes = []
        for i in range(length):
            dest = 'nav_%04d' % (i+1 if i+1 < length else 250)
            scenes.append({
                'id': 'nav_%04d' % i,
                'title': 'Route %d' % i,
                'speaker': '', 'text': '',
                'choices': [
                    {'id': 'continue', 'label': 'Continuer',
                     'next_scene': dest},
                ]})
        story = {
            'scenes': scenes,
            'during_tactical_event': {'garden/start': 'nav_0000'},
        }
        diagnostics = navigation_diagnostics(story)
        self.assertEqual(diagnostics['reachable_count'], length)
        self.assertFalse(diagnostics['structurally_unreachable'])
        self.assertEqual(shortest_occurrence(
            story, 'nav_0000', 'nav_0000'), ('nav_0000',))
        self.assertIsNone(shortest_occurrence(
            story, 'nav_0000', 'nav_0900', max_depth=20))
        a = search_narrative(story, self.data, 'garden',
                             'route', kind='scenes', max_results=40)
        b = search_narrative(story, self.data, 'garden',
                             'route', kind='scenes', max_results=40)
        self.assertEqual(a, b)
        self.assertEqual(a['matches'], length)
        self.assertTrue(a['truncated'])
        with self.assertRaises(RuleError):
            navigation_diagnostics(story, max_nodes=100)

    def test_diagnostics_do_not_modify_story_or_content(self):
        frozen_story, frozen_content = deepcopy(self.story), deepcopy(self.data)
        navigation_diagnostics(self.story)
        search_narrative(self.story, self.data, 'garden', kind='issues')
        shortest_occurrence(self.story, self.root, 'v36_assault_scene')
        self.assertEqual(self.story, frozen_story)
        self.assertEqual(self.data, frozen_content)


if __name__ == '__main__':
    unittest.main()

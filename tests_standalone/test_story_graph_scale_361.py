"""3.6.1: bounded grouping, compact geometry and A/B route comparisons."""
from copy import deepcopy
import unittest

from sporebound.model import RuleError
from sporebound.story_graph import build_story_tree
from sporebound.story_graph_scale import (
    trace_occurrence, compare_occurrences, grouped_branches,
    grouped_collapse_paths, format_path_comparison)
from sporebound.story_authoring import link_choice
from tests_standalone.test_visual_branch_graph_36 import VisualBranchGraphTests


class StoryGraphScaleTests(unittest.TestCase):
    def setUp(self):
        f = VisualBranchGraphTests()
        f.setUp()
        self.data, self.project = f.build()
        self.story = self.project.story
        self.root = 'v36_dialogue'
        self.mid = 'garden'

    def test_normal_layout_unchanged_and_compact_reduces_dimensions(self):
        standard = build_story_tree(self.story, self.root)
        default_explicit = build_story_tree(
            self.story, self.root, density='normal')
        compact = build_story_tree(self.story, self.root, density='compact')
        self.assertEqual(standard, default_explicit)
        self.assertEqual([n['path'] for n in compact['nodes']],
                         [n['path'] for n in standard['nodes']])
        self.assertLess(compact['width'], standard['width'])
        self.assertLess(compact['height'], standard['height'])
        self.assertEqual(compact['density'], 'compact')
        with self.assertRaises(RuleError):
            build_story_tree(self.story, self.root, density='huge')

    def test_compare_exclusive_branches_includes_tactical_event_ids(self):
        a = (self.root, 'assault', 'continue')
        b = (self.root, 'parley', 'continue')
        result = compare_occurrences(
            self.story, self.data, self.mid, self.root, a, b)
        self.assertEqual(result['a']['scenes'],
                         ['v36_dialogue', 'v36_assault_scene'])
        self.assertEqual(result['b']['scenes'],
                         ['v36_dialogue', 'v36_parley_scene'])
        self.assertEqual(result['only_a_events'], ['v36_assault'])
        self.assertEqual(result['only_b_events'], ['v36_parley'])
        self.assertEqual(result['shared_steps'], [])
        report = '\n'.join(format_path_comparison(result))
        self.assertIn('Assaillir', report)
        self.assertIn('Négocier', report)
        self.assertIn('v36_assault', report)
        self.assertIn('v36_parley', report)

    def test_shared_prefix_then_divergence_reports_common_decisions(self):
        a = (self.root, 'assault')
        b = (self.root, 'assault', 'continue')
        result = compare_occurrences(
            self.story, self.data, self.mid, self.root, a, b)
        self.assertEqual(len(result['shared_steps']), 1)
        self.assertEqual(result['only_a'], [])
        self.assertEqual(result['only_a_events'], [])
        self.assertEqual(result['only_b_events'], [])
        self.assertEqual(result['common_events'], ['v36_assault'])

    def test_grouped_view_collapses_nested_choice_subtrees_only(self):
        content_before = deepcopy(self.data)
        manifest_before = deepcopy(self.project.to_dict())
        new_project = link_choice(
            self.project, __import__('sporebound.model', fromlist=['Content']).Content.from_dict(self.data),
            'v36_assault_scene', 'continue', 'v36_final')
        story = new_project.story
        groups = grouped_branches(story, self.root, self.data, self.mid)
        self.assertEqual([g['choice_id'] for g in groups],
                         ['assault', 'parley', 'wait'])
        assault = groups[0]
        self.assertEqual(assault['scene_count'], 2)
        self.assertEqual(assault['ending_count'], 1)
        self.assertEqual(assault['event_ids'], ['v36_assault'])
        collapsed = grouped_collapse_paths(story, self.root, at_depth=1)
        self.assertIn((self.root, 'assault'), collapsed)
        self.assertNotIn((self.root, 'parley'), collapsed)
        full = build_story_tree(story, self.root)
        compact_grouped = build_story_tree(
            story, self.root, collapsed=collapsed, density='compact')
        self.assertLess(len(compact_grouped['nodes']), len(full['nodes']))
        self.assertEqual(self.data, content_before)
        self.assertEqual(self.project.to_dict(), manifest_before)

    def test_scale_budget_on_large_branch_tree_is_deterministic(self):
        scenes = []
        length = 220
        for i in range(length):
            sid = 'scene_%04d' % i
            target = ('scene_%04d' % (i+1)) if i+1 < length else ''
            scenes.append({
                'id': sid, 'title': sid, 'speaker': 'Récit', 'text': sid,
                'choices': [{
                    'id': 'forward', 'label': 'Continuer',
                    **({'next_scene': target} if target else {}),
                }],
            })
        story = {'scenes': scenes}
        compact = build_story_tree(
            story, scenes[0]['id'], max_nodes=1500, density='compact')
        self.assertTrue(compact['truncated'])
        closed = grouped_collapse_paths(story, 'scene_0000',
                                         at_depth=2, max_visits=500)
        self.assertEqual(closed, {
            ('scene_0000', 'forward', 'forward')})
        result = grouped_branches(
            story, 'scene_0000', self.data, self.mid,
            max_visits=20, max_depth=32)
        self.assertTrue(result[0]['truncated'])
        self.assertEqual(result[0]['event_ids'], [])
        self.assertEqual(result, grouped_branches(
            story, 'scene_0000', self.data, self.mid,
            max_visits=20, max_depth=32))

    def test_stale_root_missing_paths_and_invalid_configuration(self):
        for invalid in (
            ('bad', ('bad',)),
            (self.root, (self.root, 'not_a_choice')),
            (self.root, (self.root, 'assault', 'continue', 'again')),
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(RuleError):
                    trace_occurrence(self.story, *invalid)
        with self.assertRaises(RuleError):
            grouped_branches(self.story, self.root,
                             self.data, self.mid, max_visits=2)
        with self.assertRaises(RuleError):
            grouped_collapse_paths(self.story, self.root, at_depth=0)
        with self.assertRaises(RuleError):
            compare_occurrences(
                self.story, self.data, 'unknown',
                self.root, (self.root,), (self.root, 'assault'))


if __name__ == '__main__':
    unittest.main()

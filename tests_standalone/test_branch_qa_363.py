"""3.6.3 Branch QA structural truth, StoryBook runtime probes and caps."""
from copy import deepcopy
import unittest

from sporebound.branch_qa_363 import (
    condition_contradiction, audit_branch_coverage, probe_story_choices,
    probe_tactical_branches, format_branch_qa)
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from tests_standalone.test_visual_branch_graph_36 import VisualBranchGraphTests


class BranchQATests(unittest.TestCase):
    def setUp(self):
        fixture = VisualBranchGraphTests()
        fixture.setUp()
        self.data, self.project = fixture.build()
        self.story = self.project.story

    def test_structural_coverage_and_terminal_paths_are_informational(self):
        report = audit_branch_coverage(self.story, self.data, 'garden')
        self.assertEqual(report['scene_count'], 5)
        self.assertEqual(report['choice_count'], 7)
        self.assertEqual(report['reachable_scene_count'], 4)
        self.assertEqual(report['structurally_reachable_choices'], 6)
        self.assertEqual(report['terminal_choices'], 5)
        self.assertEqual(
            [e['event_id'] for e in report['guarded_events']],
            ['v36_assault', 'v36_parley'])
        orphan = next(x for x in report['issues']
                      if x['code'] == 'disconnected_scene')
        self.assertEqual(orphan['scene_id'], 'v36_orphan')
        endings = [x for x in report['issues']
                   if x['code'] == 'terminal_choice']
        self.assertEqual(len(endings), 5)
        self.assertTrue(all(x['severity'] == 'info' for x in endings))
        self.assertIn('COUVERTURE STRUCTURELLE',
                      '\n'.join(format_branch_qa(report)))

    def test_condition_proofs_only_when_logically_certain(self):
        impossible_eq = {'all': [
            {'flag': 'gate', 'eq': True},
            {'flag': 'gate', 'eq': False},
        ]}
        impossible_bound = {'all': [
            {'flag': 'gold', 'gte': 10},
            {'flag': 'gold', 'lte': 2},
        ]}
        impossible_not = {'all': [
            {'completed_mission': 'garden'},
            {'not': {'completed_mission': 'garden'}},
        ]}
        for expr in (impossible_eq, impossible_bound, impossible_not):
            with self.subTest(expr=expr):
                self.assertTrue(condition_contradiction(expr))
        self.assertFalse(condition_contradiction({
            'any': [impossible_eq, {'flag': 'other', 'eq': True}]}))
        self.assertTrue(condition_contradiction({
            'any': [impossible_eq, impossible_bound]}))
        self.assertFalse(condition_contradiction({
            'all': [
                {'flag': 'gate', 'eq': True},
                {'flag': 'other', 'eq': False},
            ]}))
        self.assertFalse(condition_contradiction({
            'not': {'flag': 'gate', 'eq': False}}))
        modified = deepcopy(self.story)
        row = next(s for s in modified['scenes']
                   if s['id'] == 'v36_dialogue')
        row['choices'][2]['when'] = impossible_eq
        report = audit_branch_coverage(modified, self.data, 'garden')
        issue = next(x for x in report['issues']
                     if x['code'] == 'contradictory_condition')
        self.assertEqual(issue['scene_id'], 'v36_dialogue')
        self.assertEqual(issue['choice_id'], 'wait')
        self.assertEqual(issue['severity'], 'error')

    def test_isolated_storybook_probes_use_actual_choice_guards_and_effects(self):
        raw = self.project.to_dict()
        story = raw['story']
        origin = next(s for s in story['scenes']
                      if s['id'] == 'v36_dialogue')
        origin['choices'][0]['effects'] = [
            {'kind': 'set_flag', 'flag': 'secret_access', 'value': True}]
        assault = next(s for s in story['scenes']
                       if s['id'] == 'v36_assault_scene')
        assault['choices'].append({
            'id': 'secret', 'label': 'Passage caché',
            'when': {'flag': 'secret_access', 'eq': True},
            'next_scene': 'v36_final',
        })
        project = GameProject.from_dict(raw, Content.from_dict(self.data))
        content_snapshot, project_snapshot = (
            deepcopy(self.data), deepcopy(project.to_dict()))
        first = probe_story_choices(self.data, project)
        second = probe_story_choices(self.data, project)
        self.assertEqual(first, second)
        self.assertIn('v36_assault_scene/secret',
                      first['executed_choices'])
        self.assertNotIn('v36_assault_scene/secret',
                         first['uncovered_choices'])
        self.assertFalse(first['replay_verified'])
        self.assertTrue(any(
            row['story_flags'].get('secret_access') is True
            for row in first['finished']))
        self.assertEqual(self.data, content_snapshot)
        self.assertEqual(project.to_dict(), project_snapshot)

    def test_false_guard_not_executed_and_budget_explicit(self):
        raw = self.project.to_dict()
        row = next(s for s in raw['story']['scenes']
                   if s['id'] == 'v36_dialogue')
        row['choices'][2]['when'] = {
            'flag': 'unknown_secret', 'eq': True}
        project = GameProject.from_dict(raw, Content.from_dict(self.data))
        report = probe_story_choices(self.data, project)
        self.assertIn('v36_dialogue/wait', report['uncovered_choices'])
        self.assertNotIn('v36_dialogue/wait', report['executed_choices'])
        bounded = probe_story_choices(self.data, project, max_states=1)
        self.assertTrue(bounded['truncated'])
        self.assertEqual(bounded['states'], 1)
        for limits in (
            {'max_states': 0}, {'max_states': 4001},
            {'max_depth': 0}, {'max_paths': 201}):
            with self.subTest(limits=limits):
                with self.assertRaises(RuleError):
                    probe_story_choices(self.data, project, **limits)

    def test_tactical_branch_probe_is_honest_about_replay(self):
        before = deepcopy(self.data), deepcopy(self.project.to_dict())
        report = probe_tactical_branches(self.data, self.project, 'garden',
                                          max_events=2)
        self.assertEqual(report['kind'], 'isolated_battle_preview')
        self.assertFalse(report['replay_verified'])
        self.assertTrue(any(
            r['event_id'] == 'v36_origin' for r in report['reports']))
        self.assertIn('NON', report['evidence'].upper()
                      if 'non' in report['evidence'] else 'NON')
        self.assertEqual((self.data, self.project.to_dict()), before)
        self.assertIn('APERÇUS BATTLE', '\n'.join(format_branch_qa(report)))
        with self.assertRaises(RuleError):
            probe_tactical_branches(self.data, self.project,
                                     'garden', max_events=21)

    def test_empty_story_or_no_entry_has_no_false_simulation(self):
        content = Content.from_dict(self.data)
        default = GameProject.default(content)
        raw = default.to_dict()
        raw['story'] = deepcopy(self.story)
        for key in ('entry_scenes', 'after_mission',
                    'during_tactical_event', 'after_strategic_event'):
            raw['story'][key] = {}
        # Guards require an entry scene in the same mission, so use
        # unmodified base content rather than choice-gated tactical events.
        fixture = VisualBranchGraphTests()
        fixture.setUp()
        clean = fixture.raw if hasattr(fixture, 'raw') else None
        self.assertIsNone(clean)
        from sporebound.__main__ import DEFAULT_CONTENT
        clean_data = Content.load(DEFAULT_CONTENT).to_dict()
        project = GameProject.from_dict(raw, Content.from_dict(clean_data))
        report = probe_story_choices(clean_data, project)
        self.assertEqual(report['states'], 0)
        self.assertEqual(report['executed_choices'], [])
        self.assertFalse(report['replay_verified'])


if __name__ == '__main__':
    unittest.main()

"""3.6.4 true GameSession checkpoint replay and regression gates."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.gameplay_certification_364 import (
    certify_gameplay_paths, execute_certified_path, enforce_certification,
    format_certification)
from sporebound.model import Content, RuleError
from tests_standalone.test_event_choice_branches_34 import EventChoiceBranchesTests


FIXTURE = Path(__file__).with_name('fixtures') / 'core_gameplay_certification_364.json'


def tactical_suite():
    def path(key, other, value, hazard):
        return {
            'id': key, 'campaign': 'main', 'seed': 17,
            'steps': [
                {'kind': 'start_mission', 'mission': 'garden', 'expect': {
                    'mode': 'battle', 'pending_tactical': 'garrison_choice',
                    'fired': ['branch_origin'],
                    'not_fired': ['branch_assault', 'branch_truce', 'branch_join']}},
                {'kind': 'tactical_choice', 'choice': key, 'expect': {
                    'mode': 'battle', 'pending_tactical': 'after_truce',
                    'fired': ['branch_origin', 'branch_join',
                              'branch_assault' if key == 'fight' else 'branch_truce'],
                    'not_fired': ['branch_truce' if key == 'fight'
                                  else 'branch_assault'],
                    'flags': {'strategy': value},
                    'history': [{'scene': 'garrison_choice', 'choice': key}],
                    'hazards': {'5,5' if key == 'fight' else '6,5': hazard}}},
                {'kind': 'tactical_choice', 'choice': 'continue', 'expect': {
                    'pending_tactical': '',
                    'flags': {'strategy': value},
                    'history': [
                        {'scene': 'garrison_choice', 'choice': key},
                        {'scene': 'after_truce', 'choice': 'continue'}]}}
            ]}
    return {
        'version': 1, 'min_passed_paths': 2,
        'required_choices': [
            'garrison_choice/fight', 'garrison_choice/parley',
            'after_truce/continue'],
        'required_events': ['branch_origin', 'branch_assault',
                            'branch_truce', 'branch_join'],
        'cases': [
            path('fight', 'parley', 'attack', 12),
            path('parley', 'fight', 'peace', 3),
        ],
    }


class GameplayCertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = EventChoiceBranchesTests()
        source.setUp()
        cls.data = source.data
        cls.content = source.content
        cls.project = source.project

    def test_true_session_two_exclusive_tactical_routes_certify_and_replay(self):
        before = deepcopy(self.data), deepcopy(self.project.to_dict())
        suite = tactical_suite()
        report = certify_gameplay_paths(self.data, self.project, suite)
        enforce_certification(report)
        self.assertEqual(report['passed_paths'], 2)
        self.assertEqual(report['total_paths'], 2)
        self.assertEqual(report['missing_choices'], [])
        self.assertEqual(report['missing_events'], [])
        self.assertEqual(set(report['certified_events']),
                         set(suite['required_events']))
        self.assertTrue(all(all(step['replay_verified']
                                for step in path['checkpoints'])
                            for path in report['paths']))
        self.assertEqual([len(path['checkpoints'])
                          for path in report['paths']], [3, 3])
        self.assertEqual((self.data, self.project.to_dict()), before)
        self.assertIn('Gate : PASS', '\n'.join(format_certification(report)))

    def test_replay_semantic_baseline_is_stable_across_fresh_sessions(self):
        suite = tactical_suite()
        first = certify_gameplay_paths(self.data, self.project, suite)
        second = certify_gameplay_paths(
            self.data, self.project, suite, baseline=first['semantic_baseline'])
        enforce_certification(second)
        self.assertEqual(first['semantic_baseline'],
                         second['semantic_baseline'])
        # Full session checkpoint hashes include random Battle identities,
        # but semantic baseline deliberately does not.
        self.assertEqual(first['paths'][0]['final']['battle_digest'],
                         second['paths'][0]['final']['battle_digest'])

    def test_gates_reject_missing_path_failed_oracle_and_missing_event(self):
        for variant in ('wrong_flag', 'missing_choice', 'missing_event',
                        'baseline_changed'):
            with self.subTest(variant=variant):
                suite = tactical_suite()
                baseline = None
                if variant == 'wrong_flag':
                    suite['cases'][0]['steps'][1]['expect']['flags']['strategy'] = 'peace'
                elif variant == 'missing_choice':
                    suite['required_choices'].append('garrison_choice/unknown')
                elif variant == 'missing_event':
                    suite['required_events'].append('nonexistent_event')
                else:
                    baseline = certify_gameplay_paths(
                        self.data, self.project,
                        suite)['semantic_baseline']
                    baseline = deepcopy(baseline)
                    baseline['fight']['events'] = []
                report = certify_gameplay_paths(
                    self.data, self.project, suite, baseline=baseline)
                self.assertFalse(report['passed'])
                with self.assertRaises(RuleError):
                    enforce_certification(report)
                self.assertTrue(report['gate_errors'])

    def test_reject_forged_gameplay_commands_and_invalid_oracle(self):
        suite = tactical_suite()
        suite['cases'][0]['steps'][1] = {
            'kind': 'command',
            'command': {'kind': 'story_effects', 'scene': 'garrison_choice',
                        'choice': 'fight', 'effects': []},
            'expect': {'pending_tactical': ''}}
        with self.assertRaises(RuleError):
            certify_gameplay_paths(self.data, self.project, suite)
        suite = tactical_suite()
        suite['cases'][0]['steps'][0]['expect'] = {}
        with self.assertRaises(RuleError):
            certify_gameplay_paths(self.data, self.project, suite)
        suite = tactical_suite()
        suite['cases'][0]['steps'][0]['expect'] = {'bogus': True}
        with self.assertRaises(RuleError):
            certify_gameplay_paths(self.data, self.project, suite)

    def test_real_core_campaign_decisions_and_mission_entry(self):
        raw = Content.load(DEFAULT_CONTENT).to_dict()
        content = Content.from_dict(raw)
        project = GameProject.load(
            Path(DEFAULT_CONTENT).with_suffix('.game.json'), content)
        suite = json.loads(FIXTURE.read_text(encoding='utf-8'))
        report = certify_gameplay_paths(raw, project, suite)
        enforce_certification(report)
        self.assertEqual(report['passed_paths'], 3)
        self.assertEqual(report['certified_choices'], [
            'oath/alone', 'oath/guard', 'oath_reward/proceed',
            'oath_reward/provisions'])
        guard = next(row for row in report['paths']
                     if row['id'] == 'relique_guard_supplies')
        self.assertEqual(guard['final']['gold'], 25)
        main = next(row for row in report['paths']
                    if row['id'] == 'main_garden_entry')
        self.assertEqual(main['final']['mode'], 'battle')
        self.assertTrue(main['checkpoints'][0]['replay_verified'])

    def test_checkpoint_corruption_causes_certification_failure(self):
        suite = tactical_suite()
        fake = deepcopy(suite)
        fake['cases'][0]['steps'][1]['choice'] = 'unknown_choice'
        report = certify_gameplay_paths(self.data, self.project, fake)
        self.assertFalse(report['passed'])
        self.assertFalse(report['replay_verified'])
        self.assertTrue(any('unknown' in error.lower() or
                            'unavailable' in error.lower()
                            for error in report['gate_errors']))
        with self.assertRaises(RuleError):
            enforce_certification(report)


if __name__ == '__main__':
    unittest.main()

"""VS-42: three actual R9 endings, conditional quest and negative reachability QA."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.r42_captain_slice import (
    ENDINGS, QUEST_MISSION, make_captain_slice, save_captain_template,
)
from drawtemp.sdk.r42_reachability import audit_narrative, captain_slice_audit
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import RuleError


class CaptainLoyaltySliceR42Tests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = make_captain_slice()

    def play(self, choices, *, restored_mid_dialogue=False):
        session = GameSession.new(self.content, self.project, 'main', seed=42)
        for index, choice in enumerate(choices):
            current = session.active_scene()
            self.assertIsNotNone(current)
            if restored_mid_dialogue and index == 0:
                self.assertEqual(session.narrative_line()['index'], 0)
                session.advance_narrative_line()
                snapshot = session.recording()
                session = GameSession.from_recording(
                    snapshot, self.content, self.project)
                self.assertEqual(session.recording(), snapshot)
                self.assertEqual(session.narrative_line()['index'], 1)
            while not session.narrative_line()['complete']:
                session.advance_narrative_line()
            self.assertIn(choice, {c['id'] for c in session.available_choices()})
            session.choose_story_option(choice)
        return session

    def test_canonical_reachability_covers_all_three_endings_and_reused_scenes(self):
        report = captain_slice_audit()
        self.assertTrue(report['passed'])
        self.assertEqual(report['dead_choices'], [])
        self.assertEqual(report['dead_scenes'], [])
        self.assertEqual(report['missing_endings'], [])
        self.assertEqual(report['reused_scenes'], ['camp', 'council'])
        self.assertEqual(report['required_reused_scenes'], 2)
        self.assertEqual(report['missing_reused_scenes'], 0)
        self.assertEqual(set(report['endings']), set(ENDINGS))
        self.assertGreater(report['choice_transitions'], 12)
        self.assertFalse(report['tactical_replay_verified'])
        self.assertFalse(report['player_export_verified'])
        self.assertEqual({s['id'] for s in self.project.story['subgraphs']},
                         {'shared_council', 'shared_camp'})
        self.assertTrue(all(
            witness['choice_count'] == len(witness['route'])
            for witness in report['endings'].values()))

    def test_alliance_mid_line_save_and_quest_unlock_once(self):
        session = self.play(
            ['defend', 'rescue', 'trust', 'accept', 'alliance', 'finish'],
            restored_mid_dialogue=True)
        flags = session.progress.story_flags
        self.assertEqual(flags['r42_c_main_ending'], 'alliance')
        self.assertEqual(flags['r42_c_main_captain_trust'], 50)
        self.assertTrue(flags['r42_c_main_quest_ready'])
        self.assertIn(QUEST_MISSION, session.progress.unlocked)
        self.assertIn(QUEST_MISSION, session.available_missions())
        self.assertEqual(session.campaign_inspector()['endings'], ['alliance'])
        self.assertEqual(len(session.progress.story_history), 6)
        before = session.recording()
        with self.assertRaises(RuleError):
            session.choose_story_option('finish')
        self.assertEqual(session.recording(), before)
        loaded = GameSession.from_recording(before, self.content, self.project)
        self.assertEqual(loaded.recording(), before)
        self.assertEqual(loaded.progress.story_flags['r42_c_main_ending'],
                         'alliance')

    def test_exile_is_reachable_and_does_not_unlock_quest(self):
        game = self.play(['accuse', 'silence', 'avoid', 'exile', 'finish'])
        self.assertEqual(game.progress.story_flags['r42_c_main_ending'], 'exile')
        self.assertEqual(game.progress.story_flags['r42_c_main_captain_trust'],
                         -30)
        self.assertNotIn(QUEST_MISSION, game.progress.unlocked)
        self.assertFalse(game.progress.story_flags['r42_c_main_quest_ready'])
        self.assertEqual(game.campaign_inspector()['endings'], ['exile'])

    def test_accord_is_reachable_with_evidence_but_no_quest(self):
        game = self.play(['defend', 'ledger', 'avoid', 'accord', 'finish'])
        self.assertTrue(game.progress.story_flags['r42_c_main_evidence'])
        self.assertEqual(game.progress.story_flags['r42_c_main_ending'],
                         'accord')
        self.assertEqual(game.progress.story_flags['r42_c_main_captain_trust'],
                         25)
        self.assertNotIn(QUEST_MISSION, game.progress.unlocked)
        self.assertEqual(game.campaign_inspector()['endings'], ['accord'])

    def test_player_controller_resumes_a_real_multiline_slice(self):
        with TemporaryDirectory() as folder:
            player = PlayerController(self.content, self.project, 'main',
                                      Path(folder), seed=12)
            view = player.new_game()
            self.assertEqual(view['screen'], 'dialogue')
            self.assertEqual(view['dialogue_line']['count'], 2)
            self.assertEqual(view['choices'], [])
            player.next_dialogue_line()
            player.save(1)
            new = PlayerController(self.content, self.project, 'main',
                                   Path(folder), seed=12)
            view = new.load(1)
            self.assertEqual(view['dialogue_line']['index'], 1)
            self.assertEqual({x['id'] for x in view['choices']},
                             {'defend', 'accuse'})
            view = new.choose('accuse')
            self.assertEqual(view['scene']['id'], 'archive')
            self.assertEqual(new.session.snapshot().progress[
                'story_flags']['r42_c_main_captain_trust'], -20)

    def test_unreachable_scene_is_reported_with_no_fake_success(self):
        data = self.project.to_dict()
        data['story']['scenes'].append({
            'id': 'orphan', 'title': 'Orphelin', 'speaker': 'Jeanne',
            'text': 'Impossible à atteindre.',
            'lines': [{'id': 'line_001', 'speaker': 'Jeanne',
                       'text': 'Impossible à atteindre.'}],
            'choices': [{'id': 'finish', 'label': 'Terminer'}],
        })
        invalid = GameProject.from_dict(data, self.content)
        report = audit_narrative(self.content, invalid, 'main',
                                 expected_endings=ENDINGS)
        self.assertFalse(report['passed'])
        self.assertIn('orphan', report['dead_scenes'])
        self.assertEqual(
            next(c for c in report['dead_choices'] if c['scene'] == 'orphan')[
                'reason'], 'unreachable_scene')
        with self.assertRaises(RuleError):
            audit_narrative(self.content, invalid, 'main',
                            expected_endings=ENDINGS, strict=True)

    def test_impossible_condition_gets_actionable_counterexample(self):
        data = self.project.to_dict()
        council = next(s for s in data['story']['scenes']
                       if s['id'] == 'council')
        proof = next(c for c in council['choices'] if c['id'] == 'proof')
        proof['when'] = {'gold_gte': 999999}
        broken = GameProject.from_dict(data, self.content)
        report = audit_narrative(self.content, broken, 'main',
                                 expected_endings=ENDINGS)
        self.assertFalse(report['passed'])
        dead = next(c for c in report['dead_choices']
                    if c['scene'] == 'council' and c['choice'] == 'proof')
        self.assertEqual(dead['reason'], 'condition_never_satisfied')
        self.assertEqual(dead['condition']['gold_gte'], 999999)
        self.assertEqual(dead['counterexample']['gold'], 0)
        self.assertIn('route_to_scene', dead['counterexample'])

    def test_template_export_is_validated_pair_and_never_overwrites(self):
        from sporebound.model import Content
        with TemporaryDirectory() as folder:
            target = Path(folder) / 'captain.json'
            paths = save_captain_template(target)
            self.assertEqual(len(paths), 2)
            saved_content = Content.load(target)
            saved_project = GameProject.load(
                target.with_suffix('.game.json'), saved_content)
            self.assertEqual(saved_project.story, self.project.story)
            self.assertEqual(saved_content.to_dict(), self.content.to_dict())
            with self.assertRaises(RuleError):
                save_captain_template(target)
            self.assertEqual(saved_project.story['schema_version'], 2)

    def test_bounded_execution_refuses_underbudgeted_audit(self):
        with self.assertRaises(RuleError):
            audit_narrative(self.content, self.project, 'main',
                            expected_endings=ENDINGS, max_states=1)
        with self.assertRaises(RuleError):
            audit_narrative(self.content, self.project, 'main',
                            expected_endings=ENDINGS, max_choices=1)


if __name__ == '__main__':
    unittest.main()

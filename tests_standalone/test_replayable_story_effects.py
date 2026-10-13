"""3.7.21F — battle-journalled choice effects, deterministic replay and validation."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.engine import Battle
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from sporebound.story_authoring import add_tactical_effect
from tests_standalone.test_tactical_dialogue import authored_fixture


class ReplayableTacticalChoiceTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = authored_fixture()

    def _author(self, effects):
        project = self.project
        for effect in effects:
            project = add_tactical_effect(
                project, self.content, 'lever_question', 'help', effect)
        return project

    def test_door_hazard_status_and_reinforcement_replay_identically(self):
        effects = [
            {'kind': 'open_door', 'object': 'gate'},
            {'kind': 'status', 'unit': 'ziggy', 'status': 'haste', 'duration': 10},
            {'kind': 'hazard', 'pos': [1, 6], 'amount': 6},
            {'kind': 'wave', 'actors': [
                {'id': 'choice_reinforcement', 'name': 'Renfort', 'team': 'player',
                 'pos': [0, 6]}], 'max_active': 20},
        ]
        project = self._author(effects)
        session = GameSession.new(self.content, project, 'main')
        battle = session.start_mission('garden')
        self.assertTrue(battle.board.tile((4, 1)).blocked)
        original_commands = deepcopy(battle.commands)
        self.assertEqual(session.tactical_story_pending, 'lever_question')
        session.choose_tactical_story_option('help')
        self.assertEqual(len(battle.commands), len(original_commands) + 1)
        self.assertEqual(battle.commands[-1], {
            'kind': 'story_effects', 'scene': 'lever_question', 'choice': 'help',
            'effects': effects})
        self.assertFalse(battle.board.tile((4, 1)).blocked)
        self.assertTrue(next(o for o in battle.mission.objects
                             if o['id'] == 'gate')['open'])
        self.assertEqual(battle.unit('ziggy').statuses['haste'], 10)
        self.assertEqual(battle.board.tile((1, 6)).hazard, 6)
        self.assertTrue(battle.unit('choice_reinforcement').alive)
        self.assertIn('reinforcement_wave', [event['kind'] for event in battle.events])
        self.assertEqual(Battle.replay(battle.recording()).digest(), battle.digest())
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'checkpoint.json'
            session.save(path)
            restored = GameSession.load(path, self.content, project)
            self.assertEqual(restored.recording(), session.recording())
            self.assertEqual(restored.battle.digest(), battle.digest())
            restored.choose_tactical_story_option('continue')
            restored.choose_tactical_story_option('wait')
            self.assertEqual(
                len([c for c in restored.battle.commands
                     if c['kind'] == 'story_effects']), 3)
            self.assertEqual(
                GameSession.from_recording(
                    restored.recording(), self.content, project).recording(),
                restored.recording())

    def test_invalid_authoring_rejected_and_old_story_choices_still_work(self):
        for effect in (
            {'kind': 'open_door', 'object': 'missing'},
            {'kind': 'open_door', 'object': 'switch'},
            {'kind': 'status', 'unit': 'missing', 'status': 'haste', 'duration': 4},
            {'kind': 'hazard', 'pos': [-1, 0], 'amount': 3},
            {'kind': 'wave', 'actors': []},
            {'kind': 'unknown', 'object': 'gate'},
        ):
            with self.subTest(effect=effect), self.assertRaises(RuleError):
                self._author([effect])
        session = GameSession.new(self.content, self.project, 'main')
        session.start_mission('garden')
        session.choose_tactical_story_option('ignore')
        self.assertEqual(session.battle.commands[-1]['effects'], [])
        self.assertFalse(session.progress.story_flags['village_saved'])
        self.assertEqual(
            Battle.replay(session.battle.recording()).digest(),
            session.battle.digest())

    def test_failed_tactical_effect_rolls_back_battle_and_choice(self):
        project = self._author([
            {'kind': 'open_door', 'object': 'gate'},
            {'kind': 'wave', 'actors': [
                {'id': 'collision_reinforcement', 'name': 'Collision',
                 'team': 'enemy', 'pos': [1, 5]}]}])
        session = GameSession.new(self.content, project, 'main')
        session.start_mission('garden')
        before = session.recording()
        with self.assertRaises(RuleError):
            session.choose_tactical_story_option('help')
        self.assertEqual(session.recording(), before)
        self.assertTrue(session.battle.board.tile((4, 1)).blocked)

    def test_save_checks_author_choice_identity_after_valid_replay(self):
        project = self._author([{'kind': 'open_door', 'object': 'gate'}])
        session = GameSession.new(self.content, project, 'main')
        session.start_mission('garden')
        session.choose_tactical_story_option('help')
        row = session.recording()
        row['progress']['story_history'][-1]['choice'] = 'ignore'
        row['digest'] = digest({k: v for k, v in row.items()
                                if k != 'digest'})
        with self.assertRaises(RuleError):
            GameSession.from_recording(row, self.content, project)

    def test_player_direct_commands_cannot_inject_authored_story_effects(self):
        project = self._author([{'kind': 'open_door', 'object': 'gate'}])
        session = GameSession.new(self.content, project, 'main')
        session.start_mission('garden')
        with self.assertRaises(RuleError):
            session.execute({'kind': 'story_effects', 'scene': 'lever_question',
                             'choice': 'help',
                             'effects': [{'kind': 'open_door', 'object': 'gate'}]})


if __name__ == '__main__':
    unittest.main()

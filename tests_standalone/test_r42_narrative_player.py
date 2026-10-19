"""R42.B2: saved multi-line Player progression through canonical GameSession."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.simulation import Simulation, SimulationError, thaw
from drawtemp.player.controller import PlayerController
from sporebound.game_session import GameSession, digest
from sporebound.game_project import GameProject
from sporebound.model import RuleError
from sporebound.narrative_r42 import migrate_story_v1, set_dialogue_lines
from sporebound.narrative_playback_r42 import CURSOR


class NarrativePlayerR42Tests(unittest.TestCase):
    def setUp(self):
        self.content, old = reference_project()
        upgraded = migrate_story_v1(old, self.content)
        self.project = set_dialogue_lines(upgraded, self.content, 'arrival', [
            {'id': 'intro', 'speaker': 'Jeanne', 'text': 'Bonjour capitaine.'},
            {'id': 'reply', 'speaker': 'Capitaine', 'text': 'Bonjour Jeanne.'},
            {'id': 'promise', 'speaker': 'Jeanne', 'text': 'En route !'},
        ])

    def test_game_session_checkpoint_mid_dialogue_without_rewards(self):
        session = GameSession.new(self.content, self.project, 'main')
        self.assertEqual(session.narrative_line()['id'], 'intro')
        first = session.recording()
        with self.assertRaises(RuleError):
            session.choose_story_option('enter')
        self.assertEqual(session.recording(), first)
        session.advance_narrative_line()
        self.assertEqual(session.narrative_line()['id'], 'reply')
        checkpoint = session.recording()
        restored = GameSession.from_recording(checkpoint, self.content, self.project)
        self.assertEqual(restored.recording(), checkpoint)
        self.assertEqual(restored.narrative_line()['speaker'], 'Capitaine')
        restored.advance_narrative_line()
        self.assertTrue(restored.narrative_line()['complete'])
        restored.choose_story_option('enter')
        self.assertIsNone(restored.active_scene())
        self.assertEqual(restored.progress.story_history,
                         [{'scene': 'arrival', 'choice': 'enter'}])
        self.assertEqual(restored.progress.story_flags[CURSOR], 0)
        with self.assertRaises(RuleError):
            restored.choose_story_option('enter')

    def test_simulation_revision_and_transactional_rollback(self):
        simulation = Simulation.new(self.content, self.project, 'main')
        first = simulation.snapshot()
        self.assertEqual(thaw(simulation.narrative_line())['count'], 3)
        with self.assertRaises(SimulationError):
            simulation.choose_story_option('enter', expected_revision=first.revision)
        self.assertEqual(simulation.snapshot().revision, first.revision)
        simulation.advance_narrative_line(expected_revision=first.revision)
        self.assertEqual(simulation.snapshot().revision, first.revision + 1)
        with self.assertRaises(SimulationError) as stale:
            simulation.advance_narrative_line(expected_revision=first.revision)
        self.assertEqual(stale.exception.code, 'stale_revision')
        self.assertEqual(thaw(simulation.narrative_line())['index'], 1)

    def test_player_controller_renders_active_line_and_gates_choice(self):
        with TemporaryDirectory() as folder:
            controller = PlayerController(self.content, self.project, 'main',
                                          Path(folder), seed=3)
            view = controller.new_game()
            self.assertEqual(view['dialogue_line']['index'], 0)
            self.assertEqual(view['scene']['speaker'], 'Jeanne')
            self.assertEqual(view['choices'], [])
            with self.assertRaises(ValueError):
                controller.choose('enter')
            view = controller.next_dialogue_line()
            self.assertEqual(view['scene']['speaker'], 'Capitaine')
            self.assertEqual(view['choices'], [])
            controller.save(1)
            loaded = PlayerController(self.content, self.project, 'main',
                                      Path(folder), seed=3)
            restored = loaded.load(1)
            self.assertEqual(restored['dialogue_line']['id'], 'reply')
            self.assertEqual(loaded.next_dialogue_line()['dialogue_line']['index'], 2)
            self.assertEqual([c['id'] for c in loaded.state()['choices']], ['enter'])
            after = loaded.choose('enter')
            self.assertEqual(after['dialogue_line'], {})
            self.assertEqual(loaded.session.snapshot().progress['story_history'][-1]
                             ['choice'], 'enter')

    def test_recomputed_checksum_cannot_hide_cursor_corruption(self):
        game = GameSession.new(self.content, self.project, 'main')
        original = game.recording()
        for val in (True, -1, 99, '1'):
            rec = deepcopy(original)
            rec['progress']['story_flags'][CURSOR] = val
            rec['digest'] = digest({k: v for k, v in rec.items() if k != 'digest'})
            with self.subTest(value=val), self.assertRaises(RuleError):
                GameSession.from_recording(rec, self.content, self.project)
        self.assertEqual(game.recording(), original)

    def test_legacy_progress_cursor_absent_and_unchanged(self):
        _, legacy = reference_project()
        game = GameSession.new(self.content, legacy, 'main')
        self.assertNotIn(CURSOR, game.progress.story_flags)
        self.assertIsNone(game.narrative_line())
        game.choose_story_option('enter')
        self.assertNotIn(CURSOR, game.progress.story_flags)


if __name__ == '__main__':
    unittest.main()

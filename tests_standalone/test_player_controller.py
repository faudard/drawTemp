"""Unified player flow: slots, story, tactical autosave and front commands."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController


class PlayerControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)
        cls.project = GameProject.load(Path(DEFAULT_CONTENT).with_suffix('.game.json'),
                                       cls.content)

    def test_story_and_battle_persist_through_resume(self):
        with TemporaryDirectory() as folder:
            ui = PlayerController(self.content, self.project, Path(folder) / 'profile')
            ui.new_game('relique', 1, seed=33)
            self.assertIsNotNone(ui.session.active_scene())
            ui.choose_story_option('guard')
            resumed = PlayerController(self.content, self.project, Path(folder) / 'profile')
            resumed.load_game('relique', 1)
            self.assertEqual(resumed.session.recording(), ui.session.recording())
            ui.choose_story_option('provisions')
            ui.start_mission('crown')
            resumed.load_game('relique', 1)
            self.assertEqual(resumed.session.recording(), ui.session.recording())

    def test_rejected_action_keeps_checkpoint_and_state(self):
        with TemporaryDirectory() as folder:
            ui = PlayerController(self.content, self.project, Path(folder) / 'profile')
            ui.new_game('main', 1)
            ui.start_mission('garden')
            path = ui.store().path
            before = path.read_bytes()
            recording = ui.session.recording()
            with self.assertRaises(RuleError):
                ui.execute({'kind': 'not-a-command'})
            self.assertEqual(before, path.read_bytes())
            self.assertEqual(recording, ui.session.recording())

    def test_fronts_and_timeline_roundtrip(self):
        with TemporaryDirectory() as folder:
            ui = PlayerController(self.content, self.project, Path(folder) / 'profile')
            ui.new_game('main', 1)
            # Test setup supplies two unlocked missions; front authorization stays enforced.
            ui.session.progress.unlocked.append('escape')
            ui.save()
            ui.start_fronts({'garden': 'garden', 'escape': 'escape'}, 'garden')
            ui.set_doctrine('escape', 'delay')
            ui.advance_fronts()
            ui.switch_front('escape')
            other = PlayerController(self.content, self.project, Path(folder) / 'profile')
            other.load_game('main', 1)
            self.assertEqual(other.session.recording(), ui.session.recording())

    def test_slot_overwrite_requires_explicit_choice(self):
        with TemporaryDirectory() as folder:
            ui = PlayerController(self.content, self.project, Path(folder) / 'profile')
            ui.new_game('main', 1)
            with self.assertRaises(RuleError):
                ui.new_game('main', 1)
            ui.new_game('main', 1, overwrite=True)
            self.assertEqual(ui.session.mode, 'campaign')


if __name__ == '__main__':
    unittest.main()

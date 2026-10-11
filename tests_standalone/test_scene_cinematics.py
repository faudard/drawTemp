"""3.3.4: scene cinema/audio must follow authentic narrative + verified replay."""
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from tests_standalone.test_strategic_narrative_bridge import fixtures
from sporebound.authored_siege_player import AuthoredSiegeController
from sporebound.cinematics import (cinematic_template, event_template,
                                   matching_cinematics, validate_cinematics)
from sporebound.game_project import GameProject
from sporebound.game_session import digest
from sporebound.model import RuleError


def cinematic_project():
    content, bp, project = fixtures()
    first = cinematic_template("lever_reveal", "La porte est ouverte",
                               "scene", "breach")
    first['duration_ms'] = 3000
    bg = event_template('background', 'walls', 0, 3000)
    cam = event_template('camera', 'camera', 0, 2000)
    cam['to'] = [0.2, -0.1]
    line = event_template('dialogue', 'jeanne_line', 1000, 1800)
    line.update(speaker="Jeanne", text="Nous entrons dans la forteresse !")
    music = event_template('sound', 'rally_music', 0, 3000)
    music.update(cue='jeanne_theme', bus='music', loop=True, volume=75,
                 fade_in_ms=300, fade_out_ms=500)
    first['events'] = [bg, cam, line, music]
    second = cinematic_template("army_charge", "La charge", "scene", "breach")
    second['duration_ms'] = 1000
    second['events'] = [
        event_template('actor', 'march', 0, 1000),
        {**event_template('sound', 'horn', 0, 1000),
         'cue': 'war_horn', 'bus': 'sfx', 'volume': 80},
    ]
    project.cinematics = [first, second]
    project.validate(content)
    return content, bp, project


def start_at_breach(content, bp, project, path):
    ctl = AuthoredSiegeController(content, bp, path, project=project)
    ctl.new_game()
    ctl.execute({'kind': 'start_battle'})
    ctl.execute({'kind': 'interact', 'object': 'portcullis_lever'})
    return ctl


class SceneCinematicTests(unittest.TestCase):
    def test_trigger_validation_and_scene_editor_contract(self):
        content, bp, project = cinematic_project()
        self.assertEqual(
            [row['id'] for row in matching_cinematics(project, 'scene', 'breach')],
            ['lever_reveal', 'army_charge'])
        for tamper in (
            {'kind': 'scene', 'target': 'missing'},
            {'kind': 'after_mission', 'target': 'breach'},
        ):
            changed = deepcopy(project)
            changed.cinematics[0]['trigger'] = tamper
            with self.subTest(tamper=tamper), self.assertRaises(RuleError):
                changed.validate(content)
        with self.assertRaises(RuleError):
            validate_cinematics(project.cinematics, content, project.campaigns)
        # Legacy authoring with no cinematic scene trigger still validates.
        old = deepcopy(project)
        old.cinematics = []
        old.validate(content)

    def test_real_walls_to_gate_to_cutscene_audio_to_scene_resume(self):
        content, bp, project = cinematic_project()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'game.game.json'
            ctl = start_at_breach(content, bp, project, path)
            self.assertTrue(ctl.session.fronts.front_overrides['gate']['main_gate']['open'])
            self.assertEqual(ctl.active_scene()['id'], 'breach')
            self.assertEqual(ctl.story.recording()['version'], 3)
            self.assertEqual(ctl.pending_cinematic()['id'], 'lever_reveal')
            self.assertEqual(
                {e.get('bus') for e in ctl.pending_cinematic()['events']
                 if e['kind'] == 'sound'}, {'music'})
            with self.assertRaises(RuleError):
                ctl.choose_story_option('continue')  # UI and headless parity.
            with self.assertRaises(RuleError):
                ctl.acknowledge_cinematic('army_charge')  # Must be ordered.
            ctl.acknowledge_cinematic('lever_reveal')
            self.assertEqual(ctl.pending_cinematic()['id'], 'army_charge')

            # Load after skipping only the first cinematic. Second is still due.
            from_slot = AuthoredSiegeController(content, bp, path, project=project)
            from_slot.continue_game()
            self.assertEqual(from_slot.pending_cinematic()['id'], 'army_charge')
            self.assertEqual(from_slot.story.recording(), ctl.story.recording())
            from_slot.acknowledge_cinematic('army_charge')
            self.assertIsNone(from_slot.pending_cinematic())
            from_slot.choose_story_option('continue')
            self.assertTrue(from_slot.story.progress.story_flags['gate_opened'])
            self.assertIsNone(from_slot.active_scene())
            restored = AuthoredSiegeController(content, bp, path, project=project)
            restored.continue_game()
            self.assertEqual(restored.story.recording(),
                             from_slot.story.recording())
            self.assertIsNone(restored.pending_cinematic())
            self.assertEqual([ev['kind'] for ev in restored.story.events],
                             ['strategic', 'cinematic', 'cinematic', 'choice'])

    def test_disk_failure_rolls_back_acknowledgement(self):
        content, bp, project = cinematic_project()
        with TemporaryDirectory() as tmp:
            ctl = start_at_breach(content, bp, project,
                                  Path(tmp) / 'game.game.json')
            before = ctl.story.recording()
            with patch.object(ctl, 'save', side_effect=OSError('out of space')):
                with self.assertRaises(OSError):
                    ctl.acknowledge_cinematic('lever_reveal')
            self.assertEqual(ctl.story.recording(), before)
            self.assertEqual(ctl.pending_cinematic()['id'], 'lever_reveal')

    def test_forged_early_duplicate_and_omitted_completion_rejected(self):
        content, bp, project = cinematic_project()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'game.game.json'
            ctl = start_at_breach(content, bp, project, path)
            ctl.acknowledge_cinematic('lever_reveal')
            real = json.loads(ctl.save_path.read_text(encoding='utf-8'))
            for change in ('omit', 'early', 'duplicate', 'wrong_scene'):
                corrupted = deepcopy(real)
                events = corrupted['narrative']['events']
                if change == 'omit':
                    events.pop()
                elif change == 'early':
                    events[-1]['at'] = 1
                elif change == 'duplicate':
                    events.append(deepcopy(events[-1]))
                elif change == 'wrong_scene':
                    events[-1]['scene'] = 'not_active'
                body = {k: v for k, v in corrupted['narrative'].items()
                        if k != 'digest'}
                corrupted['narrative']['digest'] = digest(body)
                ctl.save_path.write_text(
                    json.dumps(corrupted), encoding='utf-8')
                with self.subTest(change=change), self.assertRaises(RuleError):
                    AuthoredSiegeController(
                        content, bp, path, project=project).continue_game()
            ctl.save()
            roundtrip = AuthoredSiegeController(content, bp, path, project=project)
            roundtrip.continue_game()
            self.assertEqual(ctl.story.recording(), roundtrip.story.recording())

    def test_previous_v2_recording_without_cinematics_is_byte_identical(self):
        content, bp, project = cinematic_project()
        project.cinematics = []
        with TemporaryDirectory() as tmp:
            ctl = start_at_breach(content, bp, project, Path(tmp)/'old.game.json')
            self.assertEqual(ctl.story.recording()['version'], 2)
            self.assertFalse(any(e['kind'] == 'cinematic'
                                 for e in ctl.story.events))
            original = ctl.story.recording()
            ctl.choose_story_option('continue')
            again = AuthoredSiegeController(content, bp, ctl.project_path,
                                            project=project)
            again.continue_game()
            self.assertEqual(again.story.recording(), ctl.story.recording())
            self.assertEqual(set(again.story.recording()), {
                'version', 'project_digest', 'baseline', 'events',
                'state_digest', 'digest'})


if __name__ == '__main__':
    unittest.main()

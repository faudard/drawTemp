"""3.3.2 — Verified tactical event -> cross-front effect -> narrative scene."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.siege_scenarios import siege_content
from sporebound import strategic_events, story_authoring
from sporebound.authored_siege_player import AuthoredSiegeController
from sporebound.game_project import GameProject
from sporebound.game_session import digest
from sporebound.model import Content, RuleError
from sporebound.siege_authoring import new_blueprint, add_front, replace_siege


def fixtures():
    data = siege_content().to_dict()
    # Move the remparts lever next to the starting party, so the test uses a
    # real legal Battle.interact without simulating a battle or forging events.
    walls = next(m for m in data['missions'] if m['id'] == 'castle_ramparts')
    lever = next(o for o in walls['objects'] if o['id'] == 'portcullis_lever')
    lever['pos'] = [2, 3]
    content = Content.from_dict(data)
    bp = new_blueprint('castle_causal', 'main', 'castle_ramparts', front='walls')
    bp = add_front(bp, 'gate', 'castle_ram')
    bp = strategic_events.upsert(bp, content, {
        'id': 'open_portcullis',
        'when': {'all': [
            {'battle_event': {'front': 'walls', 'kind': 'interact',
                              'value': 'portcullis_lever'}},
            {'not': {'front_status': {'front': 'gate', 'status': 'defeat'}}}
        ]},
        'effects': [{'kind': 'open_door', 'front': 'gate',
                     'object': 'main_gate'},
                    {'kind': 'signal', 'text': 'La herse est ouverte.'}],
    })
    project = replace_siege(GameProject.default(content), content, bp)
    project.story = {
        'scenes': [
            {'id': 'breach', 'title': 'Les remparts', 'speaker': 'Jeanne',
             'text': 'La porte est ouverte !',
             'choices': [{'id': 'continue', 'label': 'Avancer',
                          'effects': [{'kind': 'set_flag',
                                       'flag': 'gate_opened', 'value': True}]}]},
        ],
        'after_strategic_event': {'castle_causal/open_portcullis': 'breach'},
    }
    project.validate(content)
    return content, bp, project


class StrategicNarrativeBridgeTests(unittest.TestCase):
    def test_authentic_event_opens_unloaded_gate_and_scene_is_journaled_once(self):
        content, bp, project = fixtures()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'castle.game.json'
            controller = AuthoredSiegeController(content, bp, path, project=project)
            controller.new_game()
            self.assertEqual(controller.story.recording()['version'], 2)
            self.assertIsNone(controller.active_scene())
            self.assertNotIn('gate', controller.session.fronts.battles)
            controller.execute({'kind': 'start_battle'})
            self.assertIsNone(controller.active_scene())
            self.assertNotIn('open_portcullis', controller.session.fronts.fired_graph)
            controller.execute({'kind': 'interact', 'object': 'portcullis_lever'})
            self.assertIn('open_portcullis', controller.session.fronts.fired_graph)
            self.assertTrue(controller.session.fronts.front_overrides[
                'gate']['main_gate']['open'])
            self.assertEqual(controller.active_scene()['id'], 'breach')
            self.assertEqual([event['kind'] for event in controller.story.events],
                             ['strategic'])
            with self.assertRaises(RuleError):
                controller.advance()  # Pause at a narrative decision.
            controller.choose_story_option('continue')
            self.assertTrue(controller.story.progress.story_flags['gate_opened'])
            self.assertIsNone(controller.active_scene())
            loaded = AuthoredSiegeController(content, bp, path, project=project)
            loaded.continue_game()
            self.assertEqual(loaded.story.recording(), controller.story.recording())
            self.assertEqual(loaded.session.fronts.digest(),
                             controller.session.fronts.digest())

    def test_no_action_no_scene_and_old_recording_stays_v1(self):
        content, bp, project = fixtures()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'castle.game.json'
            controller = AuthoredSiegeController(content, bp, path, project=project)
            controller.new_game()
            controller.advance()
            self.assertIsNone(controller.active_scene())
            self.assertEqual(controller.story.events, [])
            self.assertNotIn('open_portcullis', controller.session.fronts.fired_graph)
        old = deepcopy(project)
        old.story.pop('after_strategic_event')
        old.validate(content)
        with TemporaryDirectory() as tmp:
            controller = AuthoredSiegeController(
                content, bp, Path(tmp)/'legacy.game.json', project=old)
            controller.new_game()
            self.assertEqual(controller.story.recording()['version'], 1)
            self.assertEqual(controller.story.events, [])

    def test_forged_or_omitted_strategic_narrative_journal_is_rejected(self):
        content, bp, project = fixtures()
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'castle.game.json'
            ctl = AuthoredSiegeController(content, bp, path, project=project)
            ctl.new_game()
            ctl.execute({'kind': 'start_battle'})
            ctl.execute({'kind': 'interact', 'object': 'portcullis_lever'})
            actual = json.loads(ctl.save_path.read_text(encoding='utf-8'))
            for events in ([], [{'kind': 'strategic',
                                 'node': 'open_portcullis', 'at': 1}],
                           [{'kind': 'strategic',
                             'node': 'other', 'at': 2}]):
                modified = deepcopy(actual)
                modified['narrative']['events'] = events
                body = {k: v for k, v in modified['narrative'].items()
                        if k != 'digest'}
                modified['narrative']['digest'] = digest(body)
                ctl.save_path.write_text(json.dumps(modified), encoding='utf-8')
                with self.subTest(events=events), self.assertRaises(RuleError):
                    AuthoredSiegeController(
                        content, bp, path, project=project).continue_game()
            ctl.save()
            good = AuthoredSiegeController(content, bp, path, project=project)
            good.continue_game()

    def test_authoring_links_validate_references_and_undo_is_transactional(self):
        content, bp, project = fixtures()
        plain = deepcopy(project)
        plain.story.pop('after_strategic_event')
        changed = story_authoring.set_strategic_scene(
            plain, content, 'castle_causal', 'open_portcullis', 'breach')
        self.assertEqual(changed.story['after_strategic_event'],
                         project.story['after_strategic_event'])
        self.assertNotIn('after_strategic_event', plain.story)
        for siege, node, scene in [('castle_causal', 'missing', 'breach'),
                                   ('missing', 'open_portcullis', 'breach'),
                                   ('castle_causal', 'open_portcullis', 'missing')]:
            with self.subTest(node=node), self.assertRaises(RuleError):
                story_authoring.set_strategic_scene(
                    plain, content, siege, node, scene)
        self.assertNotIn('after_strategic_event', plain.story)
        removed = story_authoring.set_strategic_scene(
            changed, content, 'castle_causal', 'open_portcullis')
        self.assertNotIn('after_strategic_event', removed.story)


if __name__ == '__main__':
    unittest.main()

"""Game Studio 4.0 — 3.3.3 transactional campaign/siege assembly gates."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.siege_scenarios import siege_content
from sporebound.game_project import GameProject
from sporebound.fronts import MultiFrontSession
from sporebound.model import Content, RuleError
from sporebound.siege_authoring import make_session
from sporebound.studio_siege_flow import (
    build_guided_siege, prepare_deployment, readiness)


MISSIONS = ('castle_ramparts', 'castle_ram', 'castle_throne')


class GuidedSiegeTests(unittest.TestCase):
    def setUp(self):
        self.content = siege_content()
        self.project = GameProject.default(self.content)

    def build(self, **kw):
        return build_guided_siege(
            self.project, self.content, siege_id='jeanne_castle',
            campaign_id='main', missions=MISSIONS, **kw)

    def test_build_three_fronts_resources_and_real_locked_final(self):
        before = self.project.to_dict()
        created = self.build(reserves=4, supplies=9, escorts=2, capacity=3)
        self.assertEqual(before, self.project.to_dict())
        self.assertEqual(len(created.sieges), 1)
        siege = created.sieges[0]
        self.assertEqual(siege['fronts'], {
            'walls': 'castle_ramparts',
            'gate': 'castle_ram',
            'throne': 'castle_throne',
        })
        self.assertEqual(siege['campaign']['final_front'], 'throne')
        self.assertEqual(siege['campaign']['required_fronts'],
                         {'walls': ['victory'], 'gate': ['victory']})
        self.assertEqual(siege['logistics']['reserves']['player'], 4)
        self.assertEqual(siege['logistics']['supplies']['player'], 9)
        self.assertEqual(siege['logistics']['escorts'], 2)
        self.assertEqual(siege['logistics']['capacity'], 3)
        self.assertEqual(
            {(row['from'], row['to']) for row in siege['logistics']['routes']},
            {('reserve', 'walls'), ('reserve', 'gate'), ('reserve', 'throne')})
        run = make_session(siege, self.content)
        with self.assertRaises(RuleError):
            run.switch('throne')
        run.switch('gate')
        self.assertEqual(run.timeline.focused, 'gate')
        self.assertEqual(MultiFrontSession.replay(run.recording()).digest(),
                         run.digest())
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'siege.game.json'
            created.save(path, self.content)
            self.assertEqual(GameProject.load(path, self.content).sieges, created.sieges)

    def test_explicit_lever_and_door_link_stays_tactical(self):
        created = self.build(link_lever='portcullis_lever', link_door='main_gate')
        node = created.sieges[0]['event_graph'][0]
        self.assertEqual(node['id'], 'walls_open_gate')
        self.assertEqual(node['when'], {'battle_event': {
            'front': 'walls', 'kind': 'interact', 'value': 'portcullis_lever'}})
        self.assertEqual(node['effects'], [
            {'kind': 'open_door', 'front': 'gate', 'object': 'main_gate'}])
        session = make_session(created.sieges[0], self.content)
        self.assertNotIn('gate', session.front_overrides)
        session.advance()
        self.assertNotIn('walls_open_gate', session.fired_graph)
        self.assertNotIn('gate', session.front_overrides)

    def test_authentic_walls_interaction_opens_gate_on_unloaded_front(self):
        raw = self.content.to_dict()
        walls = next(row for row in raw['missions']
                     if row['id'] == 'castle_ramparts')
        lever = next(o for o in walls['objects'] if o['id'] == 'portcullis_lever')
        lever['pos'] = [2, 3]
        content = Content.from_dict(raw)
        project = build_guided_siege(
            self.project, content, siege_id='authentic',
            campaign_id='main', missions=MISSIONS,
            link_lever='portcullis_lever', link_door='main_gate')
        session = make_session(project.sieges[0], content)
        self.assertNotIn('gate', session.battles)
        session.execute({'kind': 'start_battle'})
        self.assertNotIn('walls_open_gate', session.fired_graph)
        session.execute({'kind': 'interact', 'object': 'portcullis_lever'})
        self.assertIn('walls_open_gate', session.fired_graph)
        self.assertTrue(session.front_overrides['gate']['main_gate']['open'])
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_wrong_ids_missing_partner_and_invalid_budget_leave_project_unchanged(self):
        saved = deepcopy(self.project.to_dict())
        variants = (
            {'missions': ('castle_ram', 'castle_ram', 'castle_throne')},
            {'missions': ('missing', 'castle_ram', 'castle_throne')},
            {'link_lever': 'portcullis_lever'},
            {'link_lever': 'not_real', 'link_door': 'main_gate'},
            {'link_lever': 'portcullis_lever', 'link_door': 'not_real'},
            {'reserves': -1},
            {'supplies': -1},
            {'capacity': 0},
            {'escorts': 1.5},
        )
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(RuleError):
                settings = dict(variant)
                missions = settings.pop('missions', MISSIONS)
                build_guided_siege(
                    self.project, self.content, siege_id='invalid',
                    campaign_id='main', missions=missions, **settings)
            self.assertEqual(self.project.to_dict(), saved)

    def test_does_not_overwrite_existing_siege_or_campaign_start_implicitly(self):
        old_start = self.project.campaign('main')['start_mission']
        created = self.build()
        self.assertEqual(created.campaign('main')['start_mission'], old_start)
        changed = self.build(set_campaign_start=True)
        self.assertEqual(changed.campaign('main')['start_mission'], MISSIONS[0])
        self.assertEqual(self.project.campaign('main')['start_mission'], old_start)
        with self.assertRaises(RuleError):
            build_guided_siege(
                created, self.content, siege_id='jeanne_castle',
                campaign_id='main', missions=MISSIONS)

    def test_prepare_deployment_zones_is_explicit_and_one_content_transaction(self):
        raw = self.content.to_dict()
        for mission in raw['missions']:
            if mission['id'] in MISSIONS:
                mission['deployment'] = []
        content = Content.from_dict(raw)
        original = deepcopy(raw)
        diagnostics = readiness(content, MISSIONS)
        self.assertEqual(sum('déploiement' in row[2] for row in diagnostics), 3)
        upgraded = prepare_deployment(raw, self.project, MISSIONS)
        self.assertEqual(raw, original)
        made = Content.from_dict(upgraded)
        self.assertEqual(len(made.missions), len(content.missions))
        for mid in MISSIONS:
            self.assertEqual(made.missions[mid].deployment[0]['id'], 'studio_start')
        # A second call preserves all existing cells exactly.
        self.assertEqual(prepare_deployment(upgraded, self.project, MISSIONS), upgraded)
        with self.assertRaises(RuleError):
            prepare_deployment(raw, self.project, (MISSIONS[0], 'absent', MISSIONS[2]))
        self.assertEqual(raw, original)


if __name__ == '__main__':
    unittest.main()

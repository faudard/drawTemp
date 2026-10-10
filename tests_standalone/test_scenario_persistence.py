"""End-to-end scenario saves use real commands, transitions and pinned content."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from sporebound.engine import Battle
from sporebound.model import Content, RuleError
from sporebound.scenarios import ScenarioDirector, ScenarioSession
from sporebound.storage import load_scenario, save_scenario
from examples.siege_campaign import SIEGE_CAMPAIGN
from examples.siege_scenarios import siege_content


def fixture():
    units = [dict(id='hero', name='Hero', team='player', pos=[0,0], hp=20,
                  statuses={'poison':50}),
             dict(id='enemy', name='Enemy', team='enemy', pos=[3,3])]
    content = Content.from_dict({'version':1, 'skills':[], 'missions':[
        dict(id=mid, name=mid, board={'width':4,'height':4}, units=deepcopy(units),
             objective='survive', target_ticks=11,
             deployment=[{'id':'camp','cells':[[0,0],[1,0]]}]) for mid in ('a','b')]})
    director = ScenarioDirector.from_dict({'start':'first','phases':[
        {'id':'first','mission':'a','exits':{'forward':'second'},
         'on_exit':{'forward':{'route':'quiet'}}},
        {'id':'second','mission':'b','exits':{'finish':None}}]})
    return ScenarioSession(content, director, seed=19)


def win(battle, use_item=False):
    battle.execute({'kind':'start_battle'})
    if use_item:
        battle.execute({'kind':'item','item':'potion','cell':[0,0]})
    for _ in range(20):
        if battle.result: break
        battle.execute({'kind':'end'})
    assert battle.result == 'victory'


class ScenarioPersistenceTests(unittest.TestCase):
    def test_save_deployment_transition_and_finish(self):
        s=fixture()
        self.assertEqual(ScenarioSession.replay(s.recording()).digest(),s.digest())
        win(s.battle, use_item=True)
        expected=deepcopy(s.battle.unit('hero'))
        s.complete('forward')
        self.assertEqual(s.elapsed_ticks,11)
        self.assertEqual(s.battle.tick,0)
        self.assertEqual(s.battle.unit('hero').hp,expected.hp)
        self.assertEqual(s.battle.unit('hero').statuses,expected.statuses)
        self.assertEqual(s.battle.inventory['player']['potion'],2)
        # A standalone battle replay must also include transferred resources.
        self.assertEqual(Battle.replay(s.battle.recording()).digest(),s.battle.digest())
        restored=ScenarioSession.replay(s.recording())
        self.assertEqual(restored.digest(),s.digest())
        for session in (s,restored):
            win(session.battle)
            session.complete('finish')
        self.assertEqual(restored.digest(),s.digest())
        self.assertTrue(ScenarioSession.replay(s.recording()).director.completed)

    def test_save_mid_activation_resumes_same_commands(self):
        s=fixture(); s.battle.execute({'kind':'start_battle'})
        s.battle.execute({'kind':'item','item':'potion','cell':[0,0]})
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'siege.json'; save_scenario(path,s)
            resumed=load_scenario(path)
            self.assertEqual(resumed.digest(),s.digest())
            self.assertFalse(list(Path(temp).glob('*.tmp')))
        for session in (s,resumed):
            while not session.battle.result: session.battle.execute({'kind':'end'})
            session.complete('forward')
        self.assertEqual(resumed.digest(),s.digest())

    def test_corruption_and_ruleset_mismatch_rejected(self):
        s=fixture(); win(s.battle); s.complete('forward')
        for mutate in (
            lambda r:r.update(digest='bad'),
            lambda r:r['journal'][0].update(digest='bad'),
            lambda r:r['journal'][0].update(choice='unknown'),
            lambda r:r['current'].update(commands=[{'kind':'end'}]),
            lambda r:r.update(current=None),
            lambda r:r.update(rules={}),
        ):
            record=s.recording(); mutate(record)
            with self.assertRaises(RuleError): ScenarioSession.replay(record)

    def test_source_content_mutation_does_not_change_saved_session(self):
        s=fixture(); data=s.recording(); s.content.missions.clear()
        restored=ScenarioSession.replay(data)
        self.assertTrue(restored.battle.deploying)
        self.assertEqual(restored.battle.mission.id,'a')

    def test_transition_failure_rolls_back_everything(self):
        s=fixture(); win(s.battle)
        s.director.phases['second']['mission']='missing'
        before=s.recording()
        with self.assertRaises(RuleError): s.complete('forward')
        self.assertEqual(s.recording(),before)

    def test_dead_hero_is_not_reactivated_in_next_mission(self):
        s=fixture()
        # Model a casualty while another player survives the encounter.
        from sporebound.model import Unit
        s.content.missions['b'].units.append(Unit('survivor','Survivor','player',(1,0)))
        s.battle.unit('hero').hp=0; s.battle.result='victory'
        s.complete('forward')
        s.battle.execute({'kind':'start_battle'})
        self.assertEqual(s.battle.unit('hero').hp,0)
        self.assertNotEqual(s.battle.active_id,'hero')
        self.assertEqual(Battle.replay(s.battle.recording()).digest(),s.battle.digest())

    def test_route_effects_are_applied_to_courtyard_only(self):
        for route in ('ram','artillery','infiltrate'):
            content=siege_content()
            s=ScenarioSession(content,ScenarioDirector.from_dict(SIEGE_CAMPAIGN))
            for choice in (route,'continue'):
                s.battle.result='victory'; s.complete(choice)
            defense=next(o for o in s.battle.mission.objects if o['id']=='stone_drop')
            self.assertEqual(defense.get('disabled',False),route=='infiltrate')
            self.assertEqual('slow' in s.battle.unit('courtyard_guard').statuses,route=='artillery')
            self.assertNotIn('disabled',content.missions['castle_courtyard'].objects[0])
            self.assertEqual(Battle.replay(s.battle.recording()).digest(),s.battle.digest())

    def test_invalid_initial_resources_rejected(self):
        s=fixture()
        for setup in ([], {'inventory':{'potion':-1}},
                      {'units':{'hero':{'hp':-1,'mp':0,'statuses':{}}}},
                      {'units':{'enemy':{'hp':0,'mp':0,'statuses':{}}}}):
            with self.assertRaises(RuleError):
                Battle(s.content,'a',initial_state=setup)

    def test_entry_effect_is_reconstructed_by_full_scenario_replay(self):
        base=fixture()
        base.content.missions['b'].objects.append({'id':'post','kind':'defense','pos':[3,2],
                                                  'team':'enemy','cells':[[2,2]]})
        definition=deepcopy(base.definition)
        definition['phases'][1]['entry_effects']=[{'flag':'route','equals':'quiet',
                                                   'objects':{'post':{'disabled':True}}}]
        s=ScenarioSession(base.content,ScenarioDirector.from_dict(definition))
        win(s.battle); s.complete('forward')
        restored=ScenarioSession.replay(s.recording())
        self.assertTrue(restored.battle.mission.objects[0]['disabled'])
        self.assertEqual(restored.digest(),s.digest())

    def test_failed_file_replace_keeps_previous_checkpoint(self):
        from unittest.mock import patch
        s=fixture()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'siege.json'; save_scenario(path,s)
            before=path.read_bytes()
            s.battle.execute({'kind':'start_battle'})
            with patch('sporebound.storage.os.replace', side_effect=OSError('write failed')):
                with self.assertRaises(OSError): save_scenario(path,s)
            self.assertEqual(path.read_bytes(),before)
            self.assertFalse(list(Path(temp).glob('*.tmp')))
            self.assertTrue(load_scenario(path).battle.deploying)

    def test_unknown_effect_patch_rejected(self):
        data=deepcopy(SIEGE_CAMPAIGN)
        data['phases'][0]['entry_effects']=[{'flag':'x','equals':1,'objects':{'x':{'kind':'door'}}}]
        with self.assertRaises(RuleError): ScenarioDirector.from_dict(data)


if __name__=='__main__': unittest.main()

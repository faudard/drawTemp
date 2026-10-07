import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.ai import choose_command, simulate
from sporebound.campaign import Campaign
from sporebound.editor import Document
from sporebound.engine import Battle
from sporebound.model import Content, RuleError
from sporebound.storage import load_battle, save_battle
from test_engine import fixture


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.data=Content.load(DEFAULT_CONTENT).to_dict()

    def test_json_roundtrip(self):
        content=Content.from_dict(json.loads(json.dumps(self.data)))
        self.assertEqual(content.to_dict(),self.data)

    def test_reject_invalid_schema_and_references(self):
        changes=[
            lambda d:d.update(version=2),
            lambda d:d['skills'].append(d['skills'][0]),
            lambda d:d['missions'][0]['units'][0].update(skills=['missing']),
            lambda d:d['missions'][0]['units'][0].update(speed=0),
            lambda d:d['missions'][0]['units'][0].update(pos=[-1,0]),
            lambda d:d['missions'][0]['units'][0].update(pos=d['missions'][0]['units'][1]['pos']),
            lambda d:d['missions'][0]['board']['tiles'].append(dict(pos=[1,1],cost=0)),
            lambda d:d['missions'][0].update(objective='unknown'),
            lambda d:d['skills'][0]['effects'][0].update(kind='script'),
            lambda d:d['missions'][0].update(next_missions=['missing']),
            lambda d:d['missions'][0]['objects'][1].update(link='missing'),
        ]
        for edit in changes:
            with self.subTest(edit=edit):
                data=copy.deepcopy(self.data); edit(data)
                with self.assertRaises(RuleError): Content.from_dict(data)

    def test_import_runtime_does_not_import_tk(self):
        result=subprocess.run([sys.executable,'-c','from sporebound.engine import Battle; import sys; assert "tkinter" not in sys.modules'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


class PersistenceTests(unittest.TestCase):
    def test_replay_exact_after_resume(self):
        c=Content.load(DEFAULT_CONTENT); b=Battle(c,'garden',seed=3)
        for _ in range(10): b.execute(choose_command(b))
        resumed=Battle.replay(b.recording())
        self.assertEqual(resumed.digest(),b.digest())
        for _ in range(15):
            if b.result: break
            b.execute(choose_command(b)); resumed.execute(choose_command(resumed))
        self.assertEqual(resumed.digest(),b.digest())
        self.assertEqual(resumed.commands,b.commands)

    def test_invalid_command_preserves_replay_rng(self):
        b=Battle(Content.load(DEFAULT_CONTENT),'garden',seed=42)
        baseline=Battle.replay(b.recording())
        with self.assertRaises(RuleError): b.execute(dict(kind='act',skill='missing',cell=[0,0]))
        for _ in range(8):
            b.execute(choose_command(b)); baseline.execute(choose_command(baseline))
        self.assertEqual(b.digest(),baseline.digest())

    def test_roundtrip_atomic_file_and_corruption(self):
        b=Battle(Content.load(DEFAULT_CONTENT),'garden')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'battle.json'; save_battle(path,b)
            self.assertEqual(load_battle(path).digest(),b.digest())
            data=json.loads(path.read_text()); data['digest']='bad'; path.write_text(json.dumps(data))
            with self.assertRaises(RuleError): load_battle(path)
            self.assertFalse(list(Path(tmp).glob('*.tmp')))

    def test_save_pins_content(self):
        content=Content.load(DEFAULT_CONTENT); b=Battle(content,'garden')
        original=b.digest(); content.skills.clear(); content.missions.clear()
        self.assertEqual(Battle.replay(b.recording()).digest(),original)


class AITests(unittest.TestCase):
    def test_deterministic_simulation_and_legal_commands(self):
        c=Content.load(DEFAULT_CONTENT)
        for mid in c.missions:
            with self.subTest(mission=mid):
                b=Battle(c,mid,seed=9); result=simulate(b,400)
                self.assertIn(result['result'],{'victory','defeat'})
                self.assertEqual(Battle.replay(b.recording()).digest(),b.digest())
                for u in b.units:
                    self.assertTrue(0<=u.hp<=u.max_hp and 0<=u.mp<=u.max_mp)
                alive=[u.pos for u in b.units if u.alive]
                self.assertEqual(len(alive),len(set(alive)))

    def test_ai_forecast_does_not_mutate_state(self):
        b=Battle(Content.load(DEFAULT_CONTENT),'garden'); digest=b.digest()
        one=choose_command(b); two=choose_command(b)
        self.assertEqual(one,two); self.assertEqual(digest,b.digest())

    def test_healer_chooses_wounded_ally(self):
        b=fixture(); b.active.hp=1
        self.assertEqual(choose_command(b),dict(kind='item',item='potion',cell=[0,1]))

    def test_charging_ai_waits(self):
        b=fixture(); b.active.cast={'skill':'cast','remaining':5}
        self.assertEqual(choose_command(b),{'kind':'end'})


    def test_ranged_ai_disengages_then_creates_distance(self):
        b=fixture(weapon='ranged',attack_range=4,min_range=2)
        b.unit('b').pos=(1,1)
        self.assertEqual(choose_command(b),{'kind':'disengage'})
        b.execute({'kind':'disengage'})
        move=choose_command(b)
        self.assertEqual(move['kind'],'move')
        self.assertGreater(abs(move['cell'][0]-1)+abs(move['cell'][1]-1),1)


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.doc=Document(Content.load(DEFAULT_CONTENT))

    def test_paint_undo_redo_and_playtest_isolation(self):
        original=copy.deepcopy(self.doc.data)
        self.doc.tile('garden',(0,0),'hazard')
        self.assertTrue(self.doc.dirty)
        changed=copy.deepcopy(self.doc.data)
        self.doc.undo(); self.assertEqual(self.doc.data,original)
        self.doc.redo(); self.assertEqual(self.doc.data,changed)
        battle=self.doc.playtest('garden'); battle.active.hp=1
        self.assertEqual(self.doc.data,changed)

    def test_invalid_edit_is_atomic(self):
        before=copy.deepcopy(self.doc.data)
        with self.assertRaises(RuleError): self.doc.tile('garden',(1,5),'wall')
        self.assertEqual(before,self.doc.data)
        self.assertEqual(self.doc.undo_stack,[])

    def test_move_unit_and_save(self):
        self.doc.place_unit('garden','ziggy',(0,0))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'content.json'; self.doc.save(path)
            self.assertFalse(self.doc.dirty)
            self.assertEqual(Content.load(path).missions['garden'].units[0].pos,(0,0))


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.content=Content.load(DEFAULT_CONTENT)
        self.campaign=Campaign(['garden'])

    def test_once_only_rewards_and_playtest(self):
        b=self.campaign.prepare(self.content,'garden'); b.result='victory'
        self.assertFalse(self.campaign.finish(b,playtest=True))
        self.assertEqual(self.campaign.gold,0)
        self.assertTrue(self.campaign.finish(b))
        self.assertEqual(self.campaign.gold,100)
        self.assertEqual(self.campaign.hero('ziggy').level,2)
        self.assertIn('escape',self.campaign.unlocked)
        self.assertFalse(self.campaign.finish(b))
        new=self.campaign.prepare(self.content,'garden'); new.result='victory'
        self.assertFalse(self.campaign.finish(new))

    def test_jobs_unlock_skills_and_apply_stats(self):
        c=self.campaign
        with self.assertRaises(RuleError): c.set_job(self.content,'ziggy','spore_maestro')
        c.hero('ziggy').job_xp['brave']=50
        c.set_job(self.content,'ziggy','spore_maestro')
        battle=c.prepare(self.content,'garden')
        self.assertIn('comet',battle.unit('ziggy').skills)
        self.assertEqual(battle.unit('ziggy').magic,10)
        self.assertEqual(self.content.missions['garden'].units[0].magic,8)

    def test_equipment_is_not_duplicated_and_applies_once(self):
        c=self.campaign; c.inventory['rhythm_boots']=1
        c.equip(self.content,'ziggy','rhythm_boots')
        self.assertEqual(c.inventory['rhythm_boots'],0)
        with self.assertRaises(RuleError): c.equip(self.content,'momo','rhythm_boots')
        b1=c.prepare(self.content,'garden'); b2=c.prepare(self.content,'garden')
        self.assertEqual(b1.unit('ziggy').move,5)
        self.assertEqual(b2.unit('ziggy').move,5)

    def test_campaign_roundtrip_and_locked_mission(self):
        with self.assertRaises(RuleError): self.campaign.prepare(self.content,'hold')
        self.campaign.hero('ziggy').xp=150
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'campaign.json'; self.campaign.save(path)
            self.assertEqual(Campaign.load(path),self.campaign)


    def test_bonds_record_once_and_count_shared_kills(self):
        b=self.campaign.prepare(self.content,'garden')
        b.events=[
            {'tick':1,'kind':'damage','unit':'grincheux','source':'ziggy','amount':10},
            {'tick':2,'kind':'damage','unit':'grincheux','source':'momo','amount':10},
            {'tick':3,'kind':'downed','unit':'grincheux','source':'momo'},
        ]
        b.result='victory'
        self.assertTrue(self.campaign.record_bonds(b))
        self.assertFalse(self.campaign.record_bonds(b))
        stats=self.campaign.bond('ziggy','momo')
        self.assertEqual(stats['missions_together'],1)
        self.assertEqual(stats['shared_kills'],1)
        self.assertEqual(stats['shared_kill:grincheux'],1)

    def test_declarative_tactic_unlock_and_prepared_loadout(self):
        rules=[{
            'id':'pincer',
            'members':['ziggy','momo'],
            'unlock':{'all':[
                {'stat':'missions_together','gte':1},
                {'completed_mission':'garden'},
            ]},
        }]
        b=self.campaign.prepare(self.content,'garden'); b.result='victory'
        self.assertTrue(self.campaign.finish(b,tactic_rules=rules))
        self.assertIn('pincer',self.campaign.known_tactics['momo|ziggy'])
        self.assertTrue(self.campaign.prepare_tactic('ziggy','momo','pincer'))
        battle=self.campaign.prepare(self.content,'escape')
        self.assertIn('pincer',battle.unit('ziggy').tactics)
        self.assertIn('pincer',battle.unit('momo').tactics)

    def test_bond_progress_persists_in_campaign_save(self):
        self.campaign.bond('ziggy','momo')['missions_together']=4
        self.campaign.unlock_tactic('ziggy','momo','pincer')
        self.campaign.prepare_tactic('ziggy','momo','pincer')
        self.campaign.tracked_battles.append('battle-1')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'campaign.json'; self.campaign.save(path)
            loaded=Campaign.load(path)
        self.assertEqual(loaded.bond_stats,self.campaign.bond_stats)
        self.assertEqual(loaded.known_tactics,self.campaign.known_tactics)
        self.assertEqual(loaded.prepared_tactics,self.campaign.prepared_tactics)
        self.assertEqual(loaded.tracked_battles,self.campaign.tracked_battles)

class CrownAndShopTests(unittest.TestCase):
    def test_crown_pickup_drop_recover_and_extract(self):
        b=fixture(); b.mission.objective='crown'; b.mission.goal=[(0,0)]; b.relic_pos=(1,1)
        b.units.append(copy.deepcopy(b.unit('a')))
        b.units[-1].id='rescuer'; b.units[-1].pos=(1,2); b.units[-1].ct=0
        b.execute(dict(kind='move',cell=[1,1]))
        self.assertEqual(b.carrier,'a'); self.assertIsNone(b.relic_pos)
        b._hurt(b.unit('a'),100)
        self.assertIsNone(b.carrier); self.assertEqual(b.relic_pos,(1,1))
        b.active_id='rescuer'
        b.execute(dict(kind='move',cell=[1,1]))
        self.assertEqual(b.carrier,'rescuer')
        b.active.moved=False
        b.execute(dict(kind='move',cell=[0,0]))
        self.assertEqual(b.result,'victory')

    def test_buy_equip_unequip_and_insufficient_gold(self):
        content=Content.load(DEFAULT_CONTENT); campaign=Campaign(['garden'])
        with self.assertRaises(RuleError): campaign.buy(content,'rhythm_boots')
        campaign.gold=100; campaign.buy(content,'rhythm_boots')
        self.assertEqual(campaign.gold,40)
        campaign.equip(content,'ziggy','rhythm_boots')
        campaign.unequip('ziggy','accessory')
        self.assertEqual(campaign.inventory['rhythm_boots'],1)
        self.assertEqual(campaign.hero('ziggy').equipment,{})


if __name__=='__main__': unittest.main()

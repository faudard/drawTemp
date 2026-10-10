"""Headless tests for Studio 2.1 and the standalone player session."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound import actor_catalog, campaign_graph, event_composer
from sporebound.authoring import remove_unit
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.player_session import PlayerSession


class StudioAdvancedTests(unittest.TestCase):
    def setUp(self):
        self.content=Content.load(DEFAULT_CONTENT)
        self.data=self.content.to_dict()
        self.mid='garden'
        board=self.content.missions[self.mid].board
        occupied={cell for unit in self.content.missions[self.mid].units for cell in unit.occupied_cells()}
        self.cell=next(c for c in board.cells() if c not in occupied and not board.tile(c).blocked)

    def test_graph_links_reachability_and_cycle_detection(self):
        report=campaign_graph.inspect_graph(self.content,['garden'])
        self.assertIn('garden',report['reachable'])
        self.assertEqual(set(report['positions']),set(self.content.missions))
        # Enforce a genuine two-way cycle on the same validated content.
        data=campaign_graph.set_link(self.data,'garden','escape',True)
        data=campaign_graph.set_link(data,'escape','garden',True)
        cycle_report=campaign_graph.inspect_graph(Content.from_dict(data),['garden'])
        self.assertTrue(any(c[0]==c[-1] for c in cycle_report['cycles']))
        removed=campaign_graph.set_link(data,'escape','garden',False)
        self.assertNotIn('garden',Content.from_dict(removed).missions['escape'].next_missions)
        with self.assertRaises(RuleError):
            campaign_graph.set_link(self.data,'garden','garden',True)
        self.assertEqual(self.data,self.content.to_dict())

    def test_actor_catalog_capture_place_and_prevent_delete_when_used(self):
        data=actor_catalog.capture_actor(self.data,self.mid,'ziggy','wizard_template')
        self.assertIn('wizard_template',Content.from_dict(data).archetypes)
        data=actor_catalog.place_archetype(data,self.mid,'wizard_template',
                                           'wizard_extra','Mage allié','player',self.cell)
        wizard=next(u for u in Content.from_dict(data).missions[self.mid].units
                    if u.id=='wizard_extra')
        self.assertEqual(wizard.archetype,'wizard_template')
        self.assertEqual(wizard.team,'player')
        with self.assertRaises(RuleError):
            actor_catalog.remove_archetype(data,'wizard_template')
        data=remove_unit(data,self.mid,'wizard_extra')
        self.assertNotIn('wizard_template',Content.from_dict(
            actor_catalog.remove_archetype(data,'wizard_template')).archetypes)

    def test_new_monster_template_is_playable(self):
        data=actor_catalog.create_archetype(self.data,'troll',kind='monster',
                                           max_hp=110,attack=15,speed=7,move=2)
        data=actor_catalog.place_archetype(data,self.mid,'troll','troll_01',
                                           'Troll','enemy',self.cell)
        troll=next(u for u in Content.from_dict(data).missions[self.mid].units if u.id=='troll_01')
        self.assertEqual((troll.max_hp,troll.attack,troll.kind),(110,15,'monster'))

    def test_event_action_blocks_validate_and_reorder(self):
        a=event_composer.action('message',text='Renforts !')
        b=event_composer.action('hazard',pos=self.cell,amount=5)
        conditions=event_composer.condition('tick',tick=12)
        ordered=event_composer.move_action([a,b],1,-1)
        self.assertEqual([item['kind'] for item in ordered],['hazard','message'])
        updated=event_composer.save_event(self.data,self.mid,'scene_two',conditions,[a,b])
        event=next(x for x in Content.from_dict(updated).missions[self.mid].triggers
                   if x['id']=='scene_two')
        self.assertEqual([row['kind'] for row in event['actions']],['message','hazard'])
        updated_again=event_composer.save_event(updated,self.mid,'scene_two',conditions,ordered)
        events=Content.from_dict(updated_again).missions[self.mid].triggers
        self.assertEqual(sum(row['id']=='scene_two' for row in events),1)
        with self.assertRaises(RuleError):
            event_composer.save_event(self.data,self.mid,'broken',conditions,[
                event_composer.action('hazard',pos=[500,500],amount=1)])
        with self.assertRaises(RuleError):
            event_composer.save_event(self.data,self.mid,'empty',conditions,[])


class PlayerSessionTests(unittest.TestCase):
    def setUp(self):
        self.content=Content.load(DEFAULT_CONTENT)
        self.project=GameProject.default(self.content)

    def test_new_save_reload_and_discard_unfinished_battle(self):
        with TemporaryDirectory() as folder:
            profile=Path(folder)/'example.game.json'
            session=PlayerSession(self.content,self.project,profile)
            progress=session.new_game('main',1)
            self.assertEqual(progress.unlocked,['garden'])
            session.begin('garden')
            self.assertIsNotNone(session.battle)
            current=session.battle.digest()
            with self.assertRaises(RuleError):
                session.command({'kind':'unknown'})
            self.assertEqual(session.battle.digest(),current)
            with self.assertRaises(RuleError):
                session.save()
            with self.assertRaises(RuleError):
                session.return_to_campaign()
            session.abandon_battle()
            loaded=PlayerSession(self.content,self.project,profile)
            loaded.load_game('main',1)
            self.assertEqual(loaded.available_missions(),['garden'])
            self.assertIsNone(loaded.battle)

    def test_invalid_slot_is_rejected_without_writing(self):
        with TemporaryDirectory() as folder:
            session=PlayerSession(self.content,self.project,Path(folder)/'example.game.json')
            with self.assertRaises(RuleError):
                session.new_game('main',0)
            self.assertEqual(list(Path(folder).rglob('*.json')),[])


if __name__=='__main__':
    unittest.main()

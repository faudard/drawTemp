"""Narrative choices, exclusive mission consequences and save compatibility."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.campaign import Campaign
from sporebound.game_project import GameProject, _slot_path
from sporebound.model import Content, RuleError
from sporebound.narrative import StoryBook, matches
from sporebound.player_session import PlayerSession
from sporebound.storage import write_json
from sporebound import story_authoring


class StoryContractTests(unittest.TestCase):
    def setUp(self):
        self.content=Content.load(DEFAULT_CONTENT)
        self.data=json.loads(Path(DEFAULT_CONTENT).with_suffix('.game.json').read_text(
            encoding='utf-8'))
        self.project=GameProject.from_dict(self.data,self.content)
        self.book=StoryBook(self.project.story,self.content,self.project.campaigns)

    def test_intro_dialogue_with_conditional_followup(self):
        progress=self.project.new_game('relique',self.content)
        self.assertEqual(progress.story_pending,'oath')
        self.assertEqual([c['id'] for c in self.book.choices(progress)],['guard','alone'])
        progress=self.book.choose(progress,'guard')
        self.assertEqual(progress.story_flags['guard_oath'],True)
        self.assertEqual(progress.story_pending,'oath_reward')
        self.assertEqual([c['id'] for c in self.book.choices(progress)],['provisions','proceed'])
        progress=self.book.choose(progress,'provisions')
        self.assertEqual(progress.gold,25)
        self.assertEqual(progress.story_pending,'')
        self.assertEqual(len(progress.story_history),2)

        independent=self.project.new_game('relique',self.content)
        independent=self.book.choose(independent,'alone')
        self.assertEqual([c['id'] for c in self.book.choices(independent)],['proceed'])
        before=deepcopy(independent)
        with self.assertRaises(RuleError):
            self.book.choose(independent,'provisions')
        self.assertEqual(before,independent)

    def test_condition_combinators_are_type_safe(self):
        progress=self.project.new_game('main',self.content)
        progress.story_flags['trust']=2
        self.assertTrue(matches({'all':[{'flag':'trust','gte':2},
                                        {'not':{'gold_gte':100}}]},progress))
        self.assertFalse(matches({'flag':'trust','eq':True},progress))
        progress.story_flags['trust']=True
        self.assertFalse(matches({'flag':'trust','gte':1},progress))

    def test_validation_rejects_cycles_bad_effects_and_missing_fallback(self):
        for transformation in ('cycle','bad_mission','no_fallback'):
            data=deepcopy(self.data)
            scenes=data['story']['scenes']
            if transformation=='cycle':
                scenes[1]['choices'][1]['next_scene']='oath'
            elif transformation=='bad_mission':
                scenes[2]['choices'][0]['effects'][1]['mission']='missing'
            else:
                for choice in scenes[2]['choices']:
                    choice['when']={'gold_gte':0}
            with self.subTest(transformation=transformation),self.assertRaises(RuleError):
                GameProject.from_dict(data,self.content)

    def test_authoring_is_validated_and_undoable_by_snapshot(self):
        previous=self.project.to_dict()
        updated=story_authoring.create_scene(self.project,self.content,'meeting',
                  'Première rencontre','Les alliés discutent.','Conseiller')
        updated=story_authoring.add_choice(updated,self.content,'meeting','help',
                  'Aider',effects=[{'kind':'set_flag','flag':'helped','value':True}])
        updated=story_authoring.add_effect(updated,self.content,'meeting','help',
                  {'kind':'unlock_mission','mission':'hold'})
        updated=story_authoring.set_mission_outcome(updated,self.content,'hold','meeting')
        self.assertEqual(updated.story['after_mission']['hold'],'meeting')
        with self.assertRaises(RuleError):
            story_authoring.delete_scene(updated,self.content,'meeting')
        self.assertEqual(self.project.to_dict(),previous)


class StorySaveTests(unittest.TestCase):
    def setUp(self):
        self.content=Content.load(DEFAULT_CONTENT)
        self.project=GameProject.load(Path(DEFAULT_CONTENT).with_suffix('.game.json'),
                                      self.content)

    def test_exclusive_post_victory_route_persists_and_is_not_repeatable(self):
        with TemporaryDirectory() as folder:
            profile=Path(folder)/'story.game.json'
            player=PlayerSession(self.content,self.project,profile)
            player.new_game('main',1)
            self.assertIsNone(player.active_scene())
            player.begin('garden')
            # Exercise the normal Campaign.finish boundary without simulating 100 AI turns.
            player.battle.result='victory'
            player._finish_if_done()
            self.assertTrue(player.finalized)
            self.assertEqual(player.progress.completed,['garden'])
            self.assertEqual(player.progress.unlocked,['garden'])
            self.assertEqual(player.progress.story_pending,'council')
            self.assertEqual(player.available_missions(),[])
            with self.assertRaises(RuleError):
                player.begin('escape')
            player.return_to_campaign()
            selected=player.choose_story('tunnel')
            self.assertIsNone(selected)
            self.assertEqual(player.progress.story_flags['chosen_route'],'tunnel')
            self.assertEqual(player.available_missions(),['escape'])
            self.assertNotIn('hold',player.progress.unlocked)
            self.assertNotIn('crown',player.progress.unlocked)
            before=deepcopy(player.progress)
            with self.assertRaises(RuleError):
                player.choose_story('defend')
            self.assertEqual(before,player.progress)

            resumed=PlayerSession(self.content,self.project,profile)
            resumed.load_game('main',1)
            self.assertEqual(resumed.available_missions(),['escape'])
            self.assertEqual(resumed.progress.story_history,
                             [{'scene':'council','choice':'tunnel'}])

    def test_legacy_slots_can_load_and_story_contract_change_is_rejected(self):
        with TemporaryDirectory() as folder:
            profile=Path(folder)/'campaign.game.json'
            path=_slot_path(profile,self.project,'main',1)
            legacy=Campaign(unlocked=['garden'])
            data={'version':1,**asdict(legacy)}
            for key in tuple(data):
                if key.startswith('story_'):
                    del data[key]
            write_json(path,data)
            player=PlayerSession(self.content,self.project,profile)
            player.load_game('main',1)
            self.assertEqual(player.progress.story_pending,'')
            player.save()
            changed=deepcopy(self.project.to_dict())
            changed['story']['scenes'][2]['text']='Autre version du scénario'
            changed_project=GameProject.from_dict(changed,self.content)
            with self.assertRaises(RuleError):
                PlayerSession(self.content,changed_project,profile).load_game('main',1)

    def test_failed_story_gold_effect_does_not_mutate_save(self):
        with TemporaryDirectory() as folder:
            player=PlayerSession(self.content,self.project,Path(folder)/'game.json')
            player.new_game('main',1)
            player.progress.story_pending='council'
            previous=deepcopy(player.progress)
            with self.assertRaises(RuleError):
                player.choose_story('relic')
            self.assertEqual(player.progress,previous)


if __name__=='__main__':
    unittest.main()

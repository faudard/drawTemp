"""Regression tests for guided level authoring and high-level game projects."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import (add_unit, remove_unit, add_object, remove_object,
                                  add_event, remove_event, resize_map, add_blank_mission,
                                  set_mission_properties)
from sporebound.campaign import Campaign
from sporebound.editor import Document
from sporebound.game_project import GameProject, save_slot, load_slot
from sporebound.model import Content, RuleError


def free_cell(mission):
    occupied = {cell for unit in mission.units for cell in unit.occupied_cells()}
    for cell in mission.board.cells():
        if cell not in occupied and not mission.board.tile(cell).blocked:
            return cell
    raise AssertionError('Example mission needs a free cell')


class AuthoringTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.data = self.content.to_dict()
        self.mid = next(iter(self.content.missions))
        self.cell = free_cell(self.content.missions[self.mid])

    def test_actor_and_object_create_remove_are_validated(self):
        data = add_unit(self.data,self.mid,'test_enemy','Éclaireur','enemy',self.cell)
        self.assertIn('test_enemy',[u['id'] for m in data['missions'] if m['id']==self.mid for u in m['units']])
        with self.assertRaises(RuleError):
            add_unit(data,self.mid,'test_enemy','Dupliqué','enemy',self.cell)
        data = remove_unit(data,self.mid,'test_enemy')
        data = add_object(data,self.mid,'test_chest','chest',self.cell)
        self.assertIn('test_chest',[o['id'] for m in data['missions'] if m['id']==self.mid for o in m['objects']])
        with self.assertRaises(RuleError):
            add_object(data,self.mid,'orphan','switch',self.cell,link='missing')
        data = remove_object(data,self.mid,'test_chest')
        self.assertIsNotNone(Content.from_dict(data))

    def test_event_create_and_undo(self):
        doc=Document(self.content)
        updated=add_event(doc.data,self.mid,'visit',condition='enter',action='message',
                          pos=self.cell,text='Un ennemi approche')
        doc.replace(updated)
        self.assertTrue(doc.dirty)
        self.assertIn('visit',[t['id'] for t in Content.from_dict(doc.data).missions[self.mid].triggers])
        doc.undo()
        self.assertNotIn('visit',[t['id'] for t in Content.from_dict(doc.data).missions[self.mid].triggers])
        doc.redo()
        doc.replace(remove_event(doc.data,self.mid,'visit'))
        self.assertIsNotNone(Content.from_dict(doc.data))

    def test_batch_paint_is_one_undo_step(self):
        doc=Document(self.content)
        # Keep the paint safely away from actors and blocked tiles.
        cells=[c for c in self.content.missions[self.mid].board.cells()
               if c not in {cell for u in self.content.missions[self.mid].units
                            for cell in u.occupied_cells()}
               and not self.content.missions[self.mid].board.tile(c).blocked]
        chosen=cells[:3]
        doc.paint_many(self.mid,chosen,'cover')
        self.assertEqual(len(doc.undo_stack),1)
        board=Content.from_dict(doc.data).missions[self.mid].board
        self.assertTrue(all(board.tile(c).cover==20 for c in chosen))
        doc.undo()
        self.assertEqual(doc.data,self.content.to_dict())

    def test_triggers_are_engine_validated(self):
        updated=add_event(self.data,self.mid,'clock',condition='tick',action='hazard',
                          pos=self.cell,tick=15,amount=3)
        self.assertIsNotNone(Content.from_dict(updated))
        with self.assertRaises(RuleError):
            add_event(self.data,self.mid,'clock','tick','hazard',
                      pos=self.cell,tick=-1,amount=3)
        with self.assertRaises(RuleError):
            add_event(self.data,self.mid,'badunit',condition='defeated',action='message',
                      pos=self.cell,unit='nope')

    def test_blank_mission_and_progression(self):
        updated=add_blank_mission(self.data,'new_battle','Nouvelle bataille',8,8)
        battle=Content.from_dict(updated).missions['new_battle']
        self.assertEqual(battle.board.tiles,{})
        self.assertEqual(len(battle.units),2)
        self.assertEqual(battle.objects,[])
        self.assertEqual(battle.triggers,[])
        changed=set_mission_properties(updated,self.mid,name='Intro',
                                       objective='eliminate',reward=250,
                                       next_missions=['new_battle'])
        self.assertEqual(Content.from_dict(changed).missions[self.mid].next_missions,
                         ['new_battle'])
        with self.assertRaises(RuleError):
            set_mission_properties(updated,self.mid,name='Intro',
                                   objective='eliminate',reward=250,
                                   next_missions=['not_found'])

    def test_resize_rejects_losing_actor_or_object(self):
        mission=self.content.missions[self.mid]
        self.assertIsNotNone(Content.from_dict(resize_map(self.data,self.mid,
                                                          mission.board.width+1,
                                                          mission.board.height+1)))
        with self.assertRaises(RuleError):
            resize_map(self.data,self.mid,1,1)
        with self.assertRaises(RuleError):
            resize_map(self.data,self.mid,129,1)


class GameProjectTests(unittest.TestCase):
    def setUp(self):
        self.content=Content.load(DEFAULT_CONTENT)
        self.project=GameProject.default(self.content)

    def test_project_round_trip_and_campaign_start(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'adventure.game.json'
            self.project.save(path,self.content)
            restored=GameProject.load(path,self.content)
            self.assertEqual(restored.to_dict(),self.project.to_dict())
            progress=restored.new_game('main',self.content)
            self.assertEqual(progress.unlocked,[restored.campaign('main')['start_mission']])
            progress.gold=123
            saved=save_slot(path,restored,self.content,'main',1,progress)
            self.assertTrue(saved.is_file())
            loaded=load_slot(path,restored,self.content,'main',1)
            self.assertEqual(loaded.gold,123)
            self.assertEqual(loaded.unlocked,progress.unlocked)
            with self.assertRaises(RuleError):
                load_slot(path,restored,self.content,'main',0)

    def test_manifest_rejects_invalid_references_and_bad_options(self):
        data=self.project.to_dict()
        data['campaigns'][0]['start_mission']='unknown'
        with self.assertRaises(RuleError):
            GameProject.from_dict(data,self.content)
        data=self.project.to_dict()
        data['options']['music_volume']=101
        with self.assertRaises(RuleError):
            GameProject.from_dict(data,self.content)
        data=self.project.to_dict()
        data['campaigns'].append(deepcopy(data['campaigns'][0]))
        with self.assertRaises(RuleError):
            GameProject.from_dict(data,self.content)

    def test_slot_rejects_campaign_from_other_content(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'game.json'
            progress=Campaign(unlocked=['removed_mission'])
            with self.assertRaises(RuleError):
                save_slot(path,self.project,self.content,'main',1,progress)


if __name__ == '__main__':
    unittest.main()

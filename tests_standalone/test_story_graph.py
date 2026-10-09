"""Tests for unfolding a DAG into reusable narrative scene occurrences."""
from copy import deepcopy
from pathlib import Path
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.story_graph import build_story_tree, condition_label, effects_label
from sporebound import story_authoring as edit


def shared_story():
    return {
        'scenes':[
            {'id':'start','title':'Au carrefour','speaker':'Guide','text':'Choisir.',
             'choices':[
                 {'id':'left','label':'À gauche','next_scene':'left_scene',
                  'effects':[{'kind':'set_flag','flag':'direction','value':'left'}]},
                 {'id':'right','label':'À droite','next_scene':'right_scene'}]},
            {'id':'left_scene','title':'Chemin de gauche','speaker':'','text':'La forêt.',
             'choices':[{'id':'join','label':'Rejoindre',
                         'next_scene':'shared'}]},
            {'id':'right_scene','title':'Chemin de droite','speaker':'','text':'La plaine.',
             'choices':[{'id':'join','label':'Rejoindre',
                         'next_scene':'shared'}]},
            {'id':'shared','title':'Salle du trône','speaker':'Roi','text':'Bienvenue.',
             'choices':[{'id':'continue','label':'Terminer'}]},
        ],
        'entry_scenes':{'main':'start'},
        'after_mission':{},
    }


class StoryTreeTests(unittest.TestCase):
    def setUp(self):
        self.content=Content.load(DEFAULT_CONTENT)
        self.project=GameProject.default(self.content)
        document=self.project.to_dict()
        document['story']=shared_story()
        self.project=GameProject.from_dict(document,self.content)

    def test_shared_scene_is_drawn_twice_but_stored_once(self):
        layout=build_story_tree(self.project.story,'start')
        matches=[n for n in layout['nodes'] if n['scene_id']=='shared']
        self.assertEqual(len(self.project.story['scenes']),4)
        self.assertEqual(len(matches),2)
        self.assertEqual({n['path'] for n in matches},{
            ('start','left','join'),('start','right','join')})
        self.assertTrue(all(n['reused'] for n in matches))
        self.assertNotEqual(layout['positions'][matches[0]['path']],
                            layout['positions'][matches[1]['path']])
        self.assertEqual(len(layout['edges']),6)
        self.assertEqual(layout['shared_scenes'],['shared'])

    def test_collapsing_one_occurrence_does_not_hide_another(self):
        path=('start','left')
        layout=build_story_tree(self.project.story,'start',collapsed={path})
        self.assertTrue(any(n['scene_id']=='shared' and
                            n['path']==('start','right','join')
                            for n in layout['nodes']))
        self.assertFalse(any(n['scene_id']=='shared' and
                             n['path']==('start','left','join')
                             for n in layout['nodes']))
        folded=next(n for n in layout['nodes'] if n['path']==path)
        self.assertTrue(folded['collapsed'])

    def test_depth_and_budget_bound_large_unfolded_graphs(self):
        limited=build_story_tree(self.project.story,'start',max_nodes=3)
        self.assertLessEqual(len(limited['nodes']),3)
        self.assertTrue(limited['truncated'])
        shallow=build_story_tree(self.project.story,'start',max_depth=1)
        self.assertTrue(shallow['truncated'])
        self.assertLessEqual(max(n['depth'] for n in shallow['nodes']),1)

    def test_condition_and_reward_labels(self):
        self.assertIn('mission',condition_label({'completed_mission':'garden'}))
        self.assertIn('∧',condition_label({'all':[{'flag':'ally','eq':True},
                                                     {'gold_gte':25}]}))
        effects=effects_label([{'kind':'gold','amount':-50},
                               {'kind':'unlock_mission','mission':'hold'}])
        self.assertIn('or -50',effects)
        self.assertIn('hold',effects)

    def test_link_shared_scene_and_edit_canonical_definition(self):
        original=deepcopy(self.project.to_dict())
        changed=edit.link_choice(self.project,self.content,'right_scene','join',
                                  'left_scene')
        # A->B with B->shared is still a DAG, and both paths target the same B.
        drawn=build_story_tree(changed.story,'start')
        self.assertEqual(len([n for n in drawn['nodes']
                              if n['scene_id']=='left_scene']),2)
        changed=edit.update_scene(changed,self.content,'left_scene',
                                  title='Chemin renommé',speaker='Guide',
                                  text='Modifié une seule fois.')
        self.assertEqual([s for s in changed.story['scenes']
                          if s['id']=='left_scene'][0]['title'],'Chemin renommé')
        self.assertEqual(self.project.to_dict(),original)
        with self.assertRaises(RuleError):
            edit.link_choice(changed,self.content,'left_scene','join','start')

    def test_atomic_create_and_connect_then_undo_by_snapshot(self):
        before=self.project.to_dict()
        after=edit.create_linked_scene(
            self.project,self.content,'shared','continue','epilogue',
            'Épilogue','Fin de la bataille.')
        linked=next(s for s in after.story['scenes'] if s['id']=='shared')
        self.assertEqual(linked['choices'][0]['next_scene'],'epilogue')
        self.assertEqual(len(after.story['scenes']),5)
        tree=build_story_tree(after.story,'start')
        self.assertEqual(len([n for n in tree['nodes']
                              if n['scene_id']=='epilogue']),2)
        with self.assertRaises(RuleError):
            edit.create_linked_scene(after,self.content,'shared','continue',
                                     'duplicate','Non','Déjà liée.')
        self.assertEqual(self.project.to_dict(),before)


if __name__=='__main__':
    unittest.main()

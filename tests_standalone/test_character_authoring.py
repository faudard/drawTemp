"""2.5.3 character studio headless authoring gates (Content v1 and undo)."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.actor_catalog import create_archetype, place_archetype
from sporebound.character_authoring import (
    create_equipment, create_job, create_skill, make_effect,
    move_skill_effect, parse_bonuses, parse_skill_levels,
    remove_equipment, remove_job, remove_skill, remove_skill_effect,
    set_skill_effect, update_archetype, update_equipment, update_job,
    update_mission_unit, update_skill,
)
from sporebound.editor import Document
from sporebound.model import Content, RuleError


class CharacterRulesTests(unittest.TestCase):
    def setUp(self):
        self.original = Content.load(DEFAULT_CONTENT).to_dict()
        self.data = deepcopy(self.original)

    def test_skill_create_and_multi_effect_operations_keep_order_and_undo(self):
        doc = Document(Content.from_dict(self.data))
        created = create_skill(doc.data, 'sunward', 'Lumière du jour',
                               effect=make_effect('damage', power=8),
                               target='enemy', range=3, cost=2)
        doc.replace(created)
        self.assertEqual(doc.data['skills'][-1]['id'], 'sunward')
        status = make_effect('status', power=1, status='slow', duration=12)
        doc.replace(set_skill_effect(doc.data, 'sunward', 1, status, insert=True))
        doc.replace(move_skill_effect(doc.data, 'sunward', 1, -1))
        effect_types = [v['kind'] for v in doc.data['skills'][-1]['effects']]
        self.assertEqual(effect_types, ['status', 'damage'])
        doc.replace(set_skill_effect(doc.data, 'sunward', 1,
                                     make_effect('heal', power=5)))
        self.assertEqual(doc.data['skills'][-1]['effects'][1]['kind'], 'heal')
        doc.replace(remove_skill_effect(doc.data, 'sunward', 0))
        self.assertEqual(len(doc.data['skills'][-1]['effects']), 1)
        doc.undo()
        self.assertEqual(len(doc.data['skills'][-1]['effects']), 2)
        doc.redo()
        self.assertEqual(doc.data['skills'][-1]['effects'][0]['kind'], 'heal')
        doc.replace(update_skill(doc.data, 'sunward', range=4,
                                 radius=1, shape='cross', accuracy=90))
        self.assertEqual(Content.from_dict(doc.data).skills['sunward'].range, 4)
        self.assertEqual(self.data, self.original)

    def test_reject_invalid_effect_and_dangling_skill_reference_atomically(self):
        before = deepcopy(self.data)
        for change in (
            lambda: create_skill(self.data, 'newskill', 'Bad',
                                 effect=make_effect('status', status='unknown')),
            lambda: update_skill(self.data, 'flare', range=2, min_range=3),
            lambda: set_skill_effect(self.data, 'flare', 0,
                                     {'kind': 'damage', 'power': 20000}),
            lambda: remove_skill_effect(self.data, 'flare', 0),
            lambda: remove_skill(self.data, 'flare'),
            lambda: create_skill(self.data, 'flare', 'Duplicate'),
        ):
            with self.subTest(case=change), self.assertRaises(RuleError):
                change()
            self.assertEqual(self.data, before)

    def test_update_one_actor_mission_instance_not_other_missions(self):
        baseline = Content.from_dict(self.data)
        original = next(u for u in baseline.missions['garden'].units if u.id=='ziggy')
        changed = update_mission_unit(self.data, 'garden', 'ziggy',
                                      max_hp=original.max_hp+5, attack=11,
                                      skills=['flare','heal'], reaction='counter')
        after = Content.from_dict(changed)
        altered = next(u for u in after.missions['garden'].units if u.id=='ziggy')
        separate = next(u for u in after.missions['escape'].units if u.id=='ziggy')
        self.assertEqual(altered.max_hp, original.max_hp+5)
        self.assertEqual(altered.hp, original.max_hp+5)
        self.assertEqual(altered.attack, 11)
        self.assertEqual(altered.skills, ['flare','heal'])
        self.assertEqual(separate.attack, original.attack)
        self.assertEqual(self.data, self.original)
        for invalid in (dict(speed=0), dict(skills=['missing']),
                        dict(weapon='invalid')):
            with self.subTest(invalid=invalid), self.assertRaises(RuleError):
                update_mission_unit(self.data, 'garden', 'ziggy', **invalid)

    def test_template_change_never_mutates_previously_authored_instances(self):
        data = create_archetype(self.data, 'new_orc', kind='monster', max_hp=40,
                                skills=['flare'])
        data = place_archetype(data, 'garden', 'new_orc', 'orc_01',
                               'Gardien', 'enemy', [4, 4])
        before = Content.from_dict(data).missions['garden']
        actor_before = next(u for u in before.units if u.id == 'orc_01')
        altered = update_archetype(data, 'new_orc', max_hp=70, attack=9,
                                   skills=['heal'])
        actor_after = next(u for u in Content.from_dict(altered).missions['garden'].units
                           if u.id == 'orc_01')
        self.assertEqual(actor_before.max_hp, actor_after.max_hp)
        self.assertEqual(actor_after.skills, ['flare'])
        self.assertEqual(altered['archetypes']['new_orc']['skills'], ['heal'])
        for bad in (dict(skills=['unknown']), dict(max_hp=-1),
                    dict(pos=[1,1]), dict(patrol_route=[[0,0]])):
            with self.subTest(changes=bad), self.assertRaises(RuleError):
                update_archetype(data, 'new_orc', **bad)

    def test_job_prerequisites_skill_levels_and_bonuses(self):
        bonuses = parse_bonuses('attack=3, max_hp=12')
        levels = parse_skill_levels('flare=2, heal=5',
                                    (x['id'] for x in self.data['skills']))
        self.assertEqual(levels, {'flare':2, 'heal':5})
        first = create_job(self.data, 'warrior_plus', 'Guerrier plus',
                           requires='brave', bonuses=bonuses, skills=levels)
        self.assertIn('warrior_plus', Content.from_dict(first).jobs)
        edited = update_job(first, 'warrior_plus', requires_level=3,
                            bonuses={'defense':4})
        self.assertEqual(edited['jobs']['warrior_plus']['requires_level'],3)
        self.assertEqual(edited['jobs']['warrior_plus']['skills'],levels)
        removed = remove_job(edited, 'warrior_plus')
        self.assertNotIn('warrior_plus', removed['jobs'])
        dependent = create_job(first, 'advanced_warrior', 'Elite',
                               requires='warrior_plus')
        with self.assertRaises(RuleError):
            remove_job(dependent, 'warrior_plus')
        with self.assertRaises(RuleError):
            create_job(self.data, 'bad_class', 'Bad', skills={'ghost': 1})

    def test_equipment_create_modify_remove_and_reject_bad_fields(self):
        bonuses = parse_bonuses('weapon_power=2, attack=3', equipment=True)
        data = create_equipment(self.data, 'blade_new', 'Lame neuve', 'weapon',
                                price=75, bonuses=bonuses)
        self.assertEqual(data['equipment']['blade_new']['bonuses']['weapon_power'],2)
        changed = update_equipment(data, 'blade_new', price=110, slot='accessory')
        self.assertEqual(Content.from_dict(changed).equipment['blade_new']['price'],110)
        removed = remove_equipment(changed, 'blade_new')
        self.assertNotIn('blade_new',removed['equipment'])
        for bad in ('unknown=2', 'attack=-3', 'attack=2,attack=4'):
            with self.subTest(bonus=bad),self.assertRaises(RuleError):
                parse_bonuses(bad, equipment=True)
        with self.assertRaises(RuleError):
            create_equipment(self.data, 'bad', 'Bad', 'helmet')


if __name__ == '__main__':
    unittest.main()

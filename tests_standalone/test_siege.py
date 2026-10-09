"""Siege traversal, defender AI, sabotage and final encounter progression."""
from copy import deepcopy
import unittest
from examples.siege_scenarios import siege_content
from examples.siege_campaign import SIEGE_CAMPAIGN
from sporebound.ai import choose_command
from sporebound.engine import Battle
from sporebound.model import Content, RuleError
from sporebound.scenarios import ScenarioDirector, ScenarioSession


class SiegeTests(unittest.TestCase):
    def battle(self):
        return Battle(siege_content(), 'castle_ramparts', seed=2)

    def activate(self, b, uid):
        b.active_id = uid
        b.unit(uid).moved = b.unit(uid).acted = False

    def test_install_climb_raise_gate_and_descend(self):
        b = self.battle()
        b.execute({'kind':'start_battle'})
        self.activate(b, 'captain')
        b.unit('captain').pos = (7,1)
        self.assertNotIn((8,1), b.reachable())
        b.execute({'kind':'interact','object':'grapple'})
        self.assertIn((8,1), b.reachable())
        b.execute({'kind':'move','cell':[8,1]})
        self.assertEqual(b.unit('captain').pos, (8,1))
        self.assertTrue(b.unit('captain').moved)
        # Get past the guard, then use the inner winch and stairs.
        b.unit('oil_keeper').hp = 0
        self.activate(b, 'captain')
        b.execute({'kind':'move','cell':[10,1]})
        b.execute({'kind':'interact','object':'portcullis_lever'})
        self.assertFalse(b.board.tile((8,3)).blocked)
        self.activate(b, 'captain')
        b.execute({'kind':'move','cell':[10,3]})
        self.assertEqual(b.result, 'victory')

    def test_passage_budget_direction_and_occupied_landing(self):
        b = self.battle()
        b.execute({'kind':'start_battle'})
        p = next(o for o in b.mission.objects if o['id']=='grapple')
        p.update(enabled=True, cost=5, bidirectional=False)
        self.activate(b, 'captain')
        u = b.unit('captain'); u.pos = (7,1); u.move = 4
        self.assertNotIn((8,1), b.reachable())
        p['cost'] = 2
        b.unit('engineer').pos = (8,1)
        self.assertNotIn((8,1), b.reachable())
        b.unit('engineer').pos = (1,5)
        b.execute({'kind':'move','cell':[8,1]})
        self.activate(b, 'captain')
        self.assertNotIn((7,1), b.reachable())

    def test_defender_ai_uses_oil_and_cooldown_is_atomic(self):
        b = self.battle()
        b.execute({'kind':'start_battle'})
        b.unit('captain').pos = (7,3)
        self.activate(b, 'oil_keeper')
        command = {'kind':'interact','object':'boiling_oil'}
        before = b.digest()
        self.assertEqual(choose_command(b), command)
        self.assertEqual(b.digest(), before)
        b.execute(command)
        self.assertEqual(b.unit('captain').hp, 22)
        self.activate(b, 'oil_keeper')
        before = b.digest()
        with self.assertRaises(RuleError): b.execute(command)
        self.assertEqual(before, b.digest())
        b.tick += 20
        b.execute(command)
        self.activate(b, 'oil_keeper'); b.tick += 20
        with self.assertRaises(RuleError): b.execute(command)

    def test_sabotage_disables_defense(self):
        b = self.battle(); b.execute({'kind':'start_battle'})
        b.unit('captain').pos = (8,1)
        self.activate(b, 'captain')
        b.execute({'kind':'interact','object':'boiling_oil'})
        self.activate(b, 'oil_keeper')
        with self.assertRaises(RuleError): b.execute({'kind':'interact','object':'boiling_oil'})
        self.assertTrue(any(e['kind']=='defense_sabotaged' for e in b.events))

    def test_area_friendly_fire_and_large_unit_hit_once(self):
        b = self.battle(); b.execute({'kind':'start_battle'})
        b.unit('captain').pos = (7,2); b.unit('captain').footprint = (1,2)
        b.unit('defender').pos = (7,4)
        self.activate(b, 'oil_keeper')
        b.execute({'kind':'interact','object':'boiling_oil'})
        self.assertEqual(b.unit('captain').hp,22)
        self.assertEqual(b.unit('defender').hp,22)

    def test_oil_and_passages_replay_exactly(self):
        c = siege_content()
        m = c.missions['castle_ramparts']; m.deployment = []
        m.units[0].pos = (7,1); m.units[0].ct = 100
        b = Battle(c, m.id)
        b.execute({'kind':'interact','object':'grapple'})
        b.execute({'kind':'move','cell':[8,1]})
        self.assertEqual(Battle.replay(b.recording()).digest(),b.digest())
        m.units[0].pos = (7,3); m.units[0].ct = 0
        m.units[-1].ct = 100
        b = Battle(c, m.id)
        b.execute({'kind':'interact','object':'boiling_oil'})
        self.assertEqual(Battle.replay(b.recording()).digest(),b.digest())

    def test_every_route_finishes_in_throne_room_and_keeps_resources(self):
        for route in ('ram','artillery','infiltrate'):
            session = ScenarioSession(siege_content(), ScenarioDirector.from_dict(SIEGE_CAMPAIGN))
            for choice in (route, 'continue', 'continue'):
                session.battle.result = 'victory'
                session.battle.tick = 12
                session.battle.unit('captain').hp = 21
                session.battle.inventory['player']['potion'] = 1
                session.complete(choice)
            self.assertEqual(session.battle.mission.id,'castle_throne')
            self.assertEqual(session.elapsed_ticks,36)
            self.assertEqual(session.battle.unit('captain').hp,21)
            self.assertEqual(session.battle.inventory['player']['potion'],1)
            self.assertEqual(session.battle.mission.objective,'eliminate')
            session.battle.result = 'victory'; session.complete('finish')
            self.assertTrue(session.director.completed)

    def test_defeat_cannot_unlock_the_throne(self):
        s = ScenarioSession(siege_content(),ScenarioDirector.from_dict(SIEGE_CAMPAIGN))
        s.battle.result = 'defeat'; before = deepcopy(s.state())
        with self.assertRaises(RuleError): s.complete('ram')
        self.assertEqual(s.state(),before)

    def test_siege_ai_never_executes_blocked_ram_interaction(self):
        from sporebound.ai import simulate
        b = Battle(siege_content(), 'castle_ram')
        simulate(b, 35)
        self.assertEqual(Battle.replay(b.recording()).digest(), b.digest())

    def test_operator_holds_post_before_targets_arrive(self):
        b = self.battle(); b.execute({'kind':'start_battle'})
        self.activate(b, 'oil_keeper')
        command = choose_command(b)
        if command['kind'] == 'move':
            x,y = command['cell']
            self.assertLessEqual(abs(x-9)+abs(y-1),1)
        b.execute(command)

    def test_authoring_validation(self):
        for change in ({'charges':-1},{'cooldown':0},{'cells':[]},{'team':'nobody'}):
            c = siege_content().to_dict()
            m = next(m for m in c['missions'] if m['id']=='castle_ramparts')
            next(o for o in m['objects'] if o['kind']=='defense').update(change)
            with self.assertRaises(RuleError): Content.from_dict(c)


    def test_throne_room_defenses_and_sabotage(self):
        b = Battle(siege_content(), 'castle_throne', seed=11)
        b.execute({'kind': 'start_battle'})
        self.assertEqual(len([o for o in b.mission.objects if o['kind'] == 'defense']), 2)
        b.unit('captain').pos = (6, 3)
        self.activate(b, 'royal_guard_left')
        b.execute({'kind': 'interact', 'object': 'throne_arrow_slit'})
        self.assertEqual(b.unit('captain').hp, 29)
        slit = next(o for o in b.mission.objects if o['id'] == 'throne_arrow_slit')
        self.assertEqual(slit['charges'], 2)
        self.activate(b, 'captain')
        b.unit('captain').pos = (9, 3)
        b.execute({'kind': 'interact', 'object': 'throne_arrow_slit'})
        self.assertTrue(slit['disabled'])
        self.assertTrue(any(e['kind'] == 'defense_sabotaged' for e in b.events))
        self.activate(b, 'royal_guard_left')
        with self.assertRaises(RuleError):
            b.execute({'kind': 'interact', 'object': 'throne_arrow_slit'})

    def test_castellan_second_phase_queues_bounded_reinforcements_once(self):
        b = Battle(siege_content(), 'castle_throne', seed=11)
        b.execute({'kind': 'start_battle'})
        self.assertNotIn('haste', b.unit('castellan').statuses)
        b.unit('castellan').hp = 32
        b._triggers()
        self.assertIn('haste', b.unit('castellan').statuses)
        self.assertTrue(any(u.id == 'throne_reserve_north' for u in b.units))
        self.assertTrue(any(u.id == 'throne_reserve_south' for u in b.units))
        before = len([e for e in b.events if e['kind'] == 'reinforcement_wave'])
        b._triggers()
        self.assertEqual(len([e for e in b.events if e['kind'] == 'reinforcement_wave']), before)
        self.assertEqual(len([e for e in b.events if e['kind'] == 'trigger'
                              and e['id'] == 'castellan_second_phase']), 1)

    def test_castellan_phase_authoring_rejects_invalid_thresholds(self):
        for value in (0, 100, -1, '50'):
            data = siege_content().to_dict()
            throne = next(m for m in data['missions'] if m['id'] == 'castle_throne')
            phase = next(t for t in throne['triggers'] if t['id'] == 'castellan_second_phase')
            phase['percent'] = value
            with self.assertRaises(RuleError):
                Content.from_dict(data)


if __name__=='__main__': unittest.main()

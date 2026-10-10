"""Siege traversal, defender AI, sabotage and final encounter progression."""
from copy import deepcopy
import unittest
from examples.siege_scenarios import siege_content
from examples.siege_campaign import SIEGE_CAMPAIGN
from sporebound.ai import choose_command
from sporebound.engine import Battle
from sporebound.model import Content, RuleError
from sporebound.scenarios import ScenarioDirector, ScenarioSession
from sporebound.siege import available_operations


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

    def test_catapult_ammunition_is_finite_and_replayable(self):
        data = siege_content().to_dict()
        mission = next(m for m in data['missions'] if m['id'] == 'castle_artillery')
        next(o for o in mission['objects'] if o['kind'] == 'door')['hp'] = 8
        catapult = next(o for o in mission['objects'] if o['kind'] == 'catapult')
        catapult['ammo'] = 1
        mission['units'][1]['ct'] = 100
        content = Content.from_dict(data)
        b = Battle(content, 'castle_artillery', seed=17)
        b.execute({'kind': 'start_battle'})
        self.assertEqual(b.active_id, 'engineer')
        b.execute({'kind': 'interact', 'object': 'catapult'})
        self.assertEqual(next(o for o in b.mission.objects if o['id'] == 'catapult')['ammo'], 0)
        self.assertEqual(next(o for o in b.mission.objects if o['id'] == 'main_gate')['hp'], 6)
        before = b.digest()
        with self.assertRaises(RuleError):
            b.execute({'kind': 'interact', 'object': 'catapult'})
        self.assertEqual(before, b.digest())
        self.assertEqual(Battle.replay(b.recording()).digest(), b.digest())

    def test_siege_engine_can_be_attacked_and_repaired_with_limited_charges(self):
        b = self.battle()
        b.execute({'kind': 'start_battle'})
        ram = next(o for o in b.mission.objects if o['id'] == 'ram')
        ram['hp'] = 7
        self.activate(b, 'defender')
        b.unit('defender').pos = (4, 3)
        b.execute({'kind': 'siege_attack', 'object': 'ram'})
        self.assertEqual(ram['hp'], 1)
        self.assertTrue(any(e['kind'] == 'siege_damaged' for e in b.events))
        self.activate(b, 'engineer')
        b.unit('engineer').pos = (3, 4)
        b.execute({'kind': 'repair_siege', 'object': 'ram'})
        self.assertEqual(ram['hp'], 9)
        self.assertEqual(ram['repair_charges'], 1)
        self.activate(b, 'engineer')
        b.execute({'kind': 'repair_siege', 'object': 'ram'})
        self.assertEqual(ram['hp'], 17)
        self.assertEqual(ram['repair_charges'], 0)
        before = b.digest()
        with self.assertRaises(RuleError):
            b.execute({'kind': 'repair_siege', 'object': 'ram'})
        self.assertEqual(before, b.digest())

    def test_defender_ai_targets_an_enemy_siege_engine(self):
        data = siege_content().to_dict()
        mission = next(m for m in data['missions'] if m['id'] == 'castle_ram')
        ram = next(o for o in mission['objects'] if o['kind'] == 'ram')
        ram.update(team='player', pos=[7, 3], hp=18, max_hp=18)
        defender = next(u for u in mission['units'] if u['id'] == 'defender')
        defender['pos'] = [6, 3]
        content = Content.from_dict(data)
        b = Battle(content, 'castle_ram')
        b.execute({'kind': 'start_battle'})
        self.activate(b, 'defender')
        self.assertEqual(choose_command(b), {'kind': 'siege_attack', 'object': 'ram'})
        b.execute(choose_command(b))
        self.assertLess(next(o for o in b.mission.objects if o['id'] == 'ram')['hp'], 18)

    def test_enemy_crew_can_operate_a_ram_and_breach_a_gate(self):
        data = siege_content().to_dict()
        mission = next(m for m in data['missions'] if m['id'] == 'castle_ram')
        ram = next(o for o in mission['objects'] if o['kind'] == 'ram')
        ram.update(team='enemy', pos=[7, 3])
        next(o for o in mission['objects'] if o['kind'] == 'door')['hp'] = 1
        next(u for u in mission['units'] if u['id'] == 'defender').update(pos=[6, 3], ct=100)
        content = Content.from_dict(data)
        b = Battle(content, 'castle_ram')
        b.execute({'kind': 'start_battle'})
        self.assertEqual(b.active_id, 'defender')
        b.execute(choose_command(b))
        self.assertTrue(any(e['kind'] == 'gate_breached' for e in b.events))

    def test_siege_engine_validation_rejects_invalid_state(self):
        for change in ({'hp': 0}, {'hp': 20}, {'max_hp': 0}, {'ammo': -1},
                       {'repair': 0}, {'repair_charges': -1}, {'team': 'neutral'}):
            data = siege_content().to_dict()
            mission = next(m for m in data['missions'] if m['id'] == 'castle_artillery')
            next(o for o in mission['objects'] if o['kind'] == 'catapult').update(change)
            with self.assertRaises(RuleError):
                Content.from_dict(data)

    def test_ui_operations_are_contextual_to_engine_team_and_damage(self):
        b = self.battle()
        b.execute({'kind': 'start_battle'})
        captain = b.unit('captain')
        ram = next(o for o in b.mission.objects if o['id'] == 'ram')
        captain.pos = (2, 3)
        ram['hp'] = 10
        self.assertEqual(available_operations(b, captain), ['repair-siege:ram'])
        ram['team'] = 'enemy'
        self.assertEqual(available_operations(b, captain), ['siege-attack:ram'])
        captain.pos = (0, 0)
        self.assertEqual(available_operations(b, captain), [])


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


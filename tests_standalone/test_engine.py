import copy
import unittest

from sporebound.engine import Battle
from sporebound.model import Board, Content, Effect, Mission, RuleError, Skill, Tile, Unit


def fixture(**kwargs):
    skills = {
        'fire': Skill('fire','Fire',[Effect('damage',10,'fire')],cost=3,range=6,magical=True),
        'heal': Skill('heal','Heal',[Effect('heal',20)],cost=2,range=4,target='ally'),
        'cast': Skill('cast','Cast',[Effect('damage',10,'fire')],cost=3,range=6,magical=True,cast_ticks=12,lock='unit'),
        'area': Skill('area','Area',[Effect('damage',2,scope='all')],range=6,radius=1,target='ground'),
        'revive': Skill('revive','Revive',[Effect('revive',15)],range=4,target='downed'),
        'push': Skill('push','Push',[Effect('push',2)],range=3),
        'silence': Skill('silence','Silence',[Effect('status',status='silence')],range=6),
        'zone': Skill('zone','Zone',[Effect('zone',5,scope='enemies',duration=30)],range=6,target='ground'),
    }
    a = Unit('a','Hero','player',(0,1),speed=10,skills=list(skills),**kwargs)
    b = Unit('b','Enemy','enemy',(3,1),speed=10)
    c = Content(skills, {'test':Mission('test','Test',Board(8,5),[a,b])})
    return Battle(c,'test',seed=7)


class TurnTests(unittest.TestCase):
    def test_zero_ct_then_roster_tie_break(self):
        b = fixture()
        self.assertEqual((b.tick,b.active_id,b.active.ct),(10,'a',100))
        b.execute({'kind':'end'})
        self.assertEqual((b.tick,b.active_id), (10,'b'))
        self.assertEqual(b.unit('a').ct,40)

    def test_ct_costs_and_overflow(self):
        for moved,acted,cost in [(False,False,60),(True,False,80),(False,True,80),(True,True,100)]:
            b=fixture(); u=b.active; u.ct=127; u.moved=moved; u.acted=acted
            b.execute({'kind':'end'})
            self.assertEqual(b.unit('a').ct,min(60,127-cost))

    def test_move_then_act_and_act_then_move(self):
        for order in [('move','act'),('act','move')]:
            b=fixture()
            commands={'move':dict(kind='move',cell=[1,1]),'act':dict(kind='act',skill='fire',cell=[3,1])}
            for kind in order: b.execute(commands[kind])
            self.assertTrue(b.active.moved and b.active.acted)

    def test_double_actions_rejected_atomically(self):
        b=fixture(); b.execute(dict(kind='act',skill='fire',cell=[3,1])); before=b.digest()
        with self.assertRaises(RuleError): b.execute(dict(kind='act',skill='fire',cell=[3,1]))
        self.assertEqual(before,b.digest())
        self.assertEqual(len(b.commands),1)

    def test_wrong_unit_and_malformed_commands(self):
        for command in [dict(kind='move',cell=[1,1],unit='b'),dict(kind='move',cell=['a',1]),dict(kind='move'),dict(kind='bogus'),dict(kind='end',facing=[2,2])]:
            b=fixture(); before=b.digest()
            with self.assertRaises(RuleError): b.execute(command)
            self.assertEqual(before,b.digest())
            self.assertEqual(b.commands,[])

    def test_haste_slow_and_stop_clock(self):
        for status,ct in [('haste',15),('slow',5),('stop',0),('sleep',0)]:
            b=fixture(); a=b.unit('a'); enemy=b.unit('b'); a.ct=0; a.statuses={status:20}; enemy.ct=90
            b.active_id=None; b._advance()
            self.assertEqual(a.ct,ct)
            self.assertEqual(a.statuses[status],19)

    def test_permanent_status_refresh_stays_permanent(self):
        b=fixture(); b.active.statuses['protect']=-1
        b._status(b.active,'protect',12)
        self.assertEqual(b.active.statuses['protect'],-1)

    def test_mid_move_sleep_stops_path_and_activation(self):
        b=fixture()
        b.mission.triggers=[dict(id='sleep',condition='enter',pos=[1,1],actions=[dict(kind='status',unit='a',status='sleep',duration=20)])]
        b.execute(dict(kind='move',cell=[2,1]))
        self.assertEqual(b.unit('a').pos,(1,1))
        self.assertEqual(b.active_id,'b')

    def test_sealed_commands_pay_ct(self):
        b=fixture(); a=b.unit('a'); a.statuses={'dont_move':20,'dont_act':20}; a.ct=100
        b.active_id=None; b._advance()
        self.assertTrue(a.moved and a.acted)
        b.execute({'kind':'end'})
        self.assertEqual(a.ct,0)


class MovementTests(unittest.TestCase):
    def test_dijkstra_weight_and_walls(self):
        b=fixture(); b.board.tiles[(1,1)]=Tile(cost=4)
        self.assertEqual(b.reachable()[(2,1)][0],4)
        self.assertNotIn((3,1),b.reachable())
        b.board.tiles[(1,1)]=Tile(blocked=True)
        self.assertNotIn((1,1),b.reachable())
        self.assertEqual(b.reachable()[(2,1)][1],[(0,1),(0,0),(1,0),(2,0),(2,1)])

    def test_height_and_ignore_height(self):
        b=fixture(); b.board.tiles[(1,1)]=Tile(height=3)
        self.assertNotIn((1,1),b.reachable())
        b.active.movement='ignore_height'
        self.assertIn((1,1),b.reachable())

    def test_hazard_death_stops_movement_and_changes_turn(self):
        b=fixture(); b.units.append(Unit('ally','Ally','player',(0,4)))
        b.active.hp=1; b.board.tiles[(1,1)]=Tile(hazard=10)
        b.execute(dict(kind='move',cell=[2,1]))
        self.assertEqual(b.unit('a').pos,(1,1))
        self.assertFalse(b.unit('a').alive)
        self.assertEqual(b.active_id,'b')

    def test_los_blocked_corner_and_height(self):
        b=fixture(); b.board.tiles[(1,0)]=Tile(blocked=True)
        self.assertFalse(b.line_of_sight((0,0),(1,1)))
        self.assertFalse(b.line_of_sight((1,1),(0,0)))
        b.board.tiles={(1,1):Tile(height=3)}
        self.assertFalse(b.line_of_sight((0,1),(2,1)))

    def test_push_collision_fall_and_hazard(self):
        b=fixture(); target=b.unit('b'); b.board.tiles[(3,1)]=Tile(height=4)
        b.board.tiles[(5,1)]=Tile(blocked=True)
        b.execute(dict(kind='act',skill='push',cell=[3,1]))
        self.assertEqual(target.pos,(4,1))
        self.assertEqual(target.hp,25)

    def test_move_mp_up(self):
        b=fixture(movement='move_mp_up',mp=0)
        b.execute(dict(kind='move',cell=[1,1]))
        self.assertEqual(b.active.mp,1)

    def test_opportunity_reaction(self):
        b=fixture(); b.unit('b').pos=(1,1); b.unit('b').reaction='opportunity'; b.unit('b').brave=100
        b.execute(dict(kind='move',cell=[0,0]))
        self.assertEqual(b.unit('a').hp,25)

    def test_teleport_over_cliff(self):
        b=fixture(movement='teleport'); b.board.tiles[(1,1)]=Tile(height=8)
        b.execute(dict(kind='move',cell=[1,1]))
        self.assertEqual(b.active.pos,(1,1))


class CombatTests(unittest.TestCase):
    def test_directional_evasion(self):
        b=fixture(); a=b.active; t=b.unit('b'); t.facing=(-1,0)
        t.class_evade=50; t.shield_evade=50; t.accessory_evade=20; t.weapon_evade=50
        s=b._basic(a)
        self.assertAlmostEqual(b.hit_chance(a,t,s),.1)
        a.pos=(3,0); self.assertAlmostEqual(b.hit_chance(a,t,s),.2)
        a.pos=(4,1); self.assertAlmostEqual(b.hit_chance(a,t,s),.8)
        a.support='concentrate'; self.assertEqual(b.hit_chance(a,t,s),1)
        t.reaction='blade_grasp'; t.brave=100
        self.assertEqual(b.hit_chance(a,t,s),0)

    def test_charging_ignores_evasion_and_increases_physical_damage(self):
        b=fixture(); a=b.active; t=b.unit('b'); t.cast={'skill':'cast','remaining':4}
        t.accessory_evade=100
        self.assertEqual(b.hit_chance(a,t,b._basic(a)),1)
        self.assertEqual(b.damage(a,t,b._basic(a),Effect()),22)

    def test_faith_resistance_protect_shell(self):
        b=fixture(); a=b.active; t=b.unit('b'); s=b.content.skills['fire']
        self.assertEqual(b.damage(a,t,s,s.effects[0]),21)
        t.resistances['fire']=50
        self.assertEqual(b.damage(a,t,s,s.effects[0]),10)
        t.resistances.clear(); t.statuses['shell']=20
        self.assertEqual(b.damage(a,t,s,s.effects[0]),14)

    def test_forecast_has_no_side_effects(self):
        b=fixture(); before=b.digest()
        for _ in range(10): self.assertEqual(b.forecast('fire',(3,1))[0]['amount'],21)
        self.assertEqual(before,b.digest())

    def test_aoe_friendly_fire(self):
        b=fixture(); b.units.append(Unit('friend','Friend','player',(3,2)))
        b.execute(dict(kind='act',skill='area',cell=[3,1]))
        self.assertEqual(b.unit('b').hp,30)
        self.assertEqual(b.unit('friend').hp,30)

    def test_heal_capped(self):
        b=fixture(hp=35)
        b.execute(dict(kind='act',skill='heal',cell=[0,1]))
        self.assertEqual(b.active.hp,40)

    def test_counter_cannot_recurse(self):
        b=fixture(reaction='counter',brave=100); b.unit('b').pos=(1,1); b.unit('b').reaction='counter'; b.unit('b').brave=100
        b.execute(dict(kind='act',skill='attack',cell=[1,1]))
        self.assertEqual((b.unit('a').hp,b.unit('b').hp),(25,25))
        self.assertEqual(sum(e['kind']=='counter' for e in b.events),1)

    def test_mp_switch_redirects_hit_exceeding_mp(self):
        b=fixture(); t=b.unit('b'); t.reaction='mp_switch'; t.brave=100; t.mp=1
        b.execute(dict(kind='act',skill='fire',cell=[3,1]))
        self.assertEqual((t.hp,t.mp),(40,0))

    def test_auto_potion_consumes_inventory(self):
        b=fixture(); t=b.unit('b'); t.reaction='auto_potion'; t.brave=100
        b.execute(dict(kind='act',skill='fire',cell=[3,1]))
        self.assertEqual((t.hp,b.inventory['enemy']['potion']),(40,0))

    def test_revive_and_occupied_corpse(self):
        b=fixture(); b.units.append(Unit('friend','Friend','player',(1,1),hp=0))
        b.execute(dict(kind='act',skill='revive',cell=[1,1]))
        self.assertEqual(b.unit('friend').hp,15)
        b=fixture(); b.units.append(Unit('friend','Friend','player',(3,1),hp=0)); before=b.digest()
        with self.assertRaises(RuleError): b.execute(dict(kind='act',skill='revive',cell=[3,1]))
        self.assertEqual(before,b.digest())

    def test_items_and_empty_inventory(self):
        b=fixture(hp=5); b.execute(dict(kind='item',item='potion',cell=[0,1]))
        self.assertEqual((b.active.hp,b.inventory['player']['potion']),(30,2))
        b=fixture(); b.inventory['player']['potion']=0
        with self.assertRaises(RuleError): b.execute(dict(kind='item',item='potion',cell=[0,1]))

    def test_zone_ticks_end_activation(self):
        b=fixture(); b.execute(dict(kind='act',skill='zone',cell=[3,1]))
        b.execute({'kind':'end'}); b.execute({'kind':'end'})
        self.assertEqual(b.unit('b').hp,35)

    def test_poison_regen_and_status_cancellation(self):
        b=fixture(); a=b.active; a.statuses['poison']=30
        b.execute({'kind':'end'}); self.assertEqual(a.hp,35)
        b._status(a,'regen',30)
        self.assertNotIn('poison',a.statuses)
        self.assertIn('regen',a.statuses)


class CastingTests(unittest.TestCase):
    def test_cast_paid_at_resolution_and_unit_lock(self):
        b=fixture(); b.unit('b').max_hp=b.unit('b').hp=100
        b.execute(dict(kind='act',skill='cast',cell=[3,1]))
        self.assertEqual(b.active.mp,12)
        b.unit('b').pos=(7,4)
        while b.tick<22:
            b.execute({'kind':'end'})
        self.assertEqual(b.unit('a').mp,9)
        self.assertEqual(b.unit('b').hp,79)

    def test_cell_lock_misses_moving_target(self):
        b=fixture(); b.content.skills['cast'].lock='cell'
        b.execute(dict(kind='act',skill='cast',cell=[3,1])); b.unit('b').pos=(7,4)
        while b.tick<22: b.execute({'kind':'end'})
        self.assertEqual(b.unit('b').hp,40)
        self.assertEqual(b.unit('a').mp,9)

    def test_wait_and_move_preserve_cast_another_action_cancels(self):
        b=fixture(); b.execute(dict(kind='act',skill='cast',cell=[3,1])); b.execute(dict(kind='move',cell=[1,1]))
        self.assertIsNotNone(b.active.cast)
        b.execute({'kind':'end'})
        while b.active_id != 'a': b.execute({'kind':'end'})
        self.assertEqual(b.active_id,'a')
        self.assertIsNotNone(b.active.cast)
        b.execute(dict(kind='act',skill='fire',cell=[3,1]))
        self.assertIsNone(b.active.cast)
        self.assertEqual(b.active.mp,9)

    def test_silence_interrupts_magic_and_short_charge(self):
        b=fixture(support='short_charge'); b.execute(dict(kind='act',skill='cast',cell=[3,1]))
        self.assertEqual(b.active.cast['remaining'],6)
        b._status(b.active,'silence',20)
        self.assertIsNone(b.active.cast)
        self.assertEqual(b.active.mp,12)

    def test_insufficient_mp_at_resolution(self):
        b=fixture(); b.execute(dict(kind='act',skill='cast',cell=[3,1])); b.active.mp=0
        while b.tick<22: b.execute({'kind':'end'})
        self.assertEqual(b.unit('b').hp,40)
        self.assertTrue(any(e['kind']=='cast_failed' for e in b.events))


class MissionTests(unittest.TestCase):
    def test_extract_and_protected_unit_defeat(self):
        b=fixture(); b.mission.objective='extract'; b.mission.goal=[(1,1)]
        b.execute(dict(kind='move',cell=[1,1])); self.assertEqual(b.result,'victory')
        b=fixture(); b.mission.protected_id='a'; b.units.append(Unit('friend','Friend','player',(0,4)))
        b.active.hp=1; b.board.tiles[(1,1)]=Tile(hazard=10)
        b.execute(dict(kind='move',cell=[1,1])); self.assertEqual(b.result,'defeat')

    def test_survive_and_contested_hold(self):
        b=fixture(); b.mission.objective='survive'; b.mission.target_ticks=12
        b.execute({'kind':'end'}); b.execute({'kind':'end'})
        self.assertEqual((b.result,b.tick),('victory',12))
        b=fixture(); b.mission.objective='hold'; b.mission.goal=[(0,1),(3,1)]; b.mission.target_ticks=2
        b.execute({'kind':'end'}); b.execute({'kind':'end'})
        self.assertEqual(b.hold_ticks,0)
        b.unit('b').pos=(7,4)
        while not b.result: b.execute({'kind':'end'})
        self.assertEqual(b.result,'victory')

    def test_triggers_once_and_objects(self):
        b=fixture(); b.mission.triggers=[dict(id='t',condition='enter',pos=[1,1],actions=[dict(kind='hazard',pos=[2,1],amount=3)])]
        b.execute(dict(kind='move',cell=[1,1])); b._triggers()
        self.assertEqual(b.fired,['t']); self.assertEqual(b.board.tile((2,1)).hazard,3)
        b=fixture(); b.mission.objects=[dict(id='chest',kind='chest',pos=[1,1],amount=20)]
        b.execute(dict(kind='interact',object='chest'))
        self.assertEqual(b.loot,20)
        b.active.acted=False
        with self.assertRaises(RuleError): b.execute(dict(kind='interact',object='chest'))

    def test_switch_opens_door(self):
        b=fixture(); content=copy.deepcopy(b.content)
        content.missions['test'].objects=[dict(id='d',kind='door',pos=[2,1]),dict(id='s',kind='switch',pos=[1,1],link='d')]
        content.validate(); b=Battle(content,'test')
        self.assertTrue(b.board.tile((2,1)).blocked)
        b.execute(dict(kind='interact',object='s'))
        self.assertFalse(b.board.tile((2,1)).blocked)


class TeamTacticsTests(unittest.TestCase):
    def test_engagement_zone_and_spear_reach(self):
        b=fixture()
        enemy=b.unit('b')
        enemy.pos=(1,1)
        self.assertEqual([u.id for u in b.engaged_by(b.active)], ['b'])
        self.assertEqual(b.engagement_threats((0,1),'player')[0]['range'],1)
        enemy.weapon='spear'
        enemy.pos=(2,1)
        self.assertEqual([u.id for u in b.engaged_by(b.active)], ['b'])
        self.assertEqual(b.engagement_range(enemy),2)
        self.assertEqual(b._basic(enemy).range,2)

    def test_los_range_falloff_and_engaged_ranged_penalty(self):
        b=fixture(weapon='ranged',attack_range=4,min_range=1,attack_range_mode='los',
                  optimal_range=4,falloff_per_tile=10)
        a=b.active; target=b.unit('b'); target.pos=(7,1)
        skill=b._basic(a)
        self.assertGreaterEqual(skill.range,7)
        self.assertAlmostEqual(b.hit_chance(a,target,skill),.7)
        b.units.append(Unit('engager','Engager','enemy',(1,1)))
        self.assertAlmostEqual(b.hit_chance(a,target,skill),.455)

    def test_overwatch_is_prepared_single_charge_and_costs_ct(self):
        b=fixture(weapon='ranged',attack_range=4,min_range=1)
        b.execute({'kind':'prepare','mode':'overwatch'})
        self.assertEqual(b.prepared_reactions['a']['charges'],1)
        b.execute({'kind':'end'})
        self.assertEqual(b.active_id,'b')
        b.execute({'kind':'move','cell':[2,1]})
        self.assertEqual(b.unit('b').hp,19)
        self.assertNotIn('a',b.prepared_reactions)
        self.assertEqual(b.unit('a').ct,0)
        self.assertTrue(any(e['kind']=='prepared_triggered' and e['mode']=='overwatch' for e in b.events))

    def test_guard_triggers_on_entry_to_engagement(self):
        b=fixture()
        b.execute({'kind':'prepare','mode':'guard'})
        b.execute({'kind':'end'})
        b.execute({'kind':'move','cell':[1,1]})
        self.assertEqual(b.unit('b').hp,25)
        self.assertTrue(any(e['kind']=='engagement_entered' and e['unit']=='b' for e in b.events))
        self.assertTrue(any(e['kind']=='prepared_triggered' and e['mode']=='guard' for e in b.events))

    def test_pincer_followup_spends_partner_ct(self):
        b=fixture()
        a=b.active; target=b.unit('b')
        a.pos=(2,1); a.tactics=['pincer']
        partner=Unit('ally','Ally','player',(4,1),ct=40,tactics=['pincer'])
        b.units.append(partner)
        options=b.available_team_tactics(a,target)
        self.assertEqual(options,[{'id':'pincer','partner':'ally','target':'b','ct_cost':20}])
        b.execute({'kind':'act','skill':'attack','cell':[3,1]})
        self.assertEqual(target.hp,18)
        self.assertEqual(partner.ct,20)
        self.assertTrue(any(e['kind']=='tactic' and e['tactic']=='pincer' for e in b.events))

    def test_prepared_reaction_is_replay_deterministic(self):
        b=fixture(weapon='ranged',attack_range=4,min_range=1)
        b.execute({'kind':'prepare','mode':'overwatch'})
        b.execute({'kind':'end'})
        b.execute({'kind':'move','cell':[2,1]})
        self.assertEqual(Battle.replay(b.recording()).digest(),b.digest())


    def test_disengage_spends_action_and_avoids_opportunity(self):
        b=fixture()
        enemy=b.unit('b'); enemy.pos=(1,1); enemy.reaction='opportunity'; enemy.brave=100
        b.execute({'kind':'disengage'})
        self.assertTrue(b.active.acted and b.active.disengaging)
        b.execute({'kind':'move','cell':[0,0]})
        self.assertEqual(b.unit('a').hp,40)
        self.assertFalse(b.unit('a').disengaging)
        self.assertTrue(any(e['kind']=='disengaged' for e in b.events))


    def test_brace_absorbs_forced_movement(self):
        b=fixture()
        b.execute({'kind':'prepare','mode':'brace'})
        a=b.unit('a')
        self.assertIn('a',b.prepared_reactions)
        b._displace(b.unit('b'),a,2)
        self.assertEqual(a.pos,(0,1))
        self.assertNotIn('a',b.prepared_reactions)
        self.assertTrue(any(e['kind']=='brace' and e['absorbed']==2 for e in b.events))


    def test_sleep_cancels_prepared_reaction(self):
        b=fixture()
        b.execute({'kind':'prepare','mode':'guard'})
        self.assertIn('a',b.prepared_reactions)
        b._status(b.unit('a'),'sleep',10)
        self.assertNotIn('a',b.prepared_reactions)
        self.assertTrue(any(e['kind']=='prepared_cancelled' and e['reason']=='sleep' for e in b.events))


if __name__=='__main__': unittest.main()

"""3.7.20C2: conservative cross-floor attacks, stair AI and replay safety."""
from copy import deepcopy
import unittest

from examples.layered_house_3720c import create
from sporebound.ai import choose_command
from sporebound.engine import Battle
from sporebound.interior_levels import edit_interior_tile
from sporebound.model import Content, RuleError
from sporebound.vertical_combat import shaft_openings


MID = 'layered_house_3720c'


def scenario(*, aperture=False):
    data, mid = create()
    mission = next(m for m in data['missions'] if m['id'] == mid)
    house = mission['structures'][0]
    # Put the staircase beside, rather than directly through, the firing
    # aperture. Its endpoints remain present and valid after drilling a hole.
    mission['level_links'][0]['from'] = [0, 5, 5]
    mission['level_links'][0]['to'] = [1, 5, 5]
    if aperture:
        data = edit_interior_tile(data, mid, house['id'], 1,
                                   (4, 5), present=False)
    mission = next(m for m in data['missions'] if m['id'] == mid)
    for actor in mission['units']:
        actor['speed'] = 1000 if actor['team'] == 'player' else 1
    return Content.from_dict(data), mid


class VerticalCombatTests(unittest.TestCase):
    def test_roof_occludes_basic_cross_floor_shot(self):
        content, mid = scenario(aperture=False)
        battle = Battle(content, mid, seed=17, battle_id='closed-ceiling')
        shooter = battle.active
        self.assertEqual(shooter.weapon, 'focus')
        upper = next(u for u in battle.units if u.team == 'enemy')
        self.assertEqual(battle.unit_levels[upper.id], 1)
        before = battle.digest()
        with self.assertRaisesRegex(RuleError, 'blocked|opening'):
            battle.execute({'kind': 'level_attack', 'level': 1,
                            'cell': [4, 4]})
        self.assertEqual(battle.digest(), before)
        self.assertFalse(shooter.acted)

    def test_shaft_attack_consumes_action_and_replays(self):
        content, mid = scenario(aperture=True)
        battle = Battle(content, mid, seed=17, battle_id='open-shaft')
        shooter = battle.active
        before = battle.digest()
        forecast = battle.vertical_forecast(1, (4, 4))
        self.assertEqual(battle.digest(), before)
        self.assertEqual(forecast['kind'], 'vertical_attack')
        self.assertEqual(forecast['unit'], next(
            u.id for u in battle.units if u.team == 'enemy'))
        self.assertGreater(forecast['amount'], 0)
        self.assertTrue(0 < forecast['chance'] <= 1)
        battle.execute({'kind': 'level_attack', 'level': 1, 'cell': [4, 4]})
        self.assertTrue(battle.unit(shooter.id).acted)
        self.assertEqual(battle.commands[-1]['kind'], 'level_attack')
        self.assertTrue(any(event['kind'] == 'vertical_shot'
                            and event['target_level'] == 1
                            for event in battle.events))
        self.assertEqual(Battle.replay(battle.recording()).digest(),
                         battle.digest())

    def test_range_weapon_and_invalid_level_are_atomic(self):
        content, mid = scenario(aperture=True)
        for weapon, lvl in (('melee', 1), ('focus', 3),
                            ('focus', 0), ('focus', True)):
            trial = deepcopy(content.to_dict())
            mission = next(m for m in trial['missions'] if m['id'] == mid)
            next(u for u in mission['units']
                 if u['team'] == 'player')['weapon'] = weapon
            battle = Battle(Content.from_dict(trial), mid,
                            seed=17, battle_id='rejected')
            state = battle.digest()
            with self.subTest(weapon=weapon, level=lvl), self.assertRaises(RuleError):
                battle.execute({'kind': 'level_attack', 'level': lvl,
                                'cell': [4, 4]})
            self.assertEqual(battle.digest(), state)
            self.assertFalse(battle.active.acted)

    def test_floor_geometry_is_authoritative_not_roof_sprite(self):
        content, mid = scenario(aperture=True)
        mission = content.missions[mid]
        self.assertIn((4, 5), shaft_openings(mission, 1))
        self.assertNotIn((4, 4), shaft_openings(mission, 1))
        self.assertNotIn((5, 5), shaft_openings(mission, 1))

    def test_enemy_ai_uses_stairs_towards_ground_targets(self):
        content, mid = scenario(aperture=False)
        battle = Battle(content, mid, seed=4, battle_id='stairs-ai')
        enemy = next(u for u in battle.units if u.team == 'enemy')
        battle.active_id = enemy.id
        enemy.moved = False
        command = choose_command(battle)
        self.assertEqual(command['kind'], 'level_move')
        self.assertIn(command['level'], (0, 1))
        reachable = battle.level_reachable(enemy)
        self.assertIn((command['level'], *command['cell']), reachable)
        battle.execute(command)
        self.assertTrue(enemy.moved)

    def test_enemy_archer_fires_through_floor_aperture(self):
        content, mid = scenario(aperture=True)
        data = content.to_dict()
        mission = next(m for m in data['missions'] if m['id'] == mid)
        for row in mission['units']:
            row['speed'] = 1000 if row['team'] == 'enemy' else 1
            if row['team'] == 'enemy':
                row['weapon'] = 'ranged'
                row['attack_range'] = 4
        battle = Battle(Content.from_dict(data), mid, seed=13,
                        battle_id='archer-upper')
        archer = next(u for u in battle.units if u.team == 'enemy')
        self.assertEqual(battle.active_id, archer.id)
        decision = choose_command(battle)
        self.assertEqual(decision['kind'], 'level_attack')
        self.assertEqual(decision['level'], 0)
        battle.execute(decision)
        self.assertTrue(archer.acted)
        self.assertTrue(any(row['kind'] == 'vertical_shot'
                            for row in battle.events))
        self.assertEqual(Battle.replay(battle.recording()).digest(),
                         battle.digest())

    def test_prepared_archer_reacts_only_after_arrival_upstairs(self):
        content, mid = scenario(aperture=False)
        battle = Battle(content, mid, seed=19, battle_id='stair-reaction')
        archer = next(u for u in battle.units if u.team == 'enemy')
        archer.weapon = 'ranged'
        archer.attack_range = 4
        battle.prepared_reactions[archer.id] = {
            'mode': 'overwatch', 'charges': 1, 'ct_tax': 20}
        battle.execute({'kind': 'level_move', 'level': 1,
                        'cell': [5, 5]})
        self.assertEqual(battle.unit_levels[battle.active_id], 1)
        fired = [row for row in battle.events
                 if row['kind'] == 'prepared_triggered']
        self.assertEqual(len(fired), 1)
        self.assertEqual(fired[0]['unit'], archer.id)

    def test_legacy_content_and_shots_are_unmodified(self):
        from sporebound.__main__ import DEFAULT_CONTENT
        original = Content.load(DEFAULT_CONTENT)
        assert not any(m.level_links or m.unit_levels
                       for m in original.missions.values())
        self.assertEqual(Content.from_dict(original.to_dict()).to_dict(),
                         original.to_dict())


if __name__ == '__main__':
    unittest.main()

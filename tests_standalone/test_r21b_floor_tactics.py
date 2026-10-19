"""R21.B: floor-scoped formations, reactions and deterministic stair engagements.

Uses the real authored multi-floor house fixture. No second battle model,
fake damage formulas or manual patching of the live command recording.
"""
from copy import deepcopy
import unittest

from sporebound.engine import Battle
from sporebound.formations3 import (
    escorted, formation_control_map, formation_preview, phalanx, shield_wall,
)
from sporebound.model import Content, RuleError, Unit
from sporebound.tactical_intents import tactical_intents
from sporebound.tactical_rpg3 import tactical_rpg_rules
from tests_standalone.test_tactical_levels_3720c import TacticalFloorTests


def floor_battle(*, formation="phalanx", allies=True):
    authoring = TacticalFloorTests()
    authoring.setUp()  # Creates a validated 2-level house and authored stair.
    content = Content.from_dict(deepcopy(authoring.doc.data))
    mission = content.missions[authoring.MID]
    ground = next(u for u in mission.units if u.id == authoring.player)
    upper = next(u for u in mission.units if u.id == authoring.enemy)
    ground.speed = upper.speed = 1000
    ground.weapon = upper.weapon = "spear"
    if allies:
        ground.tags = ["formation:" + formation]
        upper.tags = ["formation:" + formation]
        upper.team = "player"
        mission.units.append(Unit(
            "hostile", "Hostile", "enemy", (12, 12),
            attack=25, weapon_power=9, speed=1))
    else:
        upper.weapon = "ranged"
        upper.attack_range = 4
        # Defender prepares upstairs before the attacker climbs the stairs.
        mission.units[:] = [upper, ground]
    return Battle(content, authoring.MID, seed=23, rules=tactical_rpg_rules()), ground.id, upper.id


class FormationFloorTests(unittest.TestCase):
    def test_spear_pair_requires_same_floor_then_activates_after_stairs(self):
        battle, ground_id, upstairs_id = floor_battle()
        ground = battle.unit(ground_id)
        upstairs = battle.unit(upstairs_id)
        original = battle.digest()
        self.assertEqual(battle.unit_levels[upstairs_id], 1)
        self.assertFalse(phalanx(battle, ground))
        broken = formation_preview(battle, ground_id)
        self.assertFalse(broken["formation_active"])
        self.assertEqual(
            broken["break_reason"], "adjacent_spear_partner_required_on_same_floor")
        self.assertEqual(broken["partners"], [])
        self.assertEqual(broken["level"], 0)
        self.assertEqual(battle.digest(), original)
        self.assertEqual(formation_control_map(battle, "player"), [])

        battle.execute({"kind": "level_move", "level": 1, "cell": [4, 5]})
        self.assertEqual(battle.unit_levels[ground_id], 1)
        self.assertTrue(phalanx(battle, ground))
        self.assertTrue(phalanx(battle, upstairs))
        formed = formation_preview(battle, ground_id)
        self.assertTrue(formed["formation_active"])
        self.assertEqual(formed["partners"], [upstairs_id])
        self.assertIsNone(formed["break_reason"])
        corridor = formation_control_map(battle, "player")
        self.assertEqual({row["level"] for row in corridor}, {1})
        self.assertEqual({row["unit"] for row in corridor}, {ground_id, upstairs_id})
        self.assertEqual(
            Battle.replay(battle.recording(), rules=tactical_rpg_rules()).digest(),
            battle.digest())

    def test_shield_wall_damage_requires_live_partner_on_same_floor(self):
        battle, ground_id, upstairs_id = floor_battle(formation="shield_wall")
        hero, guard = battle.unit(ground_id), battle.unit(upstairs_id)
        foe = battle.unit("hostile")
        skill = battle._basic(foe)
        self.assertFalse(shield_wall(battle, hero))
        exposed = battle.damage(foe, hero, skill, skill.effects[0])
        battle.execute({"kind": "level_move", "level": 1, "cell": [4, 5]})
        self.assertTrue(shield_wall(battle, hero))
        self.assertTrue(shield_wall(battle, guard))
        protected = battle.damage(foe, hero, skill, skill.effects[0])
        self.assertLess(protected, exposed)
        self.assertEqual(
            Battle.replay(battle.recording(), rules=tactical_rpg_rules()).digest(),
            battle.digest())

    def test_escort_rejects_other_floor_atomically_then_accepts_upstairs(self):
        battle, ground_id, upstairs_id = floor_battle()
        hero = battle.unit(ground_id)
        before = battle.digest()
        with self.assertRaises(RuleError):
            battle.execute({"kind": "formation", "mode": "escort",
                            "target": upstairs_id})
        self.assertEqual(battle.digest(), before)
        self.assertFalse(escorted(battle, battle.unit(upstairs_id)))
        battle.execute({"kind": "level_move", "level": 1, "cell": [4, 5]})
        battle.execute({"kind": "formation", "mode": "escort",
                        "target": upstairs_id})
        self.assertTrue(escorted(battle, battle.unit(upstairs_id)))
        view = formation_preview(battle, ground_id)
        self.assertTrue(view["providing_escort"])
        self.assertTrue(view["formation_active"])
        self.assertEqual(view["partners"], [upstairs_id])
        self.assertEqual(
            Battle.replay(battle.recording(), rules=tactical_rpg_rules()).digest(),
            battle.digest())


class ReactionFloorTests(unittest.TestCase):
    def test_upper_overwatch_hidden_below_but_triggers_on_stair_landing(self):
        battle, hero_id, watcher_id = floor_battle(allies=False)
        self.assertEqual(battle.active_id, watcher_id)
        before = battle.digest()
        self.assertEqual(battle.reaction_threats((4, 5), "player"), [])
        self.assertEqual(battle.digest(), before)
        battle.execute({"kind": "prepare", "mode": "overwatch"})
        battle.execute({"kind": "end"})
        self.assertEqual(battle.active_id, hero_id)
        self.assertEqual(battle.reaction_threats((4, 5), "player"), [])
        upper = battle.reaction_threats((4, 5), "player", level=1)
        self.assertEqual([row["unit"] for row in upper], [watcher_id])
        intents = tactical_intents(battle)
        self.assertEqual(intents["prepared"][0]["level"], 1)
        self.assertFalse(any(
            row["kind"] == "prepared" and row["unit"] == watcher_id
            for row in intents["danger"]))
        self.assertEqual(battle.digest(), battle.digest())

        battle.execute({"kind": "level_move", "level": 1, "cell": [4, 5]})
        self.assertTrue(any(e["kind"] == "prepared_triggered"
                            and e["unit"] == watcher_id and e["target"] == hero_id
                            for e in battle.events))
        self.assertEqual(
            Battle.replay(battle.recording(), rules=tactical_rpg_rules()).digest(),
            battle.digest())

    def test_reaction_query_ignores_expended_charges_and_invalid_floors(self):
        battle, hero_id, watcher_id = floor_battle(allies=False)
        battle.prepared_reactions[watcher_id] = {
            "mode": "overwatch", "charges": 0, "ct_tax": 20}
        original = battle.digest()
        self.assertEqual(battle.reaction_threats((4, 5), "player", level=1), [])
        for invalid in (-1, 4, 1.0, True):
            with self.subTest(invalid=invalid), self.assertRaises(RuleError):
                battle.reaction_threats((4, 5), "player", level=invalid)
        self.assertEqual(battle.digest(), original)


if __name__ == "__main__":
    unittest.main()

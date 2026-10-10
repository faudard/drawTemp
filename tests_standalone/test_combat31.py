"""Combat 3.1: position, visible threats and role-based squad decisions."""
from copy import deepcopy
import unittest

from sporebound.ai import choose_command
from sporebound.engine import Battle
from sporebound.model import Board, Content, Effect, Mission, Skill, Tile, Unit
from sporebound.presentation import battle_frame
from sporebound.spatial3 import facing_sector, positional_preview
from sporebound.tactical_actions import tactical_action_options, tactical_command
from sporebound.tactical_intents import tactical_intents
from sporebound.tactical_rpg3 import tactical_rpg_rules, authored_rules_for_document


def position_arena():
    warrior = Unit("warrior", "Warrior", "player", (4, 2),
                   attack=9, weapon_power=4, ct=100)
    defender = Unit("defender", "Defender", "enemy", (3, 2),
                    facing=(1, 0), hp=200, max_hp=200)
    return Content({}, {"arena": Mission("arena", "Arena", Board(8, 6),
                                         [warrior, defender])})


class PositionalMeleeTests(unittest.TestCase):
    def test_front_flank_rear_have_different_real_damage(self):
        battle = Battle(position_arena(), "arena", rules=tactical_rpg_rules())
        warrior, target = battle.unit("warrior"), battle.unit("defender")
        skill = battle._basic(warrior)
        front = battle.damage(warrior, target, skill, skill.effects[0])
        warrior.pos = (3, 1)
        flank = battle.damage(warrior, target, skill, skill.effects[0])
        warrior.pos = (2, 2)
        rear = battle.damage(warrior, target, skill, skill.effects[0])
        self.assertEqual([front, flank, rear], [36, 43, 50])
        self.assertEqual(facing_sector(warrior, target), "rear")
        self.assertEqual(positional_preview(battle, "warrior", "defender")["damage_percent"], 140)

    def test_forecast_execution_and_recording_match(self):
        rules = tactical_rpg_rules()
        battle = Battle(position_arena(), "arena", seed=42, rules=rules)
        expected = next(row["amount"] for row in battle.forecast("attack", (3, 2))
                        if row["kind"] == "damage")
        before = battle.unit("defender").hp
        battle.execute({"kind": "act", "skill": "attack", "cell": [3, 2]})
        self.assertEqual(before - battle.unit("defender").hp, expected)
        self.assertEqual(Battle.replay(battle.recording(), rules=rules).digest(),
                         battle.digest())

    def test_multicell_facing_uses_nearest_footprint_cell(self):
        attacker = Unit("a", "A", "player", (2, 4))
        large = Unit("large", "Large", "enemy", (2, 2), footprint=(2, 2),
                     facing=(0, 1))
        self.assertEqual(facing_sector(attacker, large), "front")
        attacker.pos = (4, 2)
        self.assertEqual(facing_sector(attacker, large), "flank")
        attacker.pos = (2, 1)
        self.assertEqual(facing_sector(attacker, large), "rear")

    def test_forecast_does_not_stack_exclusive_team_tactics(self):
        player = Unit("a", "A", "player", (2, 1), ct=100,
                      tactics=["chain_strike", "pincer"])
        partner = Unit("b", "B", "player", (2, 3), ct=100,
                       tactics=["chain_strike", "pincer"])
        target = Unit("foe", "Foe", "enemy", (2, 2), hp=200, max_hp=200)
        c = Content({}, {"m": Mission("m", "M", Board(6, 6),
                                      [player, partner, target])})
        rules = tactical_rpg_rules()
        battle = Battle(c, "m", rules=rules)
        before = battle.digest()
        options = battle.available_team_tactics(player, target)
        self.assertGreaterEqual(len(options), 2)
        expected = options[0]["id"]
        rows = battle.forecast("attack", target.pos)
        self.assertEqual({row["tactic"] for row in rows if row["kind"] == "tactic"},
                         {expected})
        self.assertEqual(battle.digest(), before)
        battle.execute({"kind": "act", "skill": "attack", "cell": [2, 2]})
        self.assertEqual(next(event["tactic"] for event in battle.events
                              if event["kind"] == "tactic"), expected)
        self.assertEqual(Battle.replay(battle.recording(), rules=rules).digest(),
                         battle.digest())


class VisibleIntentTests(unittest.TestCase):
    def test_cast_prepared_hazard_and_ct_projection_are_pure(self):
        caster = Unit("caster", "Caster", "enemy", (4, 2),
                      weapon="ranged", skills=["ember"], ct=70)
        hero = Unit("hero", "Hero", "player", (1, 2), ct=100)
        skill = Skill("ember", "Ember", [Effect("damage", 3)],
                      target="ground", range=6, radius=1, cast_ticks=3)
        c = Content({"ember": skill}, {"m": Mission("m", "M", Board(8, 6),
                                                    [hero, caster])})
        battle = Battle(c, "m", seed=8, rules=tactical_rpg_rules())
        battle.unit("caster").cast = {
            "skill": "ember", "cell": [2, 2], "remaining": 2, "unit": None}
        battle.prepared_reactions["caster"] = {
            "mode": "overwatch", "charges": 1, "ct_tax": 20}
        battle.board.tiles[(0, 0)] = Tile(hazard=5)
        original = battle.digest()
        view = tactical_intents(battle)
        self.assertEqual(original, battle.digest())
        self.assertEqual(view["timeline"][0]["unit"], "hero")
        self.assertEqual(view["casts"][0]["remaining_ticks"], 2)
        self.assertEqual(view["casts"][0]["certainty"], "scheduled")
        self.assertTrue(any(row["kind"] == "prepared" for row in view["danger"]))
        self.assertTrue(any(row["kind"] == "cast" for row in view["danger"]))
        self.assertTrue(any(row["kind"] == "hazard" for row in view["danger"]))
        frame = battle_frame(battle)
        self.assertEqual(frame.casts[0]["skill"], "ember")
        self.assertEqual(battle.digest(), original)

    def test_charge_corridor_is_possible_not_guaranteed(self):
        boss = Unit("boss", "Boss", "enemy", (1, 2),
                    behavior="phase_boss", tags=["boss_phase:2"])
        hero = Unit("hero", "Hero", "player", (5, 2))
        c = Content({}, {"m": Mission("m", "M", Board(8, 5), [hero, boss])})
        b = Battle(c, "m", rules=tactical_rpg_rules())
        before = b.digest()
        view = tactical_intents(b)
        self.assertTrue(view["charges"])
        self.assertEqual(view["charges"][0]["certainty"], "possible")
        self.assertEqual(b.digest(), before)


class SquadAITests(unittest.TestCase):
    def test_two_spears_prepare_phalanx_through_legal_commands(self):
        spear_a = Unit("spear_a", "A", "enemy", (2, 1), weapon="spear",
                       tags=["squad:pikeman"], behavior="coordinated", ct=100)
        spear_b = Unit("spear_b", "B", "enemy", (2, 2), weapon="spear",
                       tags=["squad:pikeman"], behavior="coordinated", ct=100)
        hero = Unit("hero", "Hero", "player", (6, 2))
        c = Content({}, {"m": Mission("m", "M", Board(8, 5),
                                      [spear_a, spear_b, hero])})
        rules = tactical_rpg_rules()
        b = Battle(c, "m", rules=rules)
        before = b.digest()
        self.assertEqual(choose_command(b),
                         {"kind": "formation", "mode": "phalanx"})
        self.assertEqual(b.digest(), before)
        b.execute(choose_command(b))
        b.execute({"kind": "end"})
        self.assertEqual(b.active_id, "spear_b")
        self.assertEqual(choose_command(b),
                         {"kind": "formation", "mode": "phalanx"})
        b.execute(choose_command(b))
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(),
                         b.digest())

    def test_officer_escorts_medic_and_role_is_authored(self):
        officer = Unit("officer", "Officer", "enemy", (3, 2), ct=100,
                       tags=["squad:officer"])
        medic = Unit("medic", "Medic", "enemy", (3, 3),
                     tags=["squad:medic"])
        hero = Unit("hero", "Hero", "player", (7, 3))
        c = Content({}, {"m": Mission("m", "M", Board(9, 6),
                                      [officer, medic, hero])})
        rules = authored_rules_for_document(c.to_dict())
        b = Battle(c, "m", rules=rules)
        self.assertEqual(choose_command(b),
                         {"kind": "formation", "mode": "escort", "target": "medic"})
        b.execute(choose_command(b))
        self.assertIn("formation:escort:medic", b.unit("officer").tags)
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(),
                         b.digest())

    def test_medic_with_no_heal_retreats_from_contact(self):
        medic = Unit("medic", "Medic", "enemy", (3, 2), ct=100,
                     tags=["squad:medic"])
        hero = Unit("hero", "Hero", "player", (2, 2))
        guard = Unit("guard", "Guard", "enemy", (4, 2),
                     tags=["squad:vanguard"])
        c = Content({}, {"m": Mission("m", "M", Board(7, 6),
                                      [medic, hero, guard])})
        b = Battle(c, "m", rules=tactical_rpg_rules())
        before = b.digest()
        cmd = choose_command(b)
        self.assertEqual(cmd["kind"], "move")
        self.assertGreater(abs(cmd["cell"][0] - 2) + abs(cmd["cell"][1] - 2), 1)
        self.assertEqual(before, b.digest())
        b.execute(cmd)
        self.assertEqual(Battle.replay(b.recording(),
                         rules=tactical_rpg_rules()).digest(), b.digest())


    def test_archer_seeks_a_shot_behind_vanguard(self):
        archer = Unit("archer", "Archer", "enemy", (0, 2), ct=100,
                      weapon="ranged", attack_range=3,
                      tags=["squad:archer"])
        guard = Unit("guard", "Guard", "enemy", (4, 2),
                     tags=["squad:vanguard"])
        hero = Unit("hero", "Hero", "player", (6, 2))
        c = Content({}, {"m": Mission("m", "M", Board(8, 5),
                                      [archer, guard, hero])})
        rules = tactical_rpg_rules()
        b = Battle(c, "m", rules=rules)
        before = b.digest()
        self.assertEqual(choose_command(b), {"kind": "move", "cell": [3, 2]})
        self.assertEqual(before, b.digest())
        b.execute(choose_command(b))
        self.assertEqual(b.unit("archer").pos, (3, 2))
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(),
                         b.digest())

    def test_pikeman_moves_to_screen_exposed_archer(self):
        spear = Unit("spear", "Spear", "enemy", (5, 3), ct=100,
                     weapon="spear", tags=["squad:pikeman"])
        archer = Unit("archer", "Archer", "enemy", (4, 2),
                      weapon="ranged", tags=["squad:archer"])
        hero = Unit("hero", "Hero", "player", (1, 2))
        c = Content({}, {"m": Mission("m", "M", Board(8, 5),
                                      [spear, archer, hero])})
        b = Battle(c, "m", rules=tactical_rpg_rules())
        command = choose_command(b)
        self.assertEqual(command["kind"], "move")
        self.assertEqual(sum(abs(a - b_) for a, b_ in zip(command["cell"], archer.pos)), 1)
        self.assertLess(sum(abs(a - b_) for a, b_ in zip(command["cell"], hero.pos)),
                        sum(abs(a - b_) for a, b_ in zip(archer.pos, hero.pos)))


class PlayerActionTests(unittest.TestCase):
    def test_formation_charge_and_preparation_are_reachable_from_player(self):
        player = Unit("spear", "Spear", "player", (1, 1), weapon="spear", ct=100)
        ally = Unit("ally", "Ally", "player", (1, 2), weapon="spear")
        enemy = Unit("enemy", "Enemy", "enemy", (5, 1))
        c = Content({}, {"m": Mission("m", "M", Board(8, 5),
                                      [player, ally, enemy])})
        rules = tactical_rpg_rules()
        b = Battle(c, "m", rules=rules)
        choices = tactical_action_options(b)
        self.assertIn("charge", choices)
        self.assertIn("formation:phalanx", choices)
        self.assertIn("prepare:guard", choices)
        before = b.digest()
        self.assertEqual(tactical_command("formation:phalanx", (0, 0)),
                         {"kind": "formation", "mode": "phalanx"})
        self.assertEqual(before, b.digest())
        b.execute(tactical_command("formation:phalanx", (0, 0)))
        self.assertNotIn("prepare:guard", tactical_action_options(b))
        self.assertEqual(Battle.replay(b.recording(), rules=rules).digest(),
                         b.digest())


if __name__ == "__main__":
    unittest.main()

"""3.1.7 combat morale: observable, consequential and replay-safe."""
import copy
import json
import unittest
from dataclasses import asdict

from sporebound.ai import choose_command
from sporebound.campaign import Campaign
from sporebound.engine import Battle
from sporebound.model import Board, Content, Mission, RuleError, Unit
from sporebound.morale31 import morale_snapshot
from sporebound.rules import default_rules
from sporebound.tactical_actions import tactical_action_options, tactical_command
from sporebound.tactical_intents import tactical_intents
from sporebound.tactical_rpg3 import tactical_rpg_rules


def arena(*units):
    content = Content({}, {"m": Mission("m", "Morale", Board(9, 6), list(units))})
    return Battle(content, "m", rules=tactical_rpg_rules(), seed=9)


class TacticalMoraleTests(unittest.TestCase):
    def test_rally_is_a_real_legal_action_and_deterministic_replay(self):
        captain = Unit("captain", "Captain", "enemy", (2, 2), ct=100,
                       tags=["bandit", "leader", "doctrine:bandit_ambush"])
        brigand = Unit("brigand", "Brigand", "enemy", (3, 2), hp=16, max_hp=40,
                       tags=["bandit", "doctrine:bandit_ambush"])
        hero = Unit("hero", "Hero", "player", (6, 2), hp=120, max_hp=120)
        b = arena(captain, brigand, hero)
        digest = b.digest()
        before = morale_snapshot(b, "brigand")
        self.assertEqual(before["state"], "shaken")
        self.assertEqual(choose_command(b), {"kind": "rally", "target": "brigand"})
        self.assertEqual(b.digest(), digest)  # AI and forecasts are pure
        b.execute(choose_command(b))
        self.assertTrue(b.unit("captain").acted)
        self.assertEqual(morale_snapshot(b, "brigand")["state"], "steady")
        self.assertTrue(any(e["kind"] == "morale_rally" for e in b.events))
        last = b.digest()
        with self.assertRaises(RuleError):
            b.execute({"kind": "rally", "target": "brigand"})
        self.assertEqual(b.digest(), last)
        self.assertEqual(Battle.replay(b.recording(), rules=tactical_rpg_rules()).digest(),
                         b.digest())

    def test_morale_is_pure_and_damage_changes_in_real_combat(self):
        hero = Unit("hero", "Hero", "player", (1, 1), ct=100, attack=8,
                    weapon_power=5, hp=20, max_hp=100, tags=["morale:shaken"])
        target = Unit("guard", "Guard", "enemy", (2, 1), hp=600, max_hp=600)
        low = arena(hero, target)
        initial = low.digest()
        state = morale_snapshot(low, "hero")
        self.assertEqual(state["state"], "routing")
        self.assertIn("critical_wound", state["reasons"])
        self.assertEqual(tactical_intents(low)["morale"][0]["state"], "routing")
        amount = next(r["amount"] for r in low.forecast("attack", (2, 1))
                      if r["kind"] == "damage")
        self.assertEqual(initial, low.digest())

        healthy = copy.deepcopy(hero)
        healthy.tags = []
        healthy.hp = healthy.max_hp
        standard = arena(healthy, target)
        baseline = next(r["amount"] for r in standard.forecast("attack", (2, 1))
                        if r["kind"] == "damage")
        self.assertLess(amount, baseline)
        before_hp = low.unit("guard").hp
        low.execute({"kind": "act", "skill": "attack", "cell": [2, 1]})
        self.assertEqual(before_hp - low.unit("guard").hp, amount)
        self.assertEqual(Battle.replay(low.recording(), rules=tactical_rpg_rules()).digest(),
                         low.digest())

    def test_bandit_surrenders_from_morale_without_hp_shortcut(self):
        brigand = Unit("bandit", "Bandit", "enemy", (2, 2), ct=100,
                       hp=40, max_hp=40,
                       tags=["bandit", "doctrine:bandit_ambush", "morale:routing"])
        h1 = Unit("h1", "Hero one", "player", (3, 2), hp=120, max_hp=120)
        h2 = Unit("h2", "Hero two", "player", (2, 3), hp=120, max_hp=120)
        b = arena(brigand, h1, h2)
        self.assertEqual(choose_command(b), {"kind": "surrender"})
        b.execute(choose_command(b))
        self.assertEqual(b.result, "victory")
        self.assertEqual(b.events[-1]["kind"], "battle_end")
        self.assertEqual(Battle.replay(b.recording(), rules=tactical_rpg_rules()).digest(),
                         b.digest())

    def test_crossbow_reload_creates_a_melee_damage_window(self):
        attacker = Unit("hero", "Hero", "player", (1, 1), ct=100,
                        weapon="melee", attack=10, weapon_power=5)
        bow = Unit("bow", "Arbaletrier", "enemy", (2, 1), hp=500, max_hp=500,
                   weapon="ranged", tags=["doctrine:crossbow_reload", "reload:empty"])
        exposed = arena(attacker, bow)
        vulnerable = next(row["amount"] for row in exposed.forecast("attack", (2, 1))
                          if row["kind"] == "damage")
        safe_bow = copy.deepcopy(bow)
        safe_bow.tags.remove("reload:empty")
        ready = arena(attacker, safe_bow)
        protected = next(row["amount"] for row in ready.forecast("attack", (2, 1))
                         if row["kind"] == "damage")
        self.assertGreater(vulnerable, protected)
        exposed.execute({"kind": "act", "skill": "attack", "cell": [2, 1]})
        self.assertEqual(exposed.unit("bow").hp, 500 - vulnerable)
        self.assertEqual(Battle.replay(exposed.recording(),
                         rules=tactical_rpg_rules()).digest(), exposed.digest())

    def test_rally_player_ui_and_campaign_morale_roundtrip(self):
        leader = Unit("jeanne", "Jeanne", "player", (1, 1), ct=100,
                      tags=["leader"])
        squire = Unit("squire", "Squire", "player", (2, 1),
                      max_hp=50, hp=20, tags=["morale:shaken"])
        foe = Unit("foe", "Foe", "enemy", (7, 2))
        battle = arena(leader, squire, foe)
        self.assertIn("rally:squire", tactical_action_options(battle))
        self.assertEqual(tactical_command("rally:squire", (0, 0)),
                         {"kind": "rally", "target": "squire"})
        battle.execute(tactical_command("rally:squire", (0, 0)))
        self.assertIn("morale:rallied", battle.unit("squire").tags)

        content = battle.content
        campaign = Campaign(unlocked=["m"])
        campaign.hero("squire").morale = "wavering"
        started = campaign.prepare(content, "m", ruleset=tactical_rpg_rules())
        self.assertIn("morale:wavering", started.unit("squire").tags)
        self.assertNotIn("morale:shaken", started.unit("squire").tags)
        self.assertEqual(campaign.hero("squire").morale, "wavering")
        payload = json.loads(json.dumps({"version": 1, **asdict(campaign)}))
        self.assertEqual(Campaign.from_dict(payload).hero("squire").morale,
                         "wavering")

    def test_old_rules_replay_is_rejected_not_silently_reinterpreted(self):
        player = Unit("p", "P", "player", (1, 1), ct=100)
        enemy = Unit("e", "E", "enemy", (3, 1))
        b = arena(player, enemy)
        recording = b.recording()
        self.assertEqual(recording["rules"]["formulas"]["damage"], "3.1.7-morale")
        incompatible = copy.deepcopy(recording)
        incompatible["rules"]["formulas"]["damage"] = "1"
        with self.assertRaisesRegex(RuleError, "Replay ruleset mismatch"):
            Battle.replay(incompatible, rules=tactical_rpg_rules())
        self.assertNotIn("rally", default_rules().commands)


if __name__ == "__main__":
    unittest.main()

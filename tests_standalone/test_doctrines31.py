"""Regression gates for the opt-in living medieval bestiary."""
import unittest

from sporebound.ai import choose_command
from sporebound.doctrines31 import DOCTRINES, doctrine
from sporebound.engine import Battle
from sporebound.model import Board, Content, Mission, RuleError, Unit
from sporebound.tactical_actions import tactical_action_options, tactical_command
from sporebound.tactical_intents import tactical_intents
from sporebound.tactical_rpg3 import tactical_rpg_rules


def fight(*units):
    model = Content({}, {"m": Mission("m", "M", Board(10, 8), list(units))})
    return Battle(model, "m", seed=4, rules=tactical_rpg_rules())


class DoctrineTests(unittest.TestCase):
    def test_four_distinct_behavior_decisions(self):
        wolf = Unit("wolf", "Wolf", "enemy", (1, 1), weapon="unarmed",
                    tags=["wolf", "doctrine:pack_hunt"], ct=100)
        victim = Unit("victim", "Victim", "player", (6, 1), max_hp=150, hp=150)
        pack = fight(wolf, victim)
        move = choose_command(pack)
        self.assertEqual(move["kind"], "move")
        self.assertLess(abs(move["cell"][0] - 6) + abs(move["cell"][1] - 1), 5)
        self.assertEqual(pack.digest(), pack.digest())

        bandit = Unit("bandit", "Bandit", "enemy", (1, 1), max_hp=40, hp=10,
                      tags=["bandit", "doctrine:bandit_ambush"], ct=100)
        bandits = fight(bandit, victim)
        self.assertEqual(choose_command(bandits), {"kind": "surrender"})
        bandits.execute(choose_command(bandits))
        self.assertEqual(bandits.result, "victory")  # enemy surrenders; player remains
        self.assertTrue(any(e["kind"] == "surrender" for e in bandits.events))
        self.assertEqual(Battle.replay(bandits.recording(), rules=tactical_rpg_rules()).digest(),
                         bandits.digest())

        spear = Unit("spear", "Spear", "enemy", (1, 1), weapon="spear",
                     attack_range=2, tags=["doctrine:spear_hold"], ct=100)
        distant = Unit("distant", "Distant", "player", (4, 1), max_hp=150, hp=150)
        line = fight(spear, distant)
        self.assertEqual(choose_command(line), {"kind": "prepare", "mode": "guard"})
        line.execute(choose_command(line))
        self.assertTrue(tactical_intents(line)["prepared"] or line.prepared_reactions)

        bow = Unit("bow", "Bow", "enemy", (1, 1), weapon="ranged",
                   attack_range=5, tags=["doctrine:crossbow_reload", "reload:empty"], ct=100)
        reload = fight(bow, distant)
        self.assertEqual(choose_command(reload), {"kind": "reload"})
        reload.execute(choose_command(reload))
        self.assertNotIn("reload:empty", reload.unit("bow").tags)
        self.assertEqual(Battle.replay(reload.recording(), rules=tactical_rpg_rules()).digest(),
                         reload.digest())

    def test_crossbow_shot_cannot_bypass_reload_and_replay_stable(self):
        bow = Unit("bow", "Arbalétrier", "player", (1, 1), weapon="ranged",
                   attack_range=5, tags=["doctrine:crossbow_reload"], ct=100)
        foe = Unit("foe", "Target", "enemy", (4, 1), max_hp=900, hp=900)
        b = fight(bow, foe)
        b.execute({"kind": "act", "skill": "attack", "cell": [4, 1]})
        self.assertIn("reload:empty", b.unit("bow").tags)
        before = b.digest()
        with self.assertRaisesRegex(RuleError, "rechargez"):
            b.execute({"kind": "act", "skill": "attack", "cell": [4, 1]})
        self.assertEqual(before, b.digest())
        b.execute({"kind": "end"})
        for _ in range(20):
            if b.active_id == "bow":
                break
            b.execute({"kind": "end"})
        self.assertEqual(b.active_id, "bow")
        self.assertIn("reload", tactical_action_options(b))
        self.assertEqual(tactical_command("reload", [0, 0]), {"kind": "reload"})
        b.execute({"kind": "reload"})
        self.assertNotIn("reload:empty", b.unit("bow").tags)
        self.assertEqual(Battle.replay(b.recording(), rules=tactical_rpg_rules()).digest(),
                         b.digest())

    def test_malformed_doctrine_is_inert_and_default_rules_stay_unchanged(self):
        from sporebound.rules import default_rules
        self.assertNotIn("reload", default_rules().commands)
        self.assertNotIn("surrender", default_rules().commands)
        self.assertEqual(doctrine(Unit("u", "U", "player", (1, 1))), "")
        self.assertEqual(set(DOCTRINES.values()),
                         {"pack_hunt", "bandit_ambush", "spear_hold", "crossbow_reload"})


if __name__ == "__main__":
    unittest.main()

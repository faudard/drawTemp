"""End-to-end living bestiary character, campaign, authoring and balance gates."""
import json
import unittest
from copy import deepcopy
from dataclasses import asdict

from sporebound.ai import choose_command
from sporebound.bestiary_studio4 import create_variant, edit_doctrine, place_variant
from sporebound.campaign import Campaign, HeroProgress
from sporebound.encounter_balance31 import analyze_three, replay_three
from sporebound.engine import Battle
from sporebound.model import Board, Content, Effect, Mission, RuleError, Skill, Unit
from sporebound.tactical_rpg3 import tactical_rpg_rules


def trilogy():
    jobs = {
        "brave": {"name": "Brave"},
        "reserve": {"name": "Réserve", "skills": {"strike": 1}},
    }
    missions = {}
    for n in range(1, 4):
        next_missions = [f"m{n+1}"] if n < 3 else []
        hero = Unit("jeanne", "Jeanne", "player", (1, 1),
                    max_hp=70, hp=70, attack=22, weapon_power=10,
                    speed=13, ct=100)
        foe = Unit(f"foe{n}", "Bandit", "enemy", (2, 1),
                   max_hp=26, hp=26, attack=4, speed=8)
        missions[f"m{n}"] = Mission(f"m{n}", "M", Board(8, 6),
                                   [hero, foe], next_missions=next_missions)
    skill = Skill("strike", "Frappe", [Effect("damage", 5)], target="enemy")
    return Content({"strike": skill}, missions, jobs=jobs,
                   archetypes={"template": {"kind": "character",
                                            "weapon": "melee", "max_hp": 40,
                                            "attack": 6, "skills": []}})


class GrowthAndPersistence(unittest.TestCase):
    def test_same_level_squires_have_distinct_tactical_builds(self):
        content = trilogy()
        campaign = Campaign(unlocked=["m1"])
        campaign.hero("jeanne").xp = 200
        campaign.hero("jeanne").job_xp["reserve"] = 50
        campaign.customize_hero(content, "jeanne", origin="soldier",
                                traits=["nimble"], secondary_job="reserve",
                                weapon_mastery={"melee": 3})
        trained = campaign.prepare(content, "m1", ruleset=tactical_rpg_rules()).unit("jeanne")
        self.assertIn("strike", trained.skills)
        self.assertEqual(trained.move, 5)
        self.assertEqual(trained.weapon_power, 13)
        other = Campaign(unlocked=["m1"])
        other.hero("jeanne").xp = 200
        other.customize_hero(content, "jeanne", origin="noble", traits=["steadfast"])
        guardian = other.prepare(content, "m1", ruleset=tactical_rpg_rules()).unit("jeanne")
        self.assertEqual(trained.id, guardian.id)
        self.assertNotEqual((trained.attack, trained.defense, trained.weapon_power),
                            (guardian.attack, guardian.defense, guardian.weapon_power))
        restored = Campaign.from_dict(json.loads(json.dumps({"version": 1,
                                                               **asdict(campaign)})))
        self.assertEqual(restored.hero("jeanne").origin, "soldier")
        self.assertEqual(restored.hero("jeanne").secondary_job, "reserve")

    def test_contribution_reward_is_bounded_and_once_only(self):
        content = trilogy()
        campaign = Campaign(unlocked=["m1"], reward_policy="contribution")
        battle = campaign.prepare(content, "m1", ruleset=tactical_rpg_rules())
        for _ in range(100):
            if battle.result:
                break
            battle.execute(choose_command(battle))
        self.assertEqual(battle.result, "victory")
        self.assertTrue(campaign.finish(battle))
        recorded_xp = campaign.hero("jeanne").xp
        self.assertGreater(recorded_xp, 75)
        self.assertLessEqual(recorded_xp, 125)
        self.assertEqual(campaign.reward_ledger["m1"]["jeanne"]["xp"], recorded_xp)
        self.assertFalse(campaign.finish(battle))
        self.assertEqual(recorded_xp, campaign.hero("jeanne").xp)

    def test_surrender_can_be_recruited_for_next_mission(self):
        content = trilogy()
        battle_content = deepcopy(content)
        bandit = battle_content.missions["m1"].units[1]
        bandit.tags = ["bandit", "doctrine:bandit_ambush"]
        bandit.hp = 8
        bandit.max_hp = 40
        bandit.ct = 100
        battle_content.missions["m1"].units[0].ct = 0
        campaign = Campaign(unlocked=["m1"], wound_policy="light")
        battle = campaign.prepare(battle_content, "m1", ruleset=tactical_rpg_rules())
        self.assertEqual(choose_command(battle), {"kind": "surrender"})
        battle.execute(choose_command(battle))
        self.assertEqual(battle.result, "victory")
        self.assertTrue(campaign.finish(battle))
        self.assertIn("foe1", campaign.prisoners)
        self.assertEqual(campaign.story_flags["surrender_count"], 1)
        self.assertEqual(campaign.recruit_prisoner("foe1"), "recruit_foe1")
        self.assertIn("recruit_foe1", [u.id for u in campaign.prepare(
            content, "m2", ruleset=tactical_rpg_rules()).units])
        data = json.loads(json.dumps({"version": 1, **asdict(campaign)}))
        loaded = Campaign.from_dict(data, ruleset=tactical_rpg_rules())
        self.assertIn("foe1", loaded.recruits)
        self.assertEqual(loaded.story_flags["prisoners_taken"], True)
        self.assertEqual(Battle.replay(battle.recording(), rules=tactical_rpg_rules()).digest(),
                         battle.digest())


class StudioAndBalance(unittest.TestCase):
    def test_variant_authoring_and_snapshot_isolation(self):
        original = trilogy().to_dict()
        created = create_variant(original, "template", "variant_squire",
                                 kind="character", doctrine="spear_hold")
        self.assertEqual(original["archetypes"].keys(), {"template"})
        self.assertIn("doctrine:spear_hold", created["archetypes"]["variant_squire"]["tags"])
        changed = edit_doctrine(created, "variant_squire", "bandit_ambush")
        self.assertIn("doctrine:bandit_ambush",
                      changed["archetypes"]["variant_squire"]["tags"])
        self.assertNotIn("doctrine:spear_hold",
                         changed["archetypes"]["variant_squire"]["tags"])
        placed = place_variant(changed, "m2", "variant_squire",
                               "custom", "Custom", "enemy", [5, 5])
        placed_model = Content.from_dict(placed, rules=tactical_rpg_rules())
        self.assertTrue(any(u.id == "custom" for u in placed_model.missions["m2"].units))
        self.assertNotEqual(created["missions"], placed["missions"])
        self.assertEqual(original["missions"], created["missions"])
        with self.assertRaises(RuleError):
            create_variant(created, "template", "variant_squire")

    def test_three_encounter_report_and_replay_resume(self):
        content = trilogy()
        report = analyze_three(content, ["m1", "m2", "m3"])
        self.assertEqual(len(report["encounters"]), 3)
        self.assertEqual([x["mission"] for x in report["encounters"]],
                         ["m1", "m2", "m3"])
        campaign = Campaign(unlocked=["m1"], reward_policy="contribution")
        result = replay_three(content, campaign, ["m1", "m2", "m3"], max_commands=200)
        self.assertTrue(result["all_victories"])
        self.assertTrue(all(row["resume_checked"] for row in result["encounters"]))
        self.assertEqual(result["campaign"].completed, ["m1", "m2", "m3"])
        self.assertEqual(campaign.completed, [])


if __name__ == "__main__":
    unittest.main()

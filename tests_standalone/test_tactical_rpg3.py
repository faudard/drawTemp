"""2.7 tactical vertical tests: gameplay, persistence, forecasts and legacy gates."""
from dataclasses import asdict
import unittest

from sporebound.ai import choose_command
from sporebound.balance3 import evaluate, percentile, verify_budgets
from sporebound.bosses3 import boss_preview
from sporebound.builds3 import talent_catalog
from sporebound.campaign import Campaign
from sporebound.engine import Battle
from sporebound.formations3 import formation_preview
from sporebound.model import Board, Content, Effect, Mission, RuleError, Skill, Unit
from sporebound.rules import default_rules
from sporebound.synergies3 import synergy_readiness
from sporebound.tactical_rpg3 import tactical_rpg_rules


def arena(*, coordinated=False):
    hero = Unit("hero", "Hero", "player", (0, 1), skills=["heal"])
    enemy = Unit("enemy", "Enemy", "enemy", (4, 1),
                 behavior="coordinated" if coordinated else "tactical")
    ally = Unit("ally", "Guard", "enemy", (4, 2), hp=10, max_hp=40)
    skills = {"heal": Skill("heal", "Heal", [Effect("heal", 20)],
                            target="ally", range=3)}
    return Content(skills, {"arena": Mission("arena", "Arena", Board(7, 5),
                                           [hero, enemy, ally])}, jobs={"brave": {}})


class RulesetTests(unittest.TestCase):
    def test_opt_in_keeps_old_manifest_identical(self):
        before = default_rules().manifest()
        rules = tactical_rpg_rules()
        self.assertEqual(default_rules().manifest(), before)
        self.assertNotEqual(rules.manifest(), before)
        for key in ("formation",):
            self.assertIn(key, rules.commands)
        for key in ("chain_strike", "trio_burst"):
            self.assertIn(key, rules.tactics)

    def test_coordinated_medic_chooses_legal_heal_and_is_pure(self):
        content = arena(coordinated=True)
        content.missions["arena"].units[1].tags = ["medic"]
        content.missions["arena"].units[1].skills = ["heal"]
        battle = Battle(content, "arena", seed=1, rules=tactical_rpg_rules())
        battle.active_id = "enemy"
        battle.unit("enemy").ct = 100
        before = battle.digest()
        cmd = choose_command(battle)
        self.assertEqual(cmd, {"kind": "act", "skill": "heal", "cell": [4, 2]})
        self.assertEqual(before, battle.digest())
        battle.execute(cmd)
        self.assertEqual(battle.unit("ally").hp, 30)


class FormationTests(unittest.TestCase):
    def setup_battle(self, tags=None):
        a = Unit("a", "A", "player", (1, 1), weapon="spear",
                 tags=list(tags or []))
        b = Unit("b", "B", "player", (1, 2), weapon="spear",
                 tags=list(tags or []))
        e = Unit("e", "E", "enemy", (2, 1), attack=12)
        c = Content({}, {"arena": Mission("arena", "Arena", Board(5, 5), [a, b, e])})
        return Battle(c, "arena", rules=tactical_rpg_rules(), seed=3)

    def test_shield_wall_and_phalanx_modify_real_damage(self):
        battle = self.setup_battle(["formation:shield_wall"])
        enemy, target = battle.unit("e"), battle.unit("a")
        skill = battle._basic(enemy)
        guarded = battle.damage(enemy, target, skill, skill.effects[0])
        battle.unit("b").tags = []
        exposed = battle.damage(enemy, target, skill, skill.effects[0])
        self.assertLess(guarded, exposed)
        battle = self.setup_battle(["formation:phalanx"])
        caster = battle.unit("a")
        skill = battle._basic(caster)
        linked = battle.damage(caster, battle.unit("e"), skill, skill.effects[0])
        battle.unit("b").tags = []
        unlinked = battle.damage(caster, battle.unit("e"), skill, skill.effects[0])
        self.assertGreater(linked, unlinked)

    def test_atomic_command_replay_and_escort_forecast(self):
        battle = self.setup_battle()
        before = battle.digest()
        with self.assertRaises(RuleError):
            battle.execute({"kind": "formation", "mode": "escort", "target": "ghost"})
        self.assertEqual(before, battle.digest())
        battle.execute({"kind": "formation", "mode": "escort", "target": "b"})
        self.assertTrue(formation_preview(battle, "b")["escort"])
        with self.assertRaises(RuleError):
            battle.execute({"kind": "formation", "mode": "none"})
        self.assertEqual(battle.digest(), Battle.replay(
            battle.recording(), rules=tactical_rpg_rules()).digest())


class TalentTests(unittest.TestCase):
    def content(self):
        content = arena()
        content.jobs["brave"]["talents"] = {
            "guard": {"jp": 1, "bonuses": {"defense": 3}},
            "warcry": {"jp": 2, "requires": ["guard"], "skills": ["heal"],
                       "exclusive": "style"},
            "trickster": {"jp": 1, "exclusive": "style"}}
        content.validate()
        return content

    def test_jp_unlocks_exclusivity_and_campaign_roundtrip(self):
        content = self.content()
        campaign = Campaign(["arena"])
        hero = campaign.hero("hero")
        hero.job_xp["brave"] = 150
        with self.assertRaises(RuleError):
            campaign.learn_talent(content, "hero", "brave", "warcry")
        self.assertEqual(hero.spent_jp, {})
        campaign.learn_talent(content, "hero", "brave", "guard")
        campaign.learn_talent(content, "hero", "brave", "warcry")
        self.assertEqual(talent_catalog(content, hero, "brave")["available_jp"], 0)
        with self.assertRaises(RuleError):
            campaign.learn_talent(content, "hero", "brave", "trickster")
        snap = {"version": 1, **asdict(campaign)}
        restored = Campaign.from_dict(snap)
        self.assertEqual(asdict(campaign), asdict(restored))
        battle = restored.prepare(content, "arena", ruleset=default_rules())
        self.assertEqual(battle.unit("hero").defense, 3)

    def test_cycle_is_rejected_before_any_purchase(self):
        content = self.content()
        content.jobs["brave"]["talents"]["guard"]["requires"] = ["warcry"]
        with self.assertRaises(RuleError):
            content.validate()


class SynergyTests(unittest.TestCase):
    def test_trio_tactic_is_forecast_and_replay_deterministic(self):
        team = [Unit("a", "A", "player", (2, 1), tactics=["trio_burst"]),
                Unit("b", "B", "player", (1, 2), tactics=["trio_burst"]),
                Unit("c", "C", "player", (3, 2), tactics=["trio_burst"])]
        foe = Unit("foe", "Foe", "enemy", (2, 2), hp=100, max_hp=100)
        content = Content({}, {"m": Mission("m", "M", Board(6, 5), [*team, foe])})
        rules = tactical_rpg_rules()
        battle = Battle(content, "m", rules=rules, seed=9)
        for u in team:
            battle.unit(u.id).ct = 100
        before = battle.digest()
        rows = synergy_readiness(battle, "a", "foe")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["members"], ["a", "b", "c"])
        self.assertEqual(battle.digest(), before)
        battle.execute({"kind": "act", "skill": "attack", "cell": [2, 2]})
        self.assertTrue(any(e["kind"] == "tactic" and e["tactic"] == "trio_burst"
                            for e in battle.events))
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())


class BossTests(unittest.TestCase):
    def test_phase_and_multicell_reinforcement_replay(self):
        hero = Unit("hero", "Hero", "player", (3, 2), skills=["smash"])
        boss = Unit("boss", "Warden", "enemy", (4, 2), max_hp=90, hp=90)
        skill = Skill("smash", "Smash", [Effect("damage", power=11)], range=1)
        mission = Mission("throne", "Throne", Board(8, 6), [hero, boss],
                          triggers=[{"id": "giant", "condition": "hp_below",
                                     "unit": "boss", "percent": 60,
                                     "actions": [{"kind": "boss_phase",
                                                  "unit": "boss", "phase": 2,
                                                  "form": "giant",
                                                  "footprint": [2, 2],
                                                  "bonuses": {"attack": 4}}]}])
        rules = tactical_rpg_rules()
        battle = Battle(Content({"smash": skill}, {"throne": mission}),
                        "throne", seed=2, rules=rules)
        self.assertEqual(boss_preview(battle, "boss")["phase"], 1)
        battle.execute({"kind": "act", "skill": "smash", "cell": [4, 2]})
        self.assertEqual(boss_preview(battle, "boss")["phase"], 2)
        self.assertEqual(battle.unit("boss").footprint, (2, 2))
        self.assertEqual(battle.unit("boss").attack, 9)
        self.assertEqual(battle.digest(), Battle.replay(
            battle.recording(), rules=rules).digest())


class CastleIntegrationTests(unittest.TestCase):
    def test_existing_siege_phase_upgrades_without_changing_original_fixture(self):
        from examples.siege_scenarios import siege_content
        from examples.tactical_rpg3_castle import advanced_castle_content

        original = siege_content()
        enhanced = advanced_castle_content()
        self.assertNotIn("boss_phase", [a["kind"] for a in
                         next(t for t in original.missions["castle_throne"].triggers
                              if t["id"] == "castellan_second_phase")["actions"]])
        rules = tactical_rpg_rules()
        battle = Battle(enhanced, "castle_throne", seed=42, rules=rules)
        battle.execute({"kind": "start_battle"})
        self.assertTrue(boss_preview(battle, "castellan")["pending"])
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())


class BalanceTests(unittest.TestCase):
    def test_seeded_metrics_percentiles_and_reproducibility(self):
        content = arena()
        report = evaluate(content, "arena", seeds=[1, 7, 42], max_commands=15)
        same = evaluate(content, "arena", seeds=[1, 7, 42], max_commands=15)
        self.assertEqual(report, same)
        self.assertEqual(report["runs"], 3)
        self.assertEqual(report["commands_p99"], percentile(
            [row["commands"] for row in report["samples"]], 99))
        self.assertTrue(verify_budgets(report, allow_limits=True,
                                       max_p95_commands=15))
        with self.assertRaises(RuleError):
            evaluate(content, "arena", seeds=[1, 1])
        with self.assertRaises(RuleError):
            verify_budgets(report, max_p95_commands=1, allow_limits=True)


if __name__ == "__main__":
    unittest.main()

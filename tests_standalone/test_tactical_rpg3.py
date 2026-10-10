"""2.7 tactical vertical tests: gameplay, persistence, forecasts and legacy gates."""
from copy import deepcopy
from dataclasses import asdict
import unittest

from sporebound.ai import choose_command
from sporebound.balance3 import compare_compositions, evaluate, percentile, verify_budgets
from sporebound.bosses3 import boss_preview, boss_intent_preview
from sporebound.builds3 import talent_catalog
from sporebound.campaign import Campaign
from sporebound.coordinated_ai import squad_focus_preview
from sporebound.engine import Battle
from sporebound.formations3 import formation_preview, formation_control_map
from sporebound.model import Board, Content, Effect, Mission, RuleError, Skill, Tile, Unit
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


    def test_coordinated_protector_moves_between_medic_and_enemy(self):
        hero = Unit("hero", "Hero", "player", (1, 2))
        medic = Unit("medic", "Medic", "enemy", (4, 2), tags=["medic"])
        guard = Unit("guard", "Guard", "enemy", (5, 3),
                     behavior="coordinated", tags=["protector"])
        content = Content({}, {"m": Mission("m", "M", Board(7, 5),
                                            [hero, medic, guard])})
        battle = Battle(content, "m", rules=tactical_rpg_rules(), seed=4)
        battle.active_id = "guard"
        battle.unit("guard").ct = 100
        before = battle.digest()
        cmd = choose_command(battle)
        self.assertEqual(cmd, {"kind": "move", "cell": [3, 2]})
        self.assertEqual(battle.digest(), before)
        battle.execute(cmd)
        self.assertEqual(battle.unit("guard").pos, (3, 2))


    def test_coordinated_focus_fire_prioritizes_supported_target(self):
        leader = Unit("leader", "Leader", "enemy", (2, 2),
                      behavior="coordinated", move=0)
        wing = Unit("wing", "Wing", "enemy", (4, 2))
        fragile = Unit("fragile", "Fragile", "player", (2, 3),
                       hp=1, max_hp=40)
        brute = Unit("brute", "Brute", "player", (3, 2))
        content = Content({}, {"m": Mission("m", "M", Board(7, 5),
                                            [leader, wing, fragile, brute])})
        rules = tactical_rpg_rules()
        battle = Battle(content, "m", seed=19, rules=rules)
        battle.active_id = "leader"
        battle.unit("leader").ct = 100
        original = battle.digest()
        preview = squad_focus_preview(battle)
        self.assertEqual(preview[0]["target"], "fragile")
        supported = next(p for p in preview if p["target"] == "brute")
        self.assertEqual(supported["supporters"], ["wing"])
        self.assertEqual(original, battle.digest())
        command = choose_command(battle)
        self.assertEqual(command,
                         {"kind": "act", "skill": "attack", "cell": [3, 2]})
        self.assertEqual(original, battle.digest())
        battle.execute(command)
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())

    def test_focus_fire_never_overrides_unsupported_basic_attack(self):
        leader = Unit("leader", "Leader", "enemy", (2, 2),
                      behavior="coordinated", move=0)
        wing = Unit("wing", "Wing", "enemy", (5, 4))
        fragile = Unit("fragile", "Fragile", "player", (2, 3),
                       hp=1, max_hp=40)
        brute = Unit("brute", "Brute", "player", (3, 2))
        content = Content({}, {"m": Mission("m", "M", Board(7, 5),
                                            [leader, wing, fragile, brute])})
        battle = Battle(content, "m", seed=19, rules=tactical_rpg_rules())
        battle.active_id = "leader"
        battle.unit("leader").ct = 100
        battle.unit("wing").acted = True
        before = battle.digest()
        command = choose_command(battle)
        self.assertEqual(command,
                         {"kind": "act", "skill": "attack", "cell": [2, 3]})
        self.assertEqual(battle.digest(), before)


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

    def test_terrain_affects_formation_damage_and_preview(self):
        battle = self.setup_battle(["formation:shield_wall"])
        enemy, shield = battle.unit("e"), battle.unit("a")
        skill = battle._basic(enemy)
        bare = battle.damage(enemy, shield, skill, skill.effects[0])
        battle.board.tiles[(1, 1)] = Tile(cover=30)
        fortified = battle.damage(enemy, shield, skill, skill.effects[0])
        view = formation_preview(battle, "a")
        self.assertTrue(view["fortified"])
        self.assertEqual(view["terrain_cover"], 30)
        self.assertLess(fortified, bare)

        battle = self.setup_battle(["formation:phalanx"])
        spear, enemy = battle.unit("a"), battle.unit("e")
        skill = battle._basic(spear)
        level = battle.damage(spear, enemy, skill, skill.effects[0])
        battle.board.tiles[(1, 1)] = Tile(height=3)
        hill = battle.damage(spear, enemy, skill, skill.effects[0])
        self.assertGreater(hill, level)
        self.assertEqual(formation_preview(battle, "a")["elevation"], 3)

    def test_phalanx_hold_contested_corridor_and_replay(self):
        a = Unit("a", "Spear A", "player", (2, 1), weapon="spear",
                 tags=["formation:phalanx"])
        b = Unit("b", "Spear B", "player", (2, 2), weapon="spear",
                 tags=["formation:phalanx"])
        e = Unit("e", "Raider", "enemy", (5, 1))
        c = Content({}, {"m": Mission("m", "M", Board(7, 5), [a, b, e])})
        rules = tactical_rpg_rules()
        battle = Battle(c, "m", seed=3, rules=rules)
        original = battle.digest()
        self.assertEqual(formation_control_map(battle, "player")[0]["armed"], False)
        self.assertEqual(original, battle.digest())
        battle.execute({"kind": "prepare", "mode": "phalanx_hold"})
        self.assertEqual(formation_control_map(battle, "player")[0]["armed"], True)
        self.assertEqual(
            [row["unit"] for row in battle.reaction_threats((3, 1), "enemy")],
            ["a"])
        battle.execute({"kind": "end"})
        battle.execute({"kind": "end"})
        before = battle.unit("e").hp
        battle.execute({"kind": "move", "cell": [3, 1]})
        self.assertLess(battle.unit("e").hp, before)
        self.assertTrue(any(ev["kind"] == "prepared_triggered"
                            and ev["mode"] == "phalanx_hold"
                            for ev in battle.events))
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())

    def test_phalanx_hold_without_partner_rejected_atomically(self):
        battle = self.setup_battle()
        original = battle.digest()
        with self.assertRaises(RuleError):
            battle.execute({"kind": "prepare", "mode": "phalanx_hold"})
        self.assertEqual(battle.digest(), original)

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

    def test_old_campaign_slots_and_default_battle_replays_still_load(self):
        old = Campaign(["arena"])
        old.hero("hero").xp = 100
        snap = {"version": 1, **asdict(old)}
        del snap["heroes"]["hero"]["spent_jp"]
        del snap["heroes"]["hero"]["learned_talents"]
        self.assertEqual(Campaign.from_dict(snap).hero("hero").spent_jp, {})
        snap["heroes"]["hero"]["learned_talents"] = {"brave": [{}]}
        with self.assertRaises(RuleError):
            Campaign.from_dict(snap)
        battle = Battle(arena(), "arena", seed=4)
        battle.execute({"kind": "end"})
        self.assertEqual(Battle.replay(battle.recording()).digest(), battle.digest())

    def test_advanced_rules_survive_game_session_save_and_resume(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from sporebound.__main__ import DEFAULT_CONTENT
        from sporebound.game_project import GameProject
        from sporebound.game_session import GameSession

        content = Content.load(DEFAULT_CONTENT)
        project = GameProject.load(
            Path(DEFAULT_CONTENT).with_suffix(".game.json"), content)
        rules = tactical_rpg_rules()
        session = GameSession.new(content, project, "main", seed=17, rules=rules)
        session.start_mission("garden")
        session.execute({"kind": "formation", "mode": "shield_wall"})
        with TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            session.save(path)
            resumed = GameSession.load(path, content, project, rules=rules)
            self.assertEqual(resumed.recording(), session.recording())
            self.assertEqual(resumed.battle.digest(), session.battle.digest())

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


class BossBehaviorTests(unittest.TestCase):
    def test_second_phase_charge_is_legal_and_replayable(self):
        hero = Unit("hero", "Hero", "player", (5, 2))
        boss = Unit("boss", "Boss", "enemy", (1, 2), speed=20,
                    behavior="phase_boss", tags=["boss_phase:2"])
        content = Content({}, {"m": Mission("m", "M", Board(8, 5), [hero, boss])})
        rules = tactical_rpg_rules()
        battle = Battle(content, "m", seed=2, rules=rules)
        before = battle.digest()
        cmd = choose_command(battle)
        self.assertEqual(cmd, {"kind": "charge", "cell": [5, 2]})
        intent = boss_intent_preview(battle, "boss")
        self.assertTrue(intent["ready"])
        self.assertEqual(intent["phase"], 2)
        self.assertEqual(intent["command"], cmd)
        self.assertIsInstance(intent["threats"], list)
        self.assertEqual(battle.digest(), before)
        battle.execute(cmd)
        self.assertFalse(boss_intent_preview(battle, "boss")["ready"])
        self.assertTrue(any(event["kind"] == "charge" for event in battle.events))
        self.assertEqual(battle.digest(), Battle.replay(
            battle.recording(), rules=rules).digest())


class BalanceTests(unittest.TestCase):
    def test_paired_seed_composition_delta_and_nonmutation(self):
        basic = arena()
        variant = deepcopy(basic)
        variant.missions["arena"].units[0].attack += 4
        origin = basic.to_dict()
        changed = variant.to_dict()
        inputs = {"veteran": variant, "novice": basic}
        report = compare_compositions(inputs, "arena", baseline="novice",
                                      seeds=(4, 9), max_commands=12)
        again = compare_compositions(inputs, "arena", baseline="novice",
                                     seeds=(4, 9), max_commands=12)
        self.assertEqual(report, again)
        self.assertEqual([row["name"] for row in report["compositions"]],
                         ["novice", "veteran"])
        self.assertEqual(report["compositions"][0]["victory_rate_delta"], 0)
        self.assertEqual(report["compositions"][0]["damage_taken_delta"], 0)
        self.assertEqual(basic.to_dict(), origin)
        self.assertEqual(variant.to_dict(), changed)
        with self.assertRaises(RuleError):
            compare_compositions(inputs, "arena", baseline="missing", seeds=(4,))

    def test_seeded_metrics_percentiles_and_reproducibility(self):
        content = arena()
        report = evaluate(content, "arena", seeds=[1, 7, 42], max_commands=15)
        same = evaluate(content, "arena", seeds=[1, 7, 42], max_commands=15)
        self.assertEqual(report, same)
        self.assertEqual(report["runs"], 3)
        self.assertEqual(len({row["digest"] for row in report["samples"]}),
                         len(set(row["digest"] for row in report["samples"])))
        self.assertEqual(report["telemetry"]["events"].get("activation", 0),
                         sum(row["events"].get("activation", 0)
                             for row in report["samples"]))
        self.assertEqual(report["telemetry"]["tactics"].get("pincer", 0),
                         sum(row["tactics"].get("pincer", 0)
                             for row in report["samples"]))
        self.assertEqual(report["damage_taken_mean"],
                         round(sum(row["damage_taken"] for row in report["samples"]) / 3, 3))
        self.assertEqual(report["commands_p99"], percentile(
            [row["commands"] for row in report["samples"]], 99))
        self.assertTrue(verify_budgets(report, allow_limits=True,
                                       max_p95_commands=15))
        with self.assertRaises(RuleError):
            verify_budgets(report, max_mean_damage_taken=-1, allow_limits=True)
        self.assertTrue(verify_budgets(report,
            max_mean_damage_taken=report["damage_taken_mean"],
            allow_limits=True))
        with self.assertRaises(RuleError):
            evaluate(content, "arena", seeds=[1, 1])
        with self.assertRaises(RuleError):
            verify_budgets(report, max_p95_commands=1, allow_limits=True)


if __name__ == "__main__":
    unittest.main()

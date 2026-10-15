"""R6 regression gates: advanced victory conditions, AI plans and build UX."""
from copy import deepcopy
from dataclasses import asdict
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sporebound.ai import choose_command
from sporebound.campaign import Campaign
from sporebound.engine import Battle
from sporebound.game_project import GameProject
from sporebound.player_session import PlayerSession
from sporebound.model import Board, Content, Mission, RuleError, Tile, Unit
from sporebound.rules import default_rules
from sporebound.tactical_r6 import (
    ADVANCED_OBJECTIVES, active_enemy_plan, objective_progress,
    party_build_preview, squad_coordination, tactical_r6_rules,
)
from sporebound.tactical_rpg3 import authored_rules_for_document, tactical_rpg_rules
from sporebound.tactical_ui import tactical_snapshot


def fixture(objective="eliminate", *, goal=None, protected="", objects=None):
    hero = Unit("hero", "Hero", "player", (0, 1))
    enemy = Unit("enemy", "Enemy", "enemy", (5, 4),
                 behavior="coordinated", tags=["squad:vanguard"])
    mission = Mission("arena", "Arena", Board(7, 6), [hero, enemy],
                      objective=objective, goal=goal or [],
                      protected_id=protected, objects=objects or [])
    return Content({}, {"arena": mission}, jobs={"brave": {}})


class ObjectiveTests(unittest.TestCase):
    def test_registry_is_explicit_and_legacy_is_unchanged(self):
        before = default_rules().manifest()
        enhanced = tactical_r6_rules()
        self.assertEqual(default_rules().manifest(), before)
        self.assertNotIn("capture", tactical_rpg_rules().objectives)
        self.assertNotIn("capture", default_rules().objectives)
        self.assertTrue(ADVANCED_OBJECTIVES <= set(enhanced.objectives.manifest()))
        with self.assertRaises(RuleError):
            Battle(fixture("capture", goal=[(1, 1)]), "arena")

    def test_capture_is_multizone_contested_and_replayable(self):
        content = fixture("capture", goal=[(1, 1), (2, 1)])
        rules = tactical_r6_rules()
        battle = Battle(content, "arena", seed=4, rules=rules)
        self.assertFalse(objective_progress(battle)["achieved"])
        battle.execute({"kind": "move", "cell": [1, 1]})
        self.assertIsNone(battle.result)
        self.assertFalse(objective_progress(battle)["achieved"])
        # A second allied occupant must control the remaining zone.
        battle.unit("enemy").team = "player"
        battle.unit("enemy").pos = (2, 1)
        self.assertTrue(rules.objectives.get("capture").achieved(battle))
        battle.unit("enemy").team = "enemy"
        battle.unit("enemy").pos = (5, 4)
        self.assertFalse(rules.objectives.get("capture").achieved(battle))
        self.assertEqual(battle.digest(), Battle.replay(
            battle.recording(), rules=rules).digest())

    def test_capture_single_zone_ends_via_actual_command(self):
        rules = tactical_r6_rules()
        content = fixture("capture", goal=[(1, 1)])
        battle = Battle(content, "arena", seed=5, rules=rules)
        battle.execute({"kind": "move", "cell": [1, 1]})
        self.assertEqual(battle.result, "victory")
        self.assertEqual(battle.digest(), Battle.replay(
            battle.recording(), rules=rules).digest())

    def test_escort_defend_retreat_and_validation(self):
        rules = tactical_r6_rules()
        with self.assertRaises(RuleError):
            Battle(fixture("escort", goal=[(1, 1)]), "arena", rules=rules)
        escort = Battle(fixture("escort", goal=[(1, 1)], protected="hero"),
                        "arena", rules=rules)
        self.assertFalse(rules.objectives.get("escort").achieved(escort))
        escort.unit("hero").pos = (1, 1)
        self.assertTrue(rules.objectives.get("escort").achieved(escort))

        defend = Battle(fixture("defend", protected="hero"), "arena", rules=rules)
        self.assertFalse(rules.objectives.get("defend").achieved(defend))
        defend.tick = defend.mission.target_ticks
        self.assertTrue(rules.objectives.get("defend").achieved(defend))
        defend.unit("hero").hp = 0
        self.assertFalse(rules.objectives.get("defend").achieved(defend))

        retreat = Battle(fixture("retreat", goal=[(1, 1)]), "arena", rules=rules)
        self.assertFalse(rules.objectives.get("retreat").achieved(retreat))
        retreat.unit("hero").pos = (1, 1)
        self.assertTrue(rules.objectives.get("retreat").achieved(retreat))

    def test_sabotage_enemy_defense_via_interact_and_replay(self):
        defense = {"id": "tower", "kind": "defense", "team": "enemy",
                   "pos": [1, 1], "cells": [[0, 1]],
                   "charges": 2, "disabled": False}
        rules = tactical_r6_rules()
        with self.assertRaises(RuleError):
            Battle(fixture("sabotage"), "arena", rules=rules)
        content = fixture("sabotage", objects=[defense])
        battle = Battle(content, "arena", rules=rules, seed=7)
        self.assertFalse(objective_progress(battle)["achieved"])
        battle.execute({"kind": "interact", "object": "tower"})
        self.assertEqual(battle.result, "victory")
        self.assertTrue(objective_progress(battle)["defenses"][0]["disabled"])
        self.assertEqual(battle.digest(), Battle.replay(
            battle.recording(), rules=rules).digest())

    def test_player_campaign_uses_r6_rules_and_party_view(self):
        content = fixture("capture", goal=[(1, 1)])
        project = GameProject.default(content)
        with TemporaryDirectory() as folder:
            session = PlayerSession(content, project, Path(folder) / "saves.json")
            session.new_game("main", 1)
            preview = session.party_build_preview("arena")
            self.assertEqual(preview["party_size"], 1)
            self.assertIsNone(session.battle)
            battle = session.begin("arena")
            self.assertIn("capture", battle.rules.objectives)
            session.command({"kind": "move", "cell": [1, 1]})
            self.assertEqual(battle.result, "victory")
            self.assertTrue(session.finalized)

    def test_authored_missions_select_enhanced_objective_rules(self):
        content = fixture("escort", goal=[(1, 1)], protected="hero")
        rules = authored_rules_for_document(content.to_dict())
        self.assertIn("escort", rules.objectives)
        self.assertNotIn("escort", default_rules().objectives)


class IntelligenceTests(unittest.TestCase):
    def test_plan_and_metrics_are_pure_and_conditional(self):
        battle = Battle(fixture("capture", goal=[(6, 4)]), "arena",
                        rules=tactical_r6_rules(), seed=8)
        battle.active_id = "enemy"
        battle.unit("enemy").ct = 100
        before = battle.digest()
        plan = active_enemy_plan(battle)
        self.assertEqual(plan["unit"], "enemy")
        self.assertEqual(plan["horizon"], "current_activation")
        self.assertEqual(plan["certainty"], "conditional")
        view = tactical_snapshot(battle)
        self.assertEqual(view["enemy_plan"], plan)
        self.assertEqual(view["objective"]["kind"], "capture")
        self.assertEqual(view["coordination"], squad_coordination(battle))
        self.assertEqual(before, battle.digest())
        self.assertEqual(plan, active_enemy_plan(battle))

        battle.active_id = "hero"
        self.assertIsNone(active_enemy_plan(battle))
        self.assertEqual(tactical_snapshot(battle)["enemy_plan"], None)

    def test_objective_changes_coordinated_move_decision(self):
        def decision(objective):
            content = fixture(objective, goal=[(6, 4)] if objective == "capture" else [])
            content.missions["arena"].units[0].pos = (0, 2)
            content.missions["arena"].units[1].pos = (3, 2)
            battle = Battle(content, "arena", rules=tactical_r6_rules())
            battle.active_id = "enemy"
            battle.unit("enemy").ct = 100
            before = battle.digest()
            command = choose_command(battle)
            self.assertEqual(battle.digest(), before)
            return command
        baseline = decision("eliminate")
        goal = decision("capture")
        self.assertEqual(goal["kind"], "move")
        self.assertGreater(goal["cell"][0], 3)
        self.assertNotEqual(goal, baseline)

    def test_archer_chooses_safe_higher_cover_before_flat_tile(self):
        archer = Unit("archer", "Archer", "enemy", (1, 1),
                      weapon="ranged", attack_range=3, min_range=2,
                      jump=1, move=2, behavior="coordinated",
                      tags=["squad:archer"])
        hero = Unit("hero", "Hero", "player", (5, 1), move=0)
        board = Board(7, 4, {(2, 1): Tile(height=1, cover=40)})
        content = Content({}, {"v": Mission("v", "V", board, [archer, hero])})
        battle = Battle(content, "v", seed=11, rules=tactical_r6_rules())
        battle.active_id = "archer"
        battle.unit("archer").ct = 100
        before = battle.digest()
        command = choose_command(battle)
        self.assertEqual(command, {"kind": "move", "cell": [2, 1]})
        self.assertEqual(battle.digest(), before)
        battle.execute(command)
        self.assertEqual(battle.unit("archer").pos, (2, 1))

    def test_ground_medic_cannot_heal_ally_on_other_floor(self):
        from sporebound.coordinated_ai import _healing_command
        from sporebound.model import Effect, Skill
        medic = Unit("medic", "Medic", "enemy", (2, 2),
                     skills=["heal"], tags=["squad:medic"],
                     behavior="coordinated")
        ally = Unit("ally", "Ally", "enemy", (2, 3),
                    hp=5, max_hp=40)
        hero = Unit("hero", "Hero", "player", (5, 4))
        heal = Skill("heal", "Heal", [Effect("heal", 20)],
                     target="ally", range=3)
        content = Content({"heal": heal}, {
            "v": Mission("v", "V", Board(7, 6), [medic, ally, hero])})
        battle = Battle(content, "v", rules=tactical_r6_rules())
        self.assertEqual(_healing_command(battle, battle.unit("medic")),
                         {"kind": "act", "skill": "heal", "cell": [2, 3]})
        battle.unit_levels["ally"] = 1
        before = battle.digest()
        self.assertIsNone(_healing_command(battle, battle.unit("medic")))
        self.assertEqual(before, battle.digest())

    def test_upper_floor_squad_uses_existing_layered_policy(self):
        from sporebound.ai import _choose_tactical_command
        from tests_standalone.test_tactical_levels_3720c import TacticalFloorTests
        floors = TacticalFloorTests()
        floors.setUp()
        # The ordinary floor fixture uses the legacy ruleset, which deliberately
        # has no coordinated behavior. Install R6 rules for this AI test.
        battle = Battle(Content.from_dict(floors.doc.data), floors.MID,
                        seed=7, rules=tactical_r6_rules())
        boss = battle.unit(floors.enemy)
        boss.behavior = "coordinated"
        boss.tags = ["squad:archer", "squad:medic"]
        battle.active_id = boss.id
        boss.ct = 100
        before = battle.digest()
        self.assertEqual(choose_command(battle), _choose_tactical_command(battle))
        self.assertEqual(before, battle.digest())

    def test_active_formation_changes_real_ai_choice(self):
        def command(with_partner):
            content = fixture()
            actor = content.missions["arena"].units[1]
            actor.weapon = "spear"
            actor.tags = ["squad:pikeman"]
            actor.pos = (4, 3)
            if with_partner:
                content.missions["arena"].units.append(
                    Unit("wing", "Wing", "enemy", (4, 4), weapon="spear"))
            battle = Battle(content, "arena", rules=tactical_r6_rules())
            battle.active_id = "enemy"
            battle.unit("enemy").ct = 100
            return choose_command(battle)
        self.assertEqual(command(True), {"kind": "formation", "mode": "phalanx"})
        self.assertNotEqual(command(False), command(True))


class BuildsTests(unittest.TestCase):
    def test_prepared_builds_use_actual_campaign_math_without_mutating_campaign(self):
        content = fixture()
        content.jobs["brave"] = {
            "bonuses": {"defense": 2},
            "talents": {"fortify": {"jp": 1, "bonuses": {"defense": 4}}}}
        content.equipment["helm"] = {"slot": "armor", "bonuses": {"defense": 3}}
        campaign = Campaign(unlocked=["arena"])
        hero = campaign.hero("hero")
        hero.job_xp["brave"] = 100
        hero.learned_talents["brave"] = ["fortify"]
        hero.spent_jp["brave"] = 1
        hero.equipment["armor"] = "helm"
        before = deepcopy(campaign)
        view = party_build_preview(content, campaign, "arena",
                                   ruleset=tactical_rpg_rules())
        self.assertEqual(view["party_size"], 1)
        self.assertEqual(view["heroes"][0]["unit"], "hero")
        self.assertGreaterEqual(view["heroes"][0]["stats"]["defense"], 9)
        self.assertEqual(view["heroes"][0]["talents"]["available_jp"], 1)
        self.assertEqual(asdict(campaign), asdict(before))


if __name__ == "__main__":
    unittest.main()

"""R50.B: R26 action combat inside canonical GameSession + Studio Player slot."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.r50b_action import (
    ActionJourneyError, SCENE, ENEMY, author_action_prototype,
    check_action_player_journey,
)
from drawtemp.studio.r50b_catalog import CatalogError, catalog, create_starter
from sporebound.action_runtime import ActionError
from sporebound.action_scene_adapter import EXTENSION
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController
from sporebound.tactical_rpg3 import authored_rules_for_document


class R50BActionCombatTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def _pair(self, content_path):
        pair = AuthoringSession.open(content_path).snapshot().to_dict()
        data = pair["content"]
        content = Content.from_dict(
            data, rules=authored_rules_for_document(data))
        project = GameProject.from_dict(pair["project"], content)
        return content, project

    def test_authored_action_project_is_canonical_and_mode_pinned(self):
        path = author_action_prototype(self.root / "action")
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()),
                         ["game.game.json", "game.json"])
        content, project = self._pair(path)
        self.assertIn(EXTENSION, project.extensions)
        self.assertEqual(project.scene_routes["start"], SCENE)
        self.assertEqual(project.game_modes["scenes"][SCENE]["preset"], "action")
        self.assertEqual(project.game_modes["default"]["preset"], "srpg")
        self.assertEqual(project.extensions[EXTENSION]["data"]["scenes"][SCENE]
                         ["enemies"][0]["id"], ENEMY)
        self.assertFalse(AuthoringSession.open(path).snapshot().dirty)
        self.assertEqual(project.to_dict()["version"], 1)

    def test_player_r26_combat_replays_in_one_gamesession_save(self):
        path = author_action_prototype(self.root / "action")
        result = check_action_player_journey(path)
        self.assertTrue(result["enemy_defeated"])
        self.assertEqual(result["action_combat_ticks"], 13)
        self.assertTrue(result["player_save_resume"])
        self.assertTrue(result["same_gamesession_checkpoint"])
        self.assertTrue(result["replay_verified"])
        self.assertTrue(result["campaign_loot_integrated"])
        self.assertTrue(result["once_only_action_reward"])
        self.assertTrue(result["r26_to_ct_to_exploration"])
        self.assertFalse(result["qt_onscreen_verified"])
        self.assertFalse(result["release_9_0_certified"])

    def test_catalog_creates_new_headless_combat_without_unlocking_action_game(self):
        entries = {row["id"]: row for row in catalog()["entries"]}
        self.assertTrue(entries["action_combat_prototype"]["can_create"])
        self.assertFalse(entries["action_adventure"]["can_create"])
        output = self.root / "arena"
        report = create_starter("action_combat_prototype", output)
        self.assertEqual(report["status"], "headless-pass")
        self.assertTrue(report["proof"]["r26_action"]["enemy_defeated"])
        self.assertFalse(report["proof"]["native_player_tested"])
        self.assertFalse(report["release_9_0_ready"])
        self.assertEqual(sorted(p.name for p in output.iterdir()),
                         ["game.game.json", "game.json"])
        with self.assertRaises(CatalogError):
            create_starter("action_combat_prototype", output)

    def test_project_validation_fails_closed_for_bad_scene_and_mode(self):
        path = author_action_prototype(self.root / "action")
        content, project = self._pair(path)
        for corrupt in (
                lambda doc: doc.extensions[EXTENSION]["data"]["scenes"][SCENE]
                ["walls"].append([0, 0]),
                lambda doc: doc.extensions[EXTENSION]["data"]["scenes"][SCENE]
                ["enemies"][0].update(id=""),
                lambda doc: doc.extensions[EXTENSION]["data"].update(version=2),
                lambda doc: doc.game_modes["scenes"][SCENE].update(preset="srpg"),
                lambda doc: doc.scene_routes.clear(),
                lambda doc: doc.extensions[EXTENSION]["data"]["scenes"][SCENE]
                ["hero"].update(pos=[1, 1]),
        ):
            candidate = deepcopy(project)
            corrupt(candidate)
            with self.subTest(mode=candidate.game_modes), self.assertRaises(RuleError):
                candidate.validate(content)

    def test_replay_tamper_rejected_even_when_outer_digest_is_recomputed(self):
        path = author_action_prototype(self.root / "action")
        content, project = self._pair(path)
        player = PlayerController(content, project, self.root / "profile.json")
        player.new_game("main", 1, seed=50)
        player.route_action_step({"tick": 1, "dx": 1, "attack": True})
        original = player.session.recording()
        self.assertIn("scene_action", original)
        self.assertIn("scene_route", original)
        corrupted = deepcopy(original)
        corrupted["scene_action"]["runtime"]["commands"][0]["attack"] = False
        corrupted["digest"] = digest(
            {k: v for k, v in corrupted.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(corrupted, content, project)
        changed_scene = deepcopy(original)
        changed_scene["scene_action"]["scene"] = "other"
        changed_scene["digest"] = digest(
            {k: v for k, v in changed_scene.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(changed_scene, content, project)

    def test_player_rejects_bad_tick_and_no_unfinished_scene_transition(self):
        path = author_action_prototype(self.root / "action")
        content, project = self._pair(path)
        player = PlayerController(content, project, self.root / "profile.json")
        player.new_game("main", 1, seed=50)
        checkpoint = player.session.recording()
        save = player.path_for("main", 1)
        snapshot = save.read_bytes()
        with self.assertRaises(RuleError):
            player.route_action_step({"tick": 2, "attack": True})
        self.assertEqual(player.session.recording(), checkpoint)
        self.assertEqual(save.read_bytes(), snapshot)
        player.route_action_step({"tick": 1, "dx": 1, "attack": True})
        battle = player.session.recording()
        with self.assertRaises(RuleError):
            player.route_transition("unknown")
        self.assertEqual(player.session.recording(), battle)

    def _defeat_enemy(self, player):
        player.route_action_step({"tick": 1, "dx": 1, "attack": True})
        for tick in range(2, 13):
            player.route_action_step({"tick": tick, "guard": True})
        player.route_action_step({"tick": 13, "attack": True})
        self.assertEqual(player.route_action_state()["enemies"][ENEMY]["hp"], 0)

    def test_one_shot_reward_then_ct_then_return_cannot_restart(self):
        path = author_action_prototype(self.root / "project")
        content, project = self._pair(path)
        profile = self.root / "p.json"
        player = PlayerController(content, project, profile)
        player.new_game("main", 1, seed=50)
        old_gold = player.session.progress.gold
        with self.assertRaises(RuleError):
            player.route_transition("after_action_to_ct")
        self.assertEqual(player.session.progress.gold, old_gold)
        self._defeat_enemy(player)
        result = player.route_action_settle("after_action_to_ct")
        self.assertEqual(result["coins_awarded"], 1)
        self.assertEqual(player.session.progress.gold, old_gold + 1)
        recorded = player.session.recording()
        self.assertNotIn("scene_action", recorded)
        self.assertEqual(len(recorded["scene_action_history"]), 1)
        self.assertEqual(recorded["scene_route"]["current"],
                         next(iter(content.missions)))
        reader = PlayerController(content, project, profile)
        reader.load_game("main", 1)
        self.assertEqual(reader.session.recording(), recorded)
        self.assertEqual(reader.session.progress.gold, old_gold + 1)
        with self.assertRaises(RuleError):
            reader.route_action_settle("after_action_to_ct")
        reader.abandon_encounter()
        reader.route_transition("ct_to_action")
        with self.assertRaises(RuleError):
            reader.route_action_step({"tick": 1, "attack": True})
        self.assertEqual(reader.session.progress.gold, old_gold + 1)
        self.assertEqual(len(reader.session.recording()["scene_action_history"]), 1)

    def test_settlement_requires_a_genuine_victory_and_restores_on_error(self):
        path = author_action_prototype(self.root / "project")
        content, project = self._pair(path)
        player = PlayerController(content, project, self.root / "p.json")
        player.new_game("main", 1, seed=50)
        player.route_action_step({"tick": 1, "dx": 1, "attack": True})
        before = player.session.recording()
        data = player.path_for("main", 1).read_bytes()
        with self.assertRaises(RuleError):
            player.route_action_settle("after_action_to_ct")
        self.assertEqual(player.session.recording(), before)
        self.assertEqual(player.path_for("main", 1).read_bytes(), data)
        self._defeat_remaining(player)
        won = player.session.recording()
        with self.assertRaises(RuleError):
            player.route_action_settle("missing")
        self.assertEqual(player.session.recording(), won)

    def _defeat_remaining(self, player):
        # First tick was already accepted above with attack, cooldown lasts 12.
        for tick in range(2, 13):
            player.route_action_step({"tick": tick, "guard": True})
        player.route_action_step({"tick": 13, "attack": True})

    def test_ct_startup_failure_rolls_back_paid_gold_and_evidence(self):
        path = author_action_prototype(self.root / "project")
        content, project = self._pair(path)
        player = PlayerController(content, project, self.root / "p.json")
        player.new_game("main", 1, seed=50)
        self._defeat_enemy(player)
        before = player.session.recording()
        saved = player.path_for("main", 1).read_bytes()
        with patch.object(
                player.session, "start_mission",
                side_effect=RuleError("Simulated CT startup failure")):
            with self.assertRaisesRegex(RuleError, "Simulated CT startup"):
                player.route_action_settle("after_action_to_ct")
        self.assertEqual(player.session.recording(), before)
        self.assertEqual(player.path_for("main", 1).read_bytes(), saved)
        self.assertNotIn("scene_action_history", player.session.recording())
        # Retrying on the restored slot pays once and transitions normally.
        result = player.route_action_settle("after_action_to_ct")
        self.assertEqual(result["coins_awarded"], 1)
        self.assertEqual(player.session.mode, "battle")
        self.assertEqual(len(player.session.recording()["scene_action_history"]), 1)

    def test_tampered_settlement_fails_even_with_matching_outer_digest(self):
        path = author_action_prototype(self.root / "project")
        content, project = self._pair(path)
        player = PlayerController(content, project, self.root / "p.json")
        player.new_game("main", 1, seed=50)
        self._defeat_enemy(player)
        player.route_action_settle("after_action_to_ct")
        original = player.session.recording()
        broken = [
            lambda d: d.pop("scene_action_history"),
            lambda d: d["scene_action_history"][0].update(coin=10),
            lambda d: d["scene_action_history"][0].update(route_index=2),
            lambda d: d["scene_action_history"][0]["runtime"]["commands"][0].update(
                attack=False),
            lambda d: d["progress"]["story_flags"].clear(),
            lambda d: d["scene_action_history"].append(
                deepcopy(d["scene_action_history"][0])),
        ]
        for mutation in broken:
            forged = deepcopy(original)
            mutation(forged)
            forged["digest"] = digest(
                {k: v for k, v in forged.items() if k != "digest"})
            with self.subTest(mutation=mutation), self.assertRaises(RuleError):
                GameSession.from_recording(forged, content, project)

    def test_failed_action_audit_never_publishes_partial_creator_project(self):
        output = self.root / "failed"
        with patch("drawtemp.studio.r50b_action.check_action_player_journey",
                   side_effect=ActionJourneyError("Injected replay failure")):
            with self.assertRaisesRegex(CatalogError, "Injected replay failure"):
                create_starter("action_combat_prototype", output)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

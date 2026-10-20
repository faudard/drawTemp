"""R50.B exploration: canonical Studio, routed Player and persistent CT return."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.r50b_catalog import CatalogError, catalog, create_starter
from drawtemp.studio.r50b_exploration import (
    SCENE, TO_BATTLE, BACK, ExplorationJourneyError,
    author_exploration_prototype, check_exploration_player_journey,
)
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController
from sporebound.tactical_rpg3 import authored_rules_for_document


class R50BExplorationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_editor_creates_valid_canonical_route_and_undo_save(self):
        root = self.root / "authored"
        path = author_exploration_prototype(root)
        self.assertEqual(path, root / "game.json")
        self.assertTrue(path.is_file())
        self.assertEqual(
            sorted(p.name for p in root.iterdir()),
            ["game.game.json", "game.json"],
        )
        session = AuthoringSession.open(path)
        snapshot = session.snapshot().to_dict()
        self.assertFalse(snapshot["dirty"])
        project = snapshot["project"]
        self.assertEqual(project["scene_routes"]["start"], SCENE)
        self.assertEqual(project["game_modes"]["scenes"][SCENE]["preset"], "action")
        self.assertEqual(project["game_modes"]["default"]["preset"], "srpg")
        self.assertEqual(
            [r["id"] for r in project["scene_routes"]["links"]],
            [TO_BATTLE, BACK],
        )
        self.assertNotIn("game_modes", snapshot["content"])

    def test_end_to_end_catalog_prototype_is_not_full_action_game(self):
        available = {row["id"]: row for row in catalog()["entries"]}
        self.assertTrue(available["exploration_prototype"]["can_create"])
        self.assertFalse(available["action_adventure"]["can_create"])
        target = self.root / "exploration_prototype"
        report = create_starter("exploration_prototype", target)
        self.assertEqual(report["status"], "headless-pass")
        proof = report["proof"]
        self.assertEqual(proof["player_intent"],
                         "realtime-exploration-to-ct-and-return")
        journey = proof["routed_exploration"]
        self.assertEqual(journey["ticks"], 8)
        self.assertTrue(journey["fixed_movement"])
        self.assertTrue(journey["realtime_save_resume"])
        self.assertTrue(journey["ct_encounter_resume"])
        self.assertTrue(journey["route_return_resume"])
        self.assertTrue(journey["rejected_invalid_intent"])
        self.assertTrue(journey["author_documents_unchanged"])
        self.assertFalse(journey["action_combat_verified"])
        self.assertFalse(journey["qt_onscreen_verified"])
        self.assertFalse(report["release_9_0_ready"])
        self.assertEqual(
            sorted(p.name for p in target.iterdir()),
            ["game.game.json", "game.json"],
        )
        with self.assertRaises(CatalogError):
            create_starter("exploration_prototype", target)
        self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_route_failure_never_publishes_half_created_starter(self):
        target = self.root / "failure"
        with patch(
                "drawtemp.studio.r50b_exploration.check_exploration_player_journey",
                side_effect=ExplorationJourneyError("Simulated CT failure")):
            with self.assertRaisesRegex(CatalogError, "Simulated CT failure"):
                create_starter("exploration_prototype", target)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_player_rejects_wrong_route_without_mutating_slot(self):
        content_path = author_exploration_prototype(self.root / "project")
        snap = AuthoringSession.open(content_path).snapshot().to_dict()
        content = Content.from_dict(
            snap["content"], rules=authored_rules_for_document(snap["content"]))
        project = GameProject.from_dict(snap["project"], content)
        profile = self.root / "profile.json"
        player = PlayerController(content, project, profile)
        player.new_game("main", 1, seed=50)
        before = player.session.recording()
        checkpoint = player.path_for("main", 1).read_bytes()
        with self.assertRaises(RuleError):
            player.route_transition(BACK)
        self.assertEqual(player.session.recording(), before)
        self.assertEqual(player.path_for("main", 1).read_bytes(), checkpoint)
        with self.assertRaises(RuleError):
            player.route_realtime_step(dx=2)
        self.assertEqual(player.session.recording(), before)
        self.assertEqual(player.path_for("main", 1).read_bytes(), checkpoint)

    def test_player_refuses_corrupted_project_without_implicit_repair(self):
        path = author_exploration_prototype(self.root / "project")
        manifest = path.with_name("game.game.json")
        manifest.write_text('{"version": 9999}', encoding="utf-8")
        original = manifest.read_bytes()
        with self.assertRaises((ValueError, RuleError, ExplorationJourneyError)):
            check_exploration_player_journey(path, self.root / "profile.json")
        self.assertEqual(manifest.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

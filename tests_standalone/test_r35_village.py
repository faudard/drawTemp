"""R35.C1 village reference: 4 NPCs, schedule authoring and world debugger."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.studio.living_world_authoring import (
    preview_living_world, apply_living_world)
from sporebound.game_session import GameSession
from sporebound.living_world import EXTENSION
from tests_standalone.test_r35_commerce import merchant_fixture


def living_village():
    content, project = merchant_fixture()
    project.extensions[EXTENSION]["data"]["npcs"].extend([
        {"id": "guard", "schedule": [
            {"minute": 0, "scene": "arrival", "activity": "patrol"},
            {"minute": 720, "scene": "arrival", "activity": "watch"}]},
        {"id": "healer", "schedule": [
            {"minute": 360, "scene": "arrival", "activity": "rest"},
            {"minute": 540, "scene": "arrival", "activity": "treat"}]},
    ])
    project.validate(content)
    return content, project


class R35VillageTests(unittest.TestCase):
    def test_preview_apply_undo_redo_and_revision_guard(self):
        content, project = living_village()
        editor = AuthoringSession.new(content, project)
        original = editor.snapshot().to_dict()
        data = deepcopy(project.extensions[EXTENSION]["data"])
        data["npcs"][0]["schedule"][1]["minute"] = 481
        preview = preview_living_world(
            editor, data, expected_revision=editor.revision)
        self.assertEqual(preview.report["npc_count"], 4)
        self.assertEqual(preview.report["shop_count"], 1)
        self.assertEqual(preview.report["quest_count"], 1)
        self.assertEqual(editor.snapshot().to_dict(), original)
        apply_living_world(editor, preview)
        self.assertEqual(
            editor.snapshot().to_dict()["project"]["extensions"][EXTENSION]
            ["data"]["npcs"][0]["schedule"][1]["minute"], 481)
        with self.assertRaises(AuthoringError):
            apply_living_world(editor, preview)
        editor.undo()
        self.assertEqual(
            editor.snapshot().to_dict()["project"]["extensions"][EXTENSION]
            ["data"]["npcs"][0]["schedule"][1]["minute"], 480)
        editor.redo()
        self.assertEqual(
            editor.snapshot().to_dict()["project"]["extensions"][EXTENSION]
            ["data"]["npcs"][0]["schedule"][1]["minute"], 481)
        bad = deepcopy(data)
        bad["shops"][0]["npc"] = "unknown_actor"
        prior = editor.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            preview_living_world(editor, bad)
        self.assertEqual(editor.snapshot().to_dict(), prior)

    def test_read_only_timeline_and_village_save_handoff(self):
        content, project = living_village()
        game = GameSession.new(content, project, "main", seed=17)
        game.progress.gold = 100
        game.progress.story_flags["market_open"] = True
        original = game.recording()
        report = game.living_world_timeline(scene="arrival", limit=3)
        self.assertTrue(report["preview_only"])
        self.assertTrue(report["truncated"])
        self.assertGreater(report["total"], 3)
        self.assertEqual(len(report["entries"]), 3)
        self.assertEqual(game.recording(), original)
        game.living_world_advance(2)
        state = game.living_world_state(scene="arrival")
        self.assertEqual(len(state["npcs"]), 4)
        self.assertTrue(state["shops"][0]["open"])
        game.living_world_trade("village_shop", "herb", "buy", 1, "village_1")
        self.assertEqual(game.living_world_state()["shops"][0]["items"][0]["stock"], 4)
        game.progress.story_flags["portal_open"] = True
        game.route_transition("to_arena")
        self.assertEqual(game.living_world_state()["ticks"], 2)
        game.abandon_encounter()
        game.route_transition("retreat")
        self.assertEqual(game.living_world_state()["shops"][0]["items"][0]["stock"], 4)
        restored = GameSession.from_recording(game.recording(), content, project)
        self.assertEqual(restored.living_world_state(), game.living_world_state())
        self.assertFalse(restored.living_world_trade(
            "village_shop", "herb", "buy", 1, "village_1"))


if __name__ == "__main__":
    unittest.main()

"""R35.D1: bounded, replay-stable off-focus NPC movement with real wall collision."""
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from sporebound.game_session import GameSession
from sporebound.living_world import EXTENSION, LivingWorld
from sporebound.living_world_navigation import shortest_path
from sporebound.model import RuleError
from tests_standalone.test_r35_village import living_village


def positional_village():
    content, project = living_village()
    data = project.extensions[EXTENSION]["data"]
    data["start_minute"] = 475
    merchant = next(n for n in data["npcs"] if n["id"] == "merchant")
    for stop, pos in zip(merchant["schedule"],
                         ([1, 1], [3, 1], [1, 1])):
        stop["pos"] = list(pos)
    traveler = next(n for n in data["npcs"] if n["id"] == "traveler")
    for stop, pos in zip(traveler["schedule"], ([0, 0], [0, 3])):
        stop["pos"] = list(pos)
    project.validate(content)
    return content, project


class R35NavigationTests(unittest.TestCase):
    def test_obstacle_aware_shortest_route_and_no_wall_teleport(self):
        content, project = positional_village()
        scene = project.exploration["arrival"]
        self.assertEqual(shortest_path(scene, [1, 1], [3, 1]),
                         [[1, 1], [1, 0], [2, 0], [3, 0], [3, 1]])
        game = GameSession.new(content, project, "main", seed=27)
        game.progress.story_flags["market_open"] = True
        def merchant():
            return next(n for n in game.living_world_state()["npcs"]
                        if n["id"] == "merchant")
        self.assertEqual(merchant()["pos"], [1, 1])
        self.assertFalse(merchant()["moving"])
        self.assertFalse(game.living_world_state()["shops"][0]["open"])
        expected = ([1, 1], [1, 1], [1, 0],
                    [2, 0], [3, 0], [3, 1])
        for i, pos in enumerate(expected):
            self.assertEqual(merchant()["pos"], pos)
            if i < len(expected) - 1:
                game.living_world_advance(2)
        self.assertEqual(game.living_world_state()["minute"], 480)
        self.assertEqual(merchant()["activity"], "trade")
        self.assertTrue(game.living_world_state()["shops"][0]["open"])

    def test_offfocus_resume_large_jump_and_scene_transition(self):
        content, project = positional_village()
        game = GameSession.new(content, project, "main")
        game.progress.story_flags["market_open"] = True
        game.living_world_advance(6)  # 475 -> 478, one route midpoint.
        before = game.living_world_state()
        pos = next(n["pos"] for n in before["npcs"] if n["id"] == "merchant")
        self.assertEqual(pos, [2, 0])
        self.assertTrue(next(n["moving"] for n in before["npcs"]
                             if n["id"] == "merchant"))
        with TemporaryDirectory() as temp:
            saved = Path(temp) / "world.json"
            game.save(saved)
            restored = GameSession.load(saved, content, project)
            self.assertEqual(restored.living_world_state(), before)
            self.assertEqual(restored.recording(), game.recording())
            restored.progress.story_flags["portal_open"] = True
            restored.route_transition("to_arena")
            self.assertEqual(restored.living_world_state(), before)
            restored.abandon_encounter()
            restored.route_transition("retreat")
            restored.living_world_advance(4)
            self.assertEqual(restored.living_world_state()["minute"], 480)
            self.assertTrue(restored.living_world_state()["shops"][0]["open"])

    def test_disabled_conditional_stop_and_all_or_none_waypoints(self):
        content, project = positional_village()
        game = GameSession.new(content, project, "main")
        game.living_world_advance(8)  # Minute 479: before the opening.
        merchant = next(n for n in game.living_world_state()["npcs"]
                        if n["id"] == "merchant")
        self.assertEqual(merchant["pos"], [3, 0])
        self.assertTrue(merchant["moving"])
        game.progress.story_flags["market_open"] = True
        same_cell = next(n for n in game.living_world_state()["npcs"]
                         if n["id"] == "merchant")
        self.assertEqual(same_cell["pos"], [3, 0])
        game.living_world_advance(2)
        arrived = next(n for n in game.living_world_state()["npcs"]
                       if n["id"] == "merchant")
        self.assertEqual(arrived["pos"], [3, 1])
        self.assertEqual(arrived["activity"], "trade")
        game.progress.story_flags["market_open"] = False
        inactive = next(n for n in game.living_world_state()["npcs"]
                        if n["id"] == "merchant")
        self.assertEqual(inactive["pos"], [3, 1])
        self.assertEqual(inactive["activity"], "unavailable")
        invalid = deepcopy(project)
        del invalid.extensions[EXTENSION]["data"]["npcs"][0]["schedule"][0]["pos"]
        with self.assertRaises(RuleError):
            invalid.validate(content)
        invalid = deepcopy(project)
        invalid.extensions[EXTENSION]["data"]["npcs"][0]["schedule"][0]["pos"] = [2, 1]
        with self.assertRaises(RuleError):
            invalid.validate(content)
        invalid = deepcopy(project)
        invalid.extensions[EXTENSION]["data"]["npcs"][0]["schedule"][0]["pos"] = [True, 1]
        with self.assertRaises(RuleError):
            invalid.validate(content)

    def test_reject_disconnected_and_too_fast_routes(self):
        content, project = positional_village()
        invalid = deepcopy(project)
        data = invalid.extensions[EXTENSION]["data"]
        data["npcs"][0]["schedule"][1]["minute"] = 1
        with self.assertRaises(RuleError):
            invalid.validate(content)
        stage = {"width": 5, "height": 5,
                 "blocked": [[2, y] for y in range(5)]}
        with self.assertRaises(RuleError):
            shortest_path(stage, [2, 0], [1, 0])
        self.assertIsNone(shortest_path(stage, [1, 0], [3, 0]))

    def test_optional_feature_preserves_historical_npc_shape(self):
        content, project = living_village()
        world = LivingWorld(project.extensions[EXTENSION]["data"],
                            set(project.exploration) | set(content.missions))
        self.assertNotIn("pos", world.view({})["npcs"][0])
        self.assertNotIn("moving", world.view({})["npcs"][0])
        self.assertNotIn("navigation", world.snapshot())


if __name__ == "__main__":
    unittest.main()

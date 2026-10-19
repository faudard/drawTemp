"""R35.D2: explicit cross-scene portal projection, replay, render and scale."""
from copy import deepcopy
from unittest.mock import patch
import unittest

from drawtemp.render.iso_scene import scene_from_exploration
from drawtemp.sdk.simulation import Simulation, SimulationError
from sporebound.living_world import EXTENSION, LivingWorld
from sporebound.model import RuleError
from tests_standalone.test_r35_navigation import positional_village


def two_village_world():
    exploration = {
        "a": {"width": 5, "height": 4, "blocked": [[2, 1]]},
        "b": {"width": 5, "height": 4, "blocked": []},
    }
    spec = {
        "version": 1, "start_minute": 0, "ticks_per_minute": 1,
        "clock_policy": "exploration_only",
        "npcs": [{
            "id": "courier",
            "schedule": [
                {"minute": 0, "scene": "a",
                 "activity": "rest", "pos": [1, 1]},
                {"minute": 12, "scene": "b",
                 "activity": "deliver", "pos": [2, 1]},
                {"minute": 24, "scene": "a",
                 "activity": "rest", "pos": [1, 1]},
            ]}],
        "transfers": [
            {"id": "a_b", "from_scene": "a", "to_scene": "b",
             "from_pos": [3, 1], "to_pos": [0, 1],
             "travel_minutes": 2},
            {"id": "b_a", "from_scene": "b", "to_scene": "a",
             "from_pos": [0, 1], "to_pos": [3, 1],
             "travel_minutes": 2},
        ],
    }
    return spec, exploration


class R35TransferTests(unittest.TestCase):
    def make_world(self):
        spec, stages = two_village_world()
        return LivingWorld(spec, set(stages), exploration=stages)

    def test_gate_to_gate_timeline_and_midnight(self):
        world = self.make_world()
        checkpoints = {
            0: ("a", [1, 1], "rest"),
            4: ("a", [1, 1], "rest"),
            5: ("a", [1, 0], "travel"),
            6: ("a", [2, 0], "travel"),
            7: ("a", [3, 0], "travel"),
            8: ("a", [3, 1], "travel"),
            9: (None, None, "travel"),
            10: ("b", [0, 1], "travel"),
            11: ("b", [1, 1], "travel"),
            12: ("b", [2, 1], "deliver"),
            19: (None, None, "travel"),
            20: ("a", [3, 1], "travel"),
            24: ("a", [1, 1], "rest"),
        }
        for tick, (scene, cell, activity) in checkpoints.items():
            world.restore({"version": 1, "ticks": tick})
            row = world.view({})["npcs"][0]
            self.assertEqual((row["scene"], row["pos"], row["activity"]),
                             (scene, cell, activity), str(tick))
            self.assertEqual(len(world.view({}, scene="a")["npcs"]),
                             int(scene == "a"))
            self.assertEqual(len(world.view({}, scene="b")["npcs"]),
                             int(scene == "b"))
        world.restore({"version": 1, "ticks": 1440})
        row = world.view({})["npcs"][0]
        self.assertEqual((world.day, world.minute), (1, 0))
        self.assertEqual((row["scene"], row["pos"]), ("a", [1, 1]))

    def test_missing_ambiguous_blocked_and_too_fast_transfer(self):
        spec, stages = two_village_world()
        cases = [
            lambda s: s["transfers"].pop(),
            lambda s: s["transfers"].append(deepcopy(s["transfers"][0])),
            lambda s: s["transfers"][0].update(from_pos=[2, 1]),
            lambda s: s["transfers"][0].update(travel_minutes=True),
            lambda s: s["transfers"][0].update(travel_minutes=240),
            lambda s: s["transfers"][0].update(to_scene="missing"),
        ]
        for corruption in cases:
            bad = deepcopy(spec)
            corruption(bad)
            with self.subTest(document=bad), self.assertRaises(RuleError):
                LivingWorld(bad, set(stages), exploration=stages)
        legacy = deepcopy(spec)
        del legacy["transfers"]
        world = LivingWorld(legacy, set(stages), exploration=stages)
        world.advance(8)
        self.assertTrue(world.view({})["npcs"][0]["handoff_pending"])

    def test_projection_cache_and_batched_advance_equivalence(self):
        before, after = self.make_world(), self.make_world()
        with patch("sporebound.living_world_navigation.shortest_path",
                   side_effect=AssertionError("BFS during presentation")):
            for ticks in range(0, 31):
                after.restore({"version": 1, "ticks": ticks})
                self.assertEqual(len(after.view({})["npcs"]), 1)
                self.assertEqual(len(after.view({}, scene="a")["npcs"]),
                                 int(after.view({})["npcs"][0]["scene"] == "a"))
        before.advance(30)
        after.restore({"version": 1, "ticks": 0})
        for _ in range(30):
            after.advance()
        self.assertEqual(before.snapshot(), after.snapshot())
        self.assertEqual(before.view({}), after.view({}))

    def test_player_sdk_and_exploration_scene_are_read_only(self):
        content, project = positional_village()
        sdk = Simulation.new(content, project, "main")
        before = sdk.recording()
        state = sdk.living_world_state(scene="arrival")
        self.assertEqual(list(state["npcs"][0]["pos"]), [1, 1])
        self.assertEqual(sdk.recording(), before)
        stage = {
            "width": 4, "height": 4, "blocked": [[2, 1]],
            "theme": "village", "scene_id": "arrival",
            "position": [0, 1], "actors": [], "interactions": [],
        }
        rendered = scene_from_exploration(stage, living_world=state)
        ids = {a["id"] for a in rendered["actors"]}
        self.assertIn("world:merchant", ids)
        self.assertEqual(len([a for a in rendered["actors"]
                              if a["id"] == "world:merchant"]), 1)
        self.assertEqual(sdk.recording(), before)
        transition = sdk.living_world_advance(2, expected_revision=0)
        self.assertEqual(transition.snapshot.revision, 1)
        with self.assertRaises(SimulationError):
            sdk.living_world_advance(1, expected_revision=0)
        self.assertEqual(sdk.living_world_state()["ticks"], 2)

    def test_256_off_focus_npcs_and_same_route_share_data(self):
        spec, stages = two_village_world()
        source = deepcopy(spec["npcs"][0])
        spec["npcs"] = []
        for i in range(256):
            actor = deepcopy(source)
            actor["id"] = "courier_" + str(i)
            spec["npcs"].append(actor)
        world = LivingWorld(spec, set(stages), exploration=stages)
        self.assertEqual(len(world._nav_routes), 256 * 3)
        world.advance(9)
        rows = world.view({})["npcs"]
        self.assertEqual(len(rows), 256)
        self.assertTrue(all(n["scene"] is None for n in rows))
        self.assertEqual(len(world.view({}, scene="a")["npcs"]), 0)
        self.assertEqual(len(world.view({}, scene="b")["npcs"]), 0)
        self.assertEqual(world.snapshot(), {"version": 1, "ticks": 9})


if __name__ == "__main__":
    unittest.main()

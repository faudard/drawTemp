"""R64.A gates: integer-tick squads, formation, collisions, replay, CT isolation."""
from copy import deepcopy
import json
import unittest

from sporebound.fixed_clock import _digest
from sporebound.model import RuleError
from sporebound.rts64 import RTSWorld, STALL_WARNING


class RTSWorldTests(unittest.TestCase):
    def test_squad_pathfinding_formation_and_replay(self):
        units = [
            {"id": "a", "team": "blue", "pos": [1, 1]},
            {"id": "b", "team": "blue", "pos": [1, 2]},
        ]
        walls = [[3, 1], [3, 2], [3, 3]]
        world = RTSWorld(7, 5, units, walls=walls, rate=30, seed=42)
        world.submit(1, "player", {
            "kind": "move_group", "units": ["b", "a"],
            "target": [5, 2], "formation": "column"})
        snapshots = []
        for _ in range(36):
            frame = world.step()
            snapshots.append(frame)
            cells = [tuple(a["pos"]) for a in frame["units"] if a["hp"]]
            self.assertEqual(len(cells), len(set(cells)), "unit collision")
            self.assertTrue(all(tuple(p) not in {tuple(c) for c in walls}
                                for p in cells))
        self.assertEqual([a["pos"] for a in snapshots[-1]["units"]],
                         [[5, 2], [5, 3]])
        self.assertFalse(snapshots[-1]["stalled_units"])
        recording = json.loads(json.dumps(world.recording()))
        clone = RTSWorld.replay(7, 5, units, recording, walls=walls)
        self.assertEqual(clone.snapshot(), world.snapshot())
        self.assertEqual(clone.recording(), recording)

    def test_commands_ordered_by_source_and_formation_deterministically(self):
        units = [{"id": "u", "team": "blue", "pos": [2, 2]}]
        world = RTSWorld(6, 6, units)
        world.submit(1, "z", {"kind": "move_group", "units": ["u"],
                              "target": [4, 2]})
        world.submit(1, "a", {"kind": "move_group", "units": ["u"],
                              "target": [2, 4]})
        first = world.step()
        self.assertEqual([i["source"] for i in world.recording()["inputs"]],
                         ["a", "z"])
        self.assertEqual(first["units"][0]["goal"], [4, 2])
        self.assertEqual(first["units"][0]["pos"], [3, 2])
        original = world.snapshot()
        original["units"][0]["pos"][0] = 99
        self.assertEqual(world.snapshot(), first)

    def test_engagement_simultaneous_and_defensive_return_fire(self):
        units = [{"id": "a", "team": "blue", "pos": [0, 0], "hp": 3},
                 {"id": "b", "team": "red", "pos": [1, 0], "hp": 3}]
        world = RTSWorld(3, 2, units)
        world.submit(1, "control", {
            "kind": "set_engagement", "units": ["a"], "rules": "fire_at_will"})
        world.submit(1, "control", {
            "kind": "set_engagement", "units": ["b"], "rules": "return_fire"})
        for _ in range(10):
            world.step()
        a, b = world.snapshot()["units"]
        self.assertEqual((a["hp"], b["hp"]), (3, 2))
        for _ in range(10):
            world.step()
        a, b = world.snapshot()["units"]
        self.assertEqual((a["hp"], b["hp"]), (2, 1))
        for _ in range(10):
            world.step()
        a, b = world.snapshot()["units"]
        self.assertEqual((a["hp"], b["hp"]), (1, 0))
        self.assertEqual(b["goal"], None)
        self.assertEqual(RTSWorld.replay(
            3, 2, units, world.recording()).snapshot(), world.snapshot())

    def test_invalid_order_rolls_back_complete_tick(self):
        units = [{"id": "a", "team": "blue", "pos": [0, 0]},
                 {"id": "b", "team": "red", "pos": [3, 0]}]
        invalid = [
            {"kind": "move_group", "units": ["a", "b"], "target": [1, 1]},
            {"kind": "move_group", "units": ["a", "a"], "target": [1, 1]},
            {"kind": "move_group", "units": ["a"], "target": [True, 0]},
            {"kind": "move_group", "units": ["a"], "target": [4, 4]},
            {"kind": "move_group", "units": ["a"], "target": [1, 1],
             "formation": "impossible"},
            {"kind": "set_engagement", "units": ["a"], "rules": "kill_all"},
            {"kind": "stop_group", "units": ["a"], "unexpected": 1},
        ]
        for bad in invalid:
            with self.subTest(bad=bad):
                world = RTSWorld(4, 2, units)
                original = world.snapshot()
                # First command is valid; second one must abort the entire tick.
                world.submit(1, "a", {
                    "kind": "move_group", "units": ["a"], "target": [1, 0]})
                world.submit(1, "z", bad)
                with self.assertRaises(RuleError):
                    world.step()
                self.assertEqual(world.snapshot(), original)
                self.assertEqual(world.clock.tick, 0)

    def test_obstacle_stall_is_reported_without_overlap_or_teleport(self):
        world = RTSWorld(3, 1, [
            {"id": "a", "team": "blue", "pos": [0, 0]},
            {"id": "b", "team": "red", "pos": [1, 0]},
        ])
        world.submit(1, "player", {
            "kind": "move_group", "units": ["a"], "target": [2, 0]})
        for _ in range(STALL_WARNING):
            world.step()
        frame = world.snapshot()
        self.assertEqual([a["pos"] for a in frame["units"]],
                         [[0, 0], [1, 0]])
        self.assertEqual(frame["stalled_units"], ["a"])
        self.assertEqual(RTSWorld.replay(3, 1, [
            {"id": "a", "team": "blue", "pos": [0, 0]},
            {"id": "b", "team": "red", "pos": [1, 0]},
        ], world.recording()).snapshot(), frame)

    def test_tamper_and_other_scenario_are_not_silent(self):
        units = [{"id": "a", "team": "blue", "pos": [0, 0]}]
        world = RTSWorld(4, 4, units)
        world.submit(1, "player", {
            "kind": "move_group", "units": ["a"], "target": [2, 2]})
        for _ in range(4):
            world.step()
        original = world.recording()
        changed = deepcopy(original)
        changed["inputs"][0]["command"]["target"] = [1, 2]
        with self.assertRaises(RuleError):
            RTSWorld.replay(4, 4, units, changed)
        # Rehashing a modified command is insufficient to falsify every state.
        changed["digest"] = _digest({k: v for k, v in changed.items()
                                     if k != "digest"})
        with self.assertRaises(RuleError):
            RTSWorld.replay(4, 4, units, changed)
        with self.assertRaises(RuleError):
            RTSWorld.replay(5, 4, units, original)

    def test_rts_does_not_change_jeanne_ct_session(self):
        from drawtemp.sdk.reference import reference_project
        from sporebound.game_session import GameSession
        content, project = reference_project()
        before = GameSession.new(content, project, "main", seed=64).recording()
        world = RTSWorld(4, 3, [
            {"id": "a", "team": "blue", "pos": [1, 0]}])
        world.submit(1, "p", {"kind": "move_group", "units": ["a"],
                              "target": [2, 2], "formation": "wedge"})
        for _ in range(6):
            world.step()
        after = GameSession.new(content, project, "main", seed=64).recording()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

"""R13.8 movement heatmaps are grounded only in replay observed transitions."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from drawtemp.sdk.r13_movement_heatmap import build_movement_heatmap
from sporebound.battle_diagnostics import trace_seed
from sporebound.model import Board, Content, Mission, RuleError, Unit


def observed_trace():
    initial = {"tick": 0, "units": [
        {"id": "hero", "team": "player", "level": 0,
         "pos": [1, 1], "alive": True},
        {"id": "foe", "team": "enemy", "level": 0,
         "pos": [4, 1], "alive": True},
    ]}
    frames = [
        [dict(initial["units"][0]), dict(initial["units"][1])],
        [dict(initial["units"][0], pos=[2, 1]), dict(initial["units"][1])],
        [dict(initial["units"][0], pos=[2, 1]), dict(initial["units"][1]),
         {"id": "reinforcement", "team": "enemy", "level": 1,
          "pos": [3, 3], "alive": True}],
        [dict(initial["units"][0], pos=[2, 1], level=1),
         dict(initial["units"][1]),
         {"id": "reinforcement", "team": "enemy", "level": 1,
          "pos": [3, 3], "alive": True}],
    ]
    return {
        "kind": "battle_diagnostics", "schema": 1,
        "mission": "synthetic", "seed": 19,
        "digest": "fixture-verified-external", "replay_verified": True,
        "board": {"width": 6, "height": 5, "goals": []},
        "initial": initial,
        "steps": [{"index": i+1, "after": {"tick": i+1, "units": units}}
                  for i, units in enumerate(frames)],
    }


class HeatmapR13Tests(unittest.TestCase):
    def test_real_trace_positions_all_in_bounds_deterministic(self):
        content = Content({}, {"arena": Mission(
            "arena", "Arena", Board(6, 5), [
                Unit("hero", "Hero", "player", (0, 1)),
                Unit("foe", "Foe", "enemy", (4, 1)),
            ])})
        trace = trace_seed(content, "arena", seed=17, max_commands=60)
        original = deepcopy(trace)
        heatmap = build_movement_heatmap(trace)
        self.assertEqual(trace, original)
        self.assertEqual(heatmap["commands"], len(trace["steps"]))
        self.assertEqual(heatmap["seed"], 17)
        self.assertTrue(heatmap["replay_verified"])
        self.assertEqual(
            sum(row["visits"] for row in heatmap["cells"]),
            len(heatmap["entries"]))
        self.assertTrue(all(
            0 <= row["cell"][0] < 6 and 0 <= row["cell"][1] < 5
            for row in heatmap["entries"]))
        self.assertEqual(json.loads(json.dumps(heatmap)), heatmap)
        self.assertEqual(build_movement_heatmap(trace), heatmap)

    def test_only_observed_transitions_spawn_and_floor_are_counted(self):
        trace = observed_trace()
        before = deepcopy(trace)
        heatmap = build_movement_heatmap(trace)
        self.assertEqual(trace, before)
        self.assertEqual(heatmap["levels"], [0, 1])
        moves = [row for row in heatmap["entries"] if row["kind"] == "move"]
        spawns = [row for row in heatmap["entries"] if row["kind"] == "spawn"]
        self.assertEqual(len(moves), 2)
        self.assertEqual(len(spawns), 1)
        self.assertEqual(spawns[0]["unit"], "reinforcement")
        self.assertEqual(spawns[0]["step"], 3)
        self.assertEqual(moves[0]["from_cell"], [1, 1])
        self.assertEqual(moves[0]["cell"], [2, 1])
        self.assertEqual(moves[0]["step"], 2)
        self.assertEqual(moves[1]["from_level"], 0)
        self.assertEqual(moves[1]["level"], 1)
        self.assertEqual(moves[1]["from_cell"], [2, 1])
        self.assertEqual(moves[1]["cell"], [2, 1])
        self.assertEqual(moves[1]["step"], 4)
        # Four frames with an idle foe must not count as four additional visits.
        foe = [row for row in heatmap["cells"] if row["unit"] == "foe"]
        self.assertEqual(len(foe), 1)
        self.assertEqual(foe[0]["visits"], 1)
        self.assertEqual(foe[0]["movements"], 0)
        self.assertEqual(len(heatmap["entries"]), 5)

    def test_reject_unverified_bad_coordinates_and_order(self):
        examples = [
            ("replay_verified", False),
            ("kind", "other"),
            ("steps", [{"index": 123, "after": {"tick": 1, "units": []}}]),
            ("board", {"width": 0, "height": 5}),
        ]
        for key, replacement in examples:
            trace = observed_trace()
            trace[key] = replacement
            with self.subTest(key=key), self.assertRaises(RuleError):
                build_movement_heatmap(trace)
        for bad_position in ([6, 1], [-1, 0], [True, 0], [1.5, 1]):
            trace = observed_trace()
            trace["steps"][0]["after"]["units"][0]["pos"] = bad_position
            with self.subTest(pos=bad_position), self.assertRaises(RuleError):
                build_movement_heatmap(trace)
        trace = observed_trace()
        trace["steps"][0]["after"]["units"].append(
            dict(trace["steps"][0]["after"]["units"][0]))
        with self.assertRaises(RuleError):
            build_movement_heatmap(trace)
        trace = observed_trace()
        trace["steps"][0]["after"]["units"][0]["team"] = "enemy"
        with self.assertRaises(RuleError):
            build_movement_heatmap(trace)


if __name__ == "__main__":
    unittest.main()

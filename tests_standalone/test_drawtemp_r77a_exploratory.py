"""R77.A bounded exploratory QA: real R26 ticks, deterministic evidence."""
from copy import deepcopy
import unittest

from drawtemp.quality.r77_exploratory import explore_action_scene
from sporebound.action_runtime import ActionRuntime


def scene(*, key=False, chest=False):
    walls = [[2, y] for y in range(5) if y != 2] if key else []
    objects = []
    if key:
        objects.append({"id": "gate", "kind": "door", "pos": [2, 2],
                        "item": "", "requires": "brass_key"})
    if chest:
        objects.append({"id": "cache", "kind": "chest", "pos": [1, 1],
                        "item": "brass_key", "requires": ""})
    return {"id": "r77_test", "width": 5, "height": 5,
            "walls": walls, "hero": {"pos": [1, 2], "hp": 10},
            "enemies": [], "objects": objects}


class ExploratoryQaTests(unittest.TestCase):
    def test_real_runtime_replay_and_nonmutation(self):
        original = scene()
        saved = deepcopy(original)
        result = explore_action_scene(original, [[3, 2]], seeds=(7, 4),
                                      ticks_per_seed=100)
        self.assertEqual(original, saved)
        self.assertEqual(result["kind"], "r77a-action-exploration")
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["runtime_replay_verified"])
        self.assertFalse(result["release_certified"])
        self.assertIn([3, 2], result["coverage"]["goals"])
        for run in result["runs"]:
            runtime = ActionRuntime(saved)
            for command in run["trace"]:
                runtime.step(command)
            self.assertEqual(runtime.digest(), run["final_state_sha256"])
            self.assertEqual(run["ticks"], len(run["trace"]))
        self.assertEqual(result, explore_action_scene(saved, [[3, 2]],
                                                       seeds=(7, 4), ticks_per_seed=100))

    def test_unopenable_door_reports_abstract_softlock_with_witness(self):
        data = scene(key=True)
        outcome = explore_action_scene(data, [[3, 2]], seeds=(9,),
                                       ticks_per_seed=100)
        self.assertEqual(outcome["status"], "abstract_softlock_risk")
        self.assertEqual(outcome["static_preflight"]["status"], "softlock_risk")
        self.assertEqual(outcome["static_preflight"]["unreachable_goals"], [[3, 2]])
        self.assertFalse(outcome["release_certified"])
        self.assertTrue(outcome["runtime_replay_verified"])
        self.assertNotIn([3, 2], outcome["coverage"]["goals"])

    def test_acquired_key_retries_door_and_allows_goal(self):
        data = scene(key=True, chest=True)
        result = explore_action_scene(data, [[3, 2]], seeds=(3,),
                                      ticks_per_seed=180)
        self.assertEqual(result["status"], "partial")
        self.assertIn("opened:gate", result["coverage"]["conditions"])
        self.assertIn([3, 2], result["coverage"]["goals"])
        self.assertTrue(result["runtime_replay_verified"])

    def test_budget_exhaustion_is_inconclusive(self):
        result = explore_action_scene(scene(), [[3, 2]], seeds=(0,),
                                      ticks_per_seed=2, state_budget=1)
        self.assertEqual(result["status"], "inconclusive")
        self.assertFalse(result["static_preflight"]["complete"])
        self.assertFalse(result["release_certified"])

    def test_fail_closed_configuration_and_authoring(self):
        for kwargs in ({"seeds": ()}, {"seeds": (1, 1)},
                       {"seeds": (True,)}, {"ticks_per_seed": 0},
                       {"ticks_per_seed": 513}, {"state_budget": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                explore_action_scene(scene(), [[3, 2]], **kwargs)
        bad = scene()
        bad["hero"]["pos"] = [99, 2]
        with self.assertRaises(ValueError):
            explore_action_scene(bad, [[3, 2]])
        with self.assertRaises(ValueError):
            explore_action_scene(scene(), [])


if __name__ == "__main__":
    unittest.main()

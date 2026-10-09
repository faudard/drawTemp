"""Scenario director tests: branching, persistence and invalid transitions."""
import unittest
from sporebound.model import RuleError
from sporebound.scenarios import ScenarioDirector


class ScenarioDirectorTests(unittest.TestCase):
    def fixture(self):
        return ScenarioDirector.from_dict({
            "start": "approach",
            "phases": [
                {"id": "approach", "mission": "castle_troll",
                 "exits": {"ram": "gate", "sneak": None},
                 "on_exit": {"ram": {"route": "ram"}}},
                {"id": "gate", "mission": "castle_ram",
                 "exits": {"finish": None}},
            ],
        })

    def test_branch_and_restore(self):
        director = self.fixture()
        self.assertEqual(director.available_choices(), ["ram", "sneak"])
        director.advance("victory", "ram")
        self.assertEqual(director.mission_id(), "castle_ram")
        self.assertEqual(director.flags["route"], "ram")
        state = director.state()
        restored = self.fixture()
        restored.restore(state)
        self.assertEqual(restored.state(), state)
        restored.advance("victory", "finish")
        self.assertTrue(restored.completed)

    def test_reject_invalid_branch_without_mutation(self):
        director = self.fixture()
        original = director.state()
        with self.assertRaises(RuleError):
            director.advance("victory", "unknown")
        self.assertEqual(director.state(), original)

    def test_reject_unknown_destination(self):
        with self.assertRaises(RuleError):
            ScenarioDirector.from_dict({
                "start": "a",
                "phases": [{"id": "a", "mission": "m", "exits": {"go": "missing"}}],
            })


if __name__ == "__main__":
    unittest.main()

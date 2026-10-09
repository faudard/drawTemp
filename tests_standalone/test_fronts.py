"""Global front timeline tests."""
import unittest
from sporebound.fronts import FrontDirector
from sporebound.model import RuleError


class FrontTests(unittest.TestCase):
    def fixture(self):
        return FrontDirector({
            "gate": {"strength": 8, "opposition": 12},
            "walls": {"strength": 6, "opposition": 7, "doctrine": "assault"},
            "camp": {"strength": 4, "opposition": 6, "doctrine": "delay"},
        }, "gate")

    def test_focused_front_not_automatically_resolved(self):
        director = self.fixture()
        director.advance()
        self.assertEqual(director.fronts["gate"]["opposition"], 12)
        self.assertEqual(director.fronts["walls"]["opposition"], 4)
        self.assertEqual(director.turn, 1)

    def test_switch_focus_at_sync_boundary(self):
        director = self.fixture()
        director.advance()
        director.switch("walls")
        director.advance()
        self.assertEqual(director.fronts["walls"]["opposition"], 4)
        self.assertEqual(director.fronts["gate"]["opposition"], 11)

    def test_restore_and_invalid_focus(self):
        director = self.fixture()
        director.advance()
        state = director.state()
        restored = self.fixture()
        restored.restore(state)
        self.assertEqual(restored.state(), state)
        with self.assertRaises(RuleError):
            restored.switch("unknown")


if __name__ == "__main__":
    unittest.main()

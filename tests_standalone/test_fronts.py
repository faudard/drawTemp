"""Global front timeline tests."""
import unittest
from sporebound.fronts import FrontDirector, MultiFrontSession
from unittest.mock import patch
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

    def test_multifront_lazily_creates_battles_and_keeps_focus(self):
        class FakeBattle:
            def __init__(self, content, mission_id, seed=1, rules=None):
                self.mission_id = mission_id
                self.active = None
                self.result = None
                self.units = []

            def state(self):
                return {"mission": self.mission_id}

        class FakeContent:
            missions = {"gate": object(), "walls": object()}

        with patch("sporebound.engine.Battle", FakeBattle):
            session = MultiFrontSession(FakeContent(),
                                        {"gate": "gate", "walls": "walls"}, "gate")
            self.assertEqual(len(session.battles), 1)
            session.advance()
            self.assertEqual(session.timeline.turn, 1)
            session.switch("walls")
            self.assertEqual(len(session.battles), 2)
            self.assertEqual(session.active.mission_id, "walls")
            session.active.result = "victory"
            session.advance()
            self.assertEqual(session.timeline.fronts["walls"]["status"], "victory")


if __name__ == "__main__":
    unittest.main()

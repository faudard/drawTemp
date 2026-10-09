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


    def test_unopened_front_materializes_offscreen_losses(self):
        from examples.siege_scenarios import siege_content
        s = MultiFrontSession(
            siege_content(), {"gate": "castle_ram", "walls": "castle_ramparts"},
            "gate", specs={"gate": {"strength": 8, "opposition": 8},
                           "walls": {"strength": 5, "opposition": 11,
                                     "doctrine": "assault"}})
        s.advance()
        s.advance()
        self.assertEqual(s.timeline.fronts["walls"]["opposition"], 5)
        s.switch("walls")
        # Prior losses must not evaporate when a front is opened for the first time.
        self.assertEqual(s.active.unit("defender").hp, 34)
        s.switch("gate")
        s.switch("walls")
        self.assertEqual(s.active.unit("defender").hp, 34)

    def test_replay_interleaves_deployment_orders_and_waves(self):
        from examples.siege_scenarios import siege_content
        s = MultiFrontSession(
            siege_content(), {"gate": "castle_ram", "walls": "castle_ramparts"},
            "gate", seed=7,
            specs={"gate": {"strength": 8, "opposition": 8},
                   "walls": {"strength": 8, "opposition": 12}})
        s.execute({"kind": "start_battle"})
        s.set_doctrine("walls", "assault")
        s.reinforce("walls", [{"id": "reserve", "name": "Reserve", "team": "enemy",
                               "pos": [11, 7]}], lifetime=50)
        s.advance()
        s.switch("walls")
        self.assertEqual(s.active.unit("defender").hp, 37)
        s.execute({"kind": "start_battle"})
        self.assertTrue(any(e["kind"] == "encounter_wave_queued"
                            for e in s.active.events))
        s.set_doctrine("gate", "delay")
        s.advance()
        recording = s.recording()
        replayed = MultiFrontSession.replay(recording)
        self.assertEqual(replayed.state(), s.state())
        self.assertEqual(replayed.digest(), s.digest())
        self.assertEqual(len(replayed.history), len(s.history))

        restored = MultiFrontSession(
            siege_content(), {"gate": "castle_ram", "walls": "castle_ramparts"},
            "gate", seed=7)
        restored.restore(recording)
        self.assertEqual(restored.digest(), s.digest())

    def test_replay_detects_out_of_band_changes_and_tampering(self):
        from copy import deepcopy
        from examples.siege_scenarios import siege_content
        s = MultiFrontSession(siege_content(), {"gate": "castle_ram",
                             "walls": "castle_ramparts"}, "gate")
        s.execute({"kind": "start_battle"})
        good = s.recording()
        changed = deepcopy(good)
        changed["operations"][0]["command"] = {"kind": "start_battle", "extra": "x"}
        # Unknown extra keys are presently tolerated; the final checksum remains
        # the authority for semantic state, so change an actual operation.
        changed["operations"][0]["command"] = {"kind": "end"}
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(changed)
        s.active.unit("captain").hp -= 1
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(s.recording())
        before = deepcopy(s.state())
        with self.assertRaises(RuleError):
            s.restore(before)
        self.assertEqual(s.state(), before)

    def test_failed_orders_do_not_modify_journal(self):
        from examples.siege_scenarios import siege_content
        s = MultiFrontSession(siege_content(), {"gate": "castle_ram",
                             "walls": "castle_ramparts"}, "gate")
        before = s.digest()
        with self.assertRaises(RuleError):
            s.set_doctrine("walls", "unsupported")
        with self.assertRaises(RuleError):
            s.reinforce("walls", [{"id": "x", "pos": [0, 0]}] * 15)
        with self.assertRaises(RuleError):
            s.execute({"kind": "move", "cell": [0, 0]})
        self.assertEqual(s.history, [])
        self.assertEqual(s.digest(), before)


if __name__ == "__main__":
    unittest.main()

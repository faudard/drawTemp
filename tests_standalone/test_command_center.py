"""Command center / contested route gameplay tests."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.siege_command import demo
from examples.siege_fronts import siege_session
from examples.siege_scenarios import siege_content
from sporebound.command_center import dashboard, handle
from sporebound.fronts import MultiFrontSession
from sporebound.model import RuleError


def actor(uid, cell=(3, 6)):
    return {"id": uid, "name": uid, "team": "player", "pos": list(cell)}


class CommandCenterTests(unittest.TestCase):
    def test_dashboard_is_pure_and_lists_awaited_fronts(self):
        session = siege_session(contested=True)
        session.send_reserves("walls", [actor("guard")])
        before = session.digest()
        board = dashboard(session)
        self.assertIn("STRATEGIC COMMAND  | turn 0", board)
        self.assertIn("walls", board)
        self.assertIn("throne", board)
        self.assertIn("convoy_1", board)
        self.assertIn("2 turn(s)", board)
        self.assertIn("player=4", board)
        self.assertEqual(before, session.digest())

    def test_ambush_requires_supply_rescue_and_replays(self):
        session = siege_session(seed=10, contested=True)
        session.set_doctrine("walls", "hold")
        session.send_reserves("walls", [actor("guard")])
        session.advance()
        order = session.logistics.convoy("convoy_1")
        self.assertTrue(order["stranded"])
        self.assertEqual(order["arrival"], 4)
        self.assertIn("RESCUE NEEDED", dashboard(session))
        self.assertEqual(session.logistics.ambushes[("reserve", "walls")]["charges"], 1)
        session.rescue_convoy("convoy_1")
        self.assertEqual(session.logistics.supplies["player"], 3)
        for _ in range(3):
            session.advance()
        self.assertEqual(session.logistics.in_transit, [])
        self.assertEqual(session.pending_reinforcements["walls"][0]["actors"][0]["id"],
                         "guard")
        events = [row["kind"] for row in session.timeline.events]
        self.assertEqual(events.count("convoy_ambushed"), 1)
        self.assertEqual(events.count("convoy_rescued"), 1)
        self.assertEqual(events.count("convoy_arrived"), 1)
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_escort_prevents_ambush_and_is_nonrefundable(self):
        s = siege_session(contested=True)
        s.send_reserves("walls", [actor("shield")])
        s.escort_convoy("convoy_1")
        self.assertEqual(s.logistics.escorts, 0)
        with self.assertRaises(RuleError):
            s.escort_convoy("convoy_1")
        s.advance()
        self.assertNotIn("RESCUE NEEDED", dashboard(s))
        self.assertEqual(s.logistics.ambushes[("reserve", "walls")]["charges"], 2)
        s.advance()
        self.assertEqual(s.logistics.in_transit, [])
        events = [row["kind"] for row in s.timeline.events]
        self.assertIn("ambush_prevented", events)
        self.assertNotIn("convoy_ambushed", events)
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_unescorted_single_scout_is_lost_in_ambush(self):
        s = siege_session(contested=True)
        s.execute({"kind": "start_battle"})
        s.transfer_units("courtyard", {"supply_scout": [3, 6]})
        s.advance()
        self.assertFalse(s.logistics.in_transit)
        self.assertEqual([event["reason"] for event in s.timeline.events
                          if event["kind"] == "convoy_lost"], ["ambush"])
        with self.assertRaises(RuleError):
            s.rescue_convoy("convoy_1")
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_two_person_rescue_keeps_surviving_actor_identity(self):
        s = siege_session(contested=True)
        s.execute({"kind": "start_battle"})
        s.transfer_units("courtyard", {"supply_outrider": [3, 6],
                                       "supply_scout": [3, 7]})
        s.advance()
        convoy = s.logistics.convoy("convoy_1")
        self.assertEqual([u["id"] for u in convoy["actors"]], ["supply_outrider"])
        s.rescue_convoy("convoy_1")
        for _ in range(3):
            s.advance()
        self.assertEqual(len(s.pending_reinforcements["courtyard"][0]["actors"]), 1)
        self.assertEqual(MultiFrontSession.replay(s.recording()).state(), s.state())

    def test_supply_shortage_does_not_spend_reserves_or_modify_journal(self):
        s = siege_session(contested=True)
        s.logistics.supplies["player"] = 0
        before = s.digest()
        with self.assertRaises(RuleError):
            s.send_reserves("walls", [actor("guard")])
        self.assertEqual(s.digest(), before)
        self.assertEqual(s.logistics.reserves["player"], 3)
        self.assertEqual(s.logistics.in_transit, [])

    def test_commands_and_verified_checkpoint_roundtrip(self):
        s = siege_session(contested=True)
        original = s.digest()
        next_s, message, _ = handle(s, "status")
        self.assertEqual(next_s.digest(), original)
        self.assertIn("FRONTS", message)
        s, _, _ = handle(s, 'tactical {"kind":"start_battle"}')
        s, _, _ = handle(s, "doctrine walls hold")
        s, message, _ = handle(s, "reserve walls demo 3 6")
        self.assertIn("convoy_1", message)
        s, _, _ = handle(s, "turn")
        self.assertIn("RESCUE NEEDED", dashboard(s))
        s, _, _ = handle(s, "rescue convoy_1")
        with TemporaryDirectory() as tmp:
            destination = Path(tmp) / "checkpoints" / "siege.json"
            s, message, _ = handle(s, "save " + str(destination))
            self.assertTrue(destination.exists())
            self.assertIn("Verified", message)
            previous = s.digest()
            s, _, _ = handle(s, "turn 2")
            restored, _, _ = handle(s, "load " + str(destination))
            self.assertEqual(restored.digest(), previous)
            self.assertEqual(restored.recording()["version"], 4)
            self.assertEqual(MultiFrontSession.replay(restored.recording()).digest(),
                             restored.digest())
        _, _, should_quit = handle(restored, "quit")
        self.assertTrue(should_quit)

    def test_invalid_hazards_rollback_and_authoring_rejection(self):
        s = siege_session(contested=True)
        s.send_reserves("walls", [actor("guard")])
        before = s.digest()
        with self.assertRaises(RuleError):
            s.rescue_convoy("convoy_1")
        self.assertEqual(s.digest(), before)
        routes = [{"from": "reserve", "to": "walls", "turns": 2}]
        config = {"routes": routes, "ambushes": [
            {"from": "reserve", "to": "walls", "casualties": 1,
             "delay": 1, "charges": 1}]}
        base = {"walls": "castle_ramparts"}
        bad = [
            {**config, "ambushes": config["ambushes"] * 2},
            {**config, "ambushes": [{**config["ambushes"][0], "delay": 0}]},
            {**config, "ambushes": [{**config["ambushes"][0], "charges": -1}]},
            {**config, "supplies": {"player": True}},
            {**config, "escorts": -1},
        ]
        for altered in bad:
            with self.subTest(altered=altered), self.assertRaises(RuleError):
                MultiFrontSession(siege_content(), base, "walls",
                                  logistics=altered)

    def test_demo_is_replayable(self):
        board = demo()
        self.assertIn("STRATEGIC COMMAND", board)
        self.assertIn("convoy_rescued", board)


if __name__ == "__main__":
    unittest.main()

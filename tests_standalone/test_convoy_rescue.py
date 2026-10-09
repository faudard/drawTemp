"""Playable convoy rescue: real Battle commands, strategic outcomes, and replay."""
from copy import deepcopy
import unittest

from examples.siege_fronts import siege_session
from examples.siege_scenarios import siege_content
from sporebound.command_center import dashboard, handle
from sporebound.fronts import MultiFrontSession
from sporebound.model import Content, RuleError


def survivor(uid):
    return {"id": uid, "name": uid, "team": "player", "pos": [3, 6]}


def stranded():
    session = siege_session(seed=4, contested=True)
    session.set_doctrine("walls", "hold")
    session.send_reserves("walls", [survivor("road_guard")])
    session.advance()
    assert session.logistics.convoy("convoy_1")["stranded"]
    return session


class ConvoyRescueTests(unittest.TestCase):
    def test_enter_real_rescue_battle_and_block_global_clock(self):
        s = stranded()
        rescue = s.start_rescue("convoy_1")
        self.assertEqual(rescue.mission.id, "castle_convoy_rescue")
        self.assertEqual(rescue.mission.protected_id, "rescue_wagon")
        self.assertIn("road_guard", [u["id"] for u in s.logistics.convoy("convoy_1")["actors"]])
        self.assertNotIn("road_guard", [u.id for u in rescue.units])
        self.assertEqual(s.timeline.turn, 1)
        before = s.digest()
        with self.assertRaises(RuleError):
            s.advance()
        with self.assertRaises(RuleError):
            s.switch("walls")
        with self.assertRaises(RuleError):
            s.execute({"kind": "end"})
        with self.assertRaises(RuleError):
            s.rescue_convoy("convoy_1")
        self.assertEqual(s.digest(), before)
        self.assertIn("RESCUE BATTLES", dashboard(s))
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), before)

    def test_real_tactical_victory_releases_convoy_and_salvages_supplies(self):
        s = stranded()
        initial_provisions = s.logistics.supplies["player"]
        s.start_rescue("convoy_1")
        for _ in range(80):
            if not s.rescue_battles:
                break
            battle = s.rescue_battles["convoy_1"]
            if battle.active_id == "rescue_leader" and not battle.active.acted:
                target = next((u for u in battle.units
                               if u.team == "enemy" and u.alive), None)
                if target is not None:
                    s.execute_rescue("convoy_1", {"kind": "act", "skill": "attack",
                                                  "cell": list(target.pos)})
                    continue
            s.execute_rescue("convoy_1", {"kind": "end"})
        self.assertEqual(s.rescue_outcomes.get("convoy_1"), "victory")
        self.assertEqual(s.rescue_battles, {})
        self.assertNotIn("stranded", s.logistics.convoy("convoy_1"))
        self.assertEqual(s.logistics.supplies["player"], initial_provisions + 1)
        self.assertIn("convoy_rescue_victory",
                      [e["kind"] for e in s.timeline.events])
        replay = MultiFrontSession.replay(s.recording())
        self.assertEqual(replay.state(), s.state())
        self.assertEqual(replay.digest(), s.digest())
        for _ in range(4):
            s.advance()
        self.assertEqual(len(s.pending_reinforcements["walls"]), 1)
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_defeat_on_protected_wagon_death_destroys_convoy(self):
        raw = siege_content().to_dict()
        rescue = next(m for m in raw["missions"] if m["id"] == "castle_convoy_rescue")
        wagon = next(u for u in rescue["units"] if u["id"] == "rescue_wagon")
        wagon["hp"] = 1
        bandit = next(u for u in rescue["units"] if u["id"] == "road_bandit")
        bandit["pos"] = [4, 3]
        bandit["speed"] = 100
        bandit["attack"] = 50
        base = siege_session(contested=True)
        s = MultiFrontSession(
            Content.from_dict(raw), base.missions, "supplies",
            seed=base.seed, rules=base.rules, specs=base.initial_specs,
            links=base.links, logistics=base.initial_logistics)
        s.set_doctrine("walls", "hold")
        s.send_reserves("walls", [survivor("road_guard")])
        s.advance()
        battle = s.start_rescue("convoy_1")
        self.assertEqual(battle.active_id, "road_bandit")
        s.execute_rescue("convoy_1", {"kind": "act", "skill": "attack",
                                     "cell": [3, 3]})
        self.assertEqual(s.rescue_outcomes["convoy_1"], "defeat")
        self.assertFalse(s.logistics.in_transit)
        self.assertNotIn("walls", s.pending_reinforcements)
        self.assertIn("convoy_rescue_defeat",
                      [e["kind"] for e in s.timeline.events])
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_voluntary_abandonment_loses_transit_units_and_frees_capacity(self):
        for started in (False, True):
            with self.subTest(started=started):
                s = stranded()
                if started:
                    s.start_rescue("convoy_1")
                s.abandon_convoy("convoy_1")
                self.assertFalse(s.logistics.in_transit)
                self.assertFalse(s.rescue_battles)
                self.assertEqual(s.rescue_outcomes["convoy_1"], "abandoned")
                self.assertEqual(s.timeline.turn, 1)
                s.advance()
                self.assertEqual(MultiFrontSession.replay(s.recording()).digest(),
                                 s.digest())

    def test_invalid_authoring_and_illegal_actions_are_atomic(self):
        raw = siege_content().to_dict()
        base = siege_session(contested=True)
        for bad_mid in ("unknown", "castle_supply"):
            config = {**base.initial_logistics, "rescue_mission": bad_mid}
            with self.subTest(mission=bad_mid), self.assertRaises(RuleError):
                MultiFrontSession(Content.from_dict(raw), base.missions, "supplies",
                                  logistics=config)
        s = stranded()
        before = s.digest()
        with self.assertRaises(RuleError):
            s.start_rescue("missing")
        with self.assertRaises(RuleError):
            s.execute_rescue("convoy_1", {"kind": "end"})
        self.assertEqual(before, s.digest())
        s.start_rescue("convoy_1")
        before = s.digest()
        with self.assertRaises(RuleError):
            s.start_rescue("convoy_1")
        with self.assertRaises(RuleError):
            s.execute_rescue("convoy_1", {"kind": "bogus"})
        self.assertEqual(s.digest(), before)

    def test_command_center_runs_skirmish_and_replays_at_mid_battle(self):
        s = stranded()
        s, msg, _ = handle(s, "skirmish convoy_1")
        self.assertIn("RESCUE BATTLES", msg)
        before = s.digest()
        s, msg, _ = handle(s, 'rescue-act convoy_1 {"kind": "end"}')
        self.assertEqual(len(s.history), 5)  # doctrine, reserve, advance, start, action
        self.assertNotEqual(before, s.digest())
        self.assertEqual(MultiFrontSession.replay(s.recording()).state(), s.state())
        s, msg, _ = handle(s, "abandon convoy_1")
        self.assertIn("RESCUE RESULTS", msg)
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_tampered_rescue_command_or_out_of_band_mutation_is_detected(self):
        s = stranded()
        s.start_rescue("convoy_1")
        s.execute_rescue("convoy_1", {"kind": "end"})
        recording = s.recording()
        tampered = deepcopy(recording)
        tampered["operations"][-1]["command"] = {"kind": "act",
                                                   "skill": "attack", "cell": [2, 2]}
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(tampered)
        s.rescue_battles["convoy_1"].unit("rescue_wagon").hp -= 1
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(s.recording())


if __name__ == "__main__":
    unittest.main()

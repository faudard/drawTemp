"""Nonbinary strategic convoy choices and playable raider pursuit."""
from copy import deepcopy
import unittest

from examples.siege_fronts import siege_session
from examples.siege_scenarios import siege_content
from sporebound.command_center import handle, dashboard
from sporebound.fronts import MultiFrontSession
from sporebound.model import Content, RuleError


def stranded(*, seed=4, troops=1):
    session = siege_session(seed=seed, contested=True, decisions=True)
    session.set_doctrine("walls", "hold")
    session.send_reserves("walls", [
        {"id": "route_hero_" + str(i), "name": "Route Hero",
         "team": "player", "pos": [3+i, 6]}
        for i in range(troops)])
    session.advance()
    assert session.logistics.convoy("convoy_1")["stranded"]
    return session


def finish_pursuit(session):
    """Use normal tactical commands to defeat the bounded pursuit encounter."""
    for _ in range(100):
        if not session.pursuit_battles:
            break
        battle = session.pursuit_battles["convoy_1"]
        if battle.active_id == "pursuit_ranger" and not battle.active.acted:
            enemy = next((u for u in battle.units if u.team == "enemy" and u.alive),
                         None)
            if enemy is not None:
                session.execute_pursuit("convoy_1", {
                    "kind": "act", "skill": "attack", "cell": list(enemy.pos)})
                continue
        session.execute_pursuit("convoy_1", {"kind": "end"})


class ConvoyChoicesTests(unittest.TestCase):
    def test_crew_evacuation_preserves_units_but_loses_cargo(self):
        session = stranded()
        self.assertEqual(session.logistics.convoy("convoy_1")["cargo"], 2)
        before_supplies = session.logistics.supplies["player"]
        session.evacuate_convoy("convoy_1")
        order = session.logistics.convoy("convoy_1")
        self.assertNotIn("stranded", order)
        self.assertEqual(order["cargo"], 0)
        self.assertEqual(order["arrival"], 4)
        self.assertEqual(session.rescue_outcomes["convoy_1"], "evacuated")
        self.assertEqual(session.pursuit_targets["convoy_1"]["loot"], 2)
        self.assertEqual(session.logistics.supplies["player"], before_supplies)
        self.assertEqual(len(order["actors"]), 1)
        for _ in range(3):
            session.advance()
        self.assertEqual(
            session.pending_reinforcements["walls"][0]["actors"][0]["id"],
            "route_hero_0")
        self.assertEqual(MultiFrontSession.replay(session.recording()).state(),
                         session.state())

    def test_evacuate_during_active_battle_preserves_replay(self):
        session = stranded()
        session.start_rescue("convoy_1")
        session.execute_rescue("convoy_1", {"kind": "end"})
        session.evacuate_convoy("convoy_1")
        self.assertFalse(session.rescue_battles)
        self.assertIn("convoy_1", session.pursuit_targets)
        session.advance()
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_ransom_preserves_cargo_at_resource_cost(self):
        session = stranded()
        before = session.digest()
        with self.assertRaises(RuleError):
            session.negotiate_convoy("convoy_1")
        self.assertEqual(session.digest(), before)
        session.start_rescue("convoy_1")
        session.execute_rescue("convoy_1", {"kind": "end"})
        stock = session.logistics.supplies["player"]
        session.negotiate_convoy("convoy_1")
        self.assertEqual(session.logistics.supplies["player"], stock - 2)
        self.assertEqual(session.logistics.convoy("convoy_1")["cargo"], 2)
        self.assertEqual(session.rescue_outcomes["convoy_1"], "negotiated")
        self.assertFalse(session.pursuit_targets)
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_salvage_requires_defeated_raider_and_keeps_half_cargo(self):
        session = stranded(troops=2)
        session.start_rescue("convoy_1")
        before = session.digest()
        with self.assertRaises(RuleError):
            session.salvage_convoy("convoy_1")
        self.assertEqual(session.digest(), before)
        for _ in range(100):
            battle = session.rescue_battles["convoy_1"]
            enemies = [u for u in battle.units if u.team == "enemy"]
            if any(not u.alive for u in enemies):
                break
            if battle.active_id == "rescue_leader" and not battle.active.acted:
                target = next(u for u in enemies if u.alive)
                session.execute_rescue("convoy_1", {
                    "kind": "act", "skill": "attack", "cell": list(target.pos)})
            else:
                session.execute_rescue("convoy_1", {"kind": "end"})
        self.assertTrue(session.rescue_battles)
        supplies = session.logistics.supplies["player"]
        session.salvage_convoy("convoy_1")
        self.assertEqual(session.rescue_outcomes["convoy_1"], "partial")
        self.assertEqual(session.logistics.supplies["player"], supplies + 2)
        self.assertEqual(session.logistics.convoy("convoy_1")["cargo"], 2)
        self.assertEqual(session.pursuit_targets["convoy_1"]["loot"], 2)
        self.assertFalse(session.rescue_battles)
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_playable_pursuit_recovers_loot_and_weakens_next_front(self):
        session = stranded()
        session.evacuate_convoy("convoy_1")
        baseline_supplies = session.logistics.supplies["player"]
        baseline_opposition = session.timeline.fronts["walls"]["opposition"]
        battle = session.start_pursuit("convoy_1")
        self.assertEqual(battle.mission.id, "castle_convoy_pursuit")
        self.assertIn("PURSUIT BATTLES", dashboard(session))
        with self.assertRaises(RuleError):
            session.advance()
        finish_pursuit(session)
        self.assertEqual(session.pursuit_outcomes["convoy_1"], "victory")
        self.assertEqual(session.logistics.supplies["player"], baseline_supplies + 2)
        self.assertEqual(session.timeline.fronts["walls"]["opposition"],
                         baseline_opposition - 1)
        self.assertFalse(session.pursuit_targets)
        self.assertFalse(session.pursuit_battles)
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_abandon_pursuit_retains_crew_but_forfeits_loot(self):
        session = stranded()
        session.evacuate_convoy("convoy_1")
        session.start_pursuit("convoy_1")
        session.execute_pursuit("convoy_1", {"kind": "end"})
        session.abandon_pursuit("convoy_1")
        self.assertEqual(session.pursuit_outcomes["convoy_1"], "abandoned")
        self.assertFalse(session.pursuit_targets)
        self.assertFalse(session.pursuit_battles)
        session.advance()
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_partial_choices_strictly_opt_in_and_version4_old_still_replays(self):
        legacy = siege_session(contested=True)
        legacy_digest = legacy.digest()
        with self.assertRaises(RuleError):
            legacy.evacuate_convoy("convoy_1")
        self.assertEqual(legacy.recording()["version"], 4)
        self.assertEqual(MultiFrontSession.replay(legacy.recording()).digest(),
                         legacy_digest)
        base = siege_session(contested=True, decisions=True)
        options = base.initial_logistics
        for altered in (
            {**options, "choices": {"ransom": True,
                                    "pursuit_mission": "castle_convoy_pursuit",
                                    "pursuit_reward": 2}},
            {**options, "choices": {"ransom": 2,
                                    "pursuit_mission": "missing",
                                    "pursuit_reward": 2}},
            {**options, "choices": {"ransom": 2,
                                    "pursuit_mission": "castle_supply",
                                    "pursuit_reward": 2}},
            {**options, "choices": {"ransom": 0,
                                    "pursuit_mission": "castle_convoy_pursuit",
                                    "pursuit_reward": 2}},
        ):
            with self.subTest(altered=altered), self.assertRaises(RuleError):
                MultiFrontSession(siege_content(), base.missions, "supplies",
                                  logistics=altered)

    def test_cli_and_replay_tamper(self):
        session = stranded()
        session, response, _ = handle(session, "evacuate convoy_1")
        self.assertIn("RECOVERABLE LOOT", response)
        session, response, _ = handle(session, "pursue convoy_1")
        self.assertIn("PURSUIT BATTLES", response)
        session, _, _ = handle(session, 'pursuit-act convoy_1 {"kind":"end"}')
        rec = session.recording()
        self.assertEqual(MultiFrontSession.replay(rec).digest(),
                         session.digest())
        corrupt = deepcopy(rec)
        corrupt["operations"][-1]["command"] = {"kind": "bogus"}
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(corrupt)
        session, _, _ = handle(session, "giveup-pursuit convoy_1")
        self.assertEqual(session.pursuit_outcomes["convoy_1"], "abandoned")
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())


if __name__ == "__main__":
    unittest.main()

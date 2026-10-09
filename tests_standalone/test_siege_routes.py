"""Multi-route campaigns: direct storm, sewer infiltration and earned recovery."""
from copy import deepcopy
import unittest

from examples.siege_fronts import siege_session, SIEGE_CAMPAIGN_PATHS
from examples.siege_routes_demo import demo as three_routes_demo
from examples.siege_scenarios import siege_content
from sporebound.command_center import dashboard, handle
from sporebound.fronts import MultiFrontSession
from sporebound.model import Content, RuleError


def session_with_easy_side_encounters():
    raw = siege_content().to_dict()
    for mission in raw["missions"]:
        if mission["id"] in {"castle_tunnels", "castle_gate_recovery"}:
            for unit in mission["units"]:
                if unit["team"] == "enemy":
                    unit["hp"] = 1
                    unit["max_hp"] = 1
        if mission["id"] == "castle_throne":
            mission["units"] = [u for u in mission["units"]
                                if u["id"] in {"captain", "engineer", "castellan"}]
            boss = next(u for u in mission["units"] if u["id"] == "castellan")
            boss.update(pos=[2, 3], hp=1, max_hp=1, speed=5)
    template = siege_session(contested=True, campaign=True, paths=True)
    return MultiFrontSession(Content.from_dict(raw), template.missions,
           "supplies", seed=3, specs=template.initial_specs, links=template.links,
           logistics=template.initial_logistics, campaign=SIEGE_CAMPAIGN_PATHS)


def play_small_battle(session, *, front, recovery=False):
    if recovery:
        battle = session.start_recovery(front)
    else:
        session.switch(front)
        session.execute({"kind": "start_battle"})
        battle = session.active
    for _ in range(100):
        if recovery:
            if front not in session.recovery_battles:
                break
            battle = session.recovery_battles[front]
        else:
            if session.active.result is not None:
                break
            battle = session.active
        ranged_id = "relief_captain" if recovery else "tunnel_sapper"
        if battle.active_id == ranged_id and not battle.active.acted:
            opponent = next((u for u in battle.units
                             if u.team == "enemy" and u.alive), None)
            if opponent:
                cmd = {"kind": "act", "skill": "attack",
                       "cell": list(opponent.pos)}
                if recovery:
                    session.execute_recovery(front, cmd)
                else:
                    session.execute(cmd)
                continue
        if recovery:
            session.execute_recovery(front, {"kind": "end"})
        else:
            session.execute({"kind": "end"})
    return session.recovery_outcomes.get(front) if recovery else session.active.result


class SiegeRoutesTests(unittest.TestCase):
    def test_three_paths_have_replayable_final_boss_victory(self):
        results = three_routes_demo()
        self.assertEqual(set(results), {
            "direct", "tunnels", "recaptured_gate"})
        self.assertTrue(all(result["status"] == "victory"
                            for result in results.values()))
        self.assertLess(results["direct"]["supplies"],
                        results["tunnels"]["supplies"])

    def test_legacy_campaign_remains_identical_without_opt_in(self):
        s = siege_session(contested=True, campaign=True)
        self.assertIsNone(s.route_policy)
        self.assertEqual(s.recording()["version"], 5)
        self.assertNotIn("route", s.state()["campaign"])
        with self.assertRaises(RuleError):
            s.select_route("direct")
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_direct_route_cost_paid_once_and_unlocks_throne(self):
        s = session_with_easy_side_encounters()
        before = s.digest()
        with self.assertRaises(RuleError):
            s.switch("throne")
        with self.assertRaises(RuleError):
            s.select_route("unknown")
        self.assertEqual(s.digest(), before)
        s.select_route("direct")
        self.assertEqual(s.logistics.supplies["player"], 2)
        self.assertEqual(s.timeline.fronts["throne"]["strength"], 3)
        self.assertTrue(s.route_locked)
        self.assertTrue(s.state()["campaign"]["unlocked"])
        for _ in range(2):
            with self.assertRaises(RuleError):
                s.select_route("direct")
            self.assertEqual(s.logistics.supplies["player"], 2)
        s.switch("throne")
        s.execute({"kind": "start_battle"})
        s.execute({"kind": "act", "skill": "attack", "cell": [2, 3]})
        self.assertEqual(s.state()["campaign"]["status"], "victory")
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_tunnels_route_requires_real_battle_victory(self):
        s = session_with_easy_side_encounters()
        s.select_route("tunnels")
        self.assertEqual(s.logistics.supplies["player"], 4)
        self.assertEqual(s.timeline.fronts["throne"]["strength"], 5)
        with self.assertRaises(RuleError):
            s.switch("throne")
        result = play_small_battle(s, front="tunnels")
        self.assertEqual(result, "victory")
        self.assertTrue(s.state()["campaign"]["unlocked"])
        s.switch("throne")
        self.assertEqual(MultiFrontSession.replay(s.recording()).state(), s.state())

    def test_long_strategic_clock_cannot_fake_tunnel_or_throne_victory(self):
        s = session_with_easy_side_encounters()
        s.set_doctrine("tunnels", "assault")
        s.set_doctrine("throne", "assault")
        for _ in range(20):
            s.advance()
        self.assertEqual(s.timeline.fronts["tunnels"]["status"], "active")
        self.assertEqual(s.timeline.fronts["throne"]["status"], "active")
        s.select_route("tunnels")
        self.assertFalse(s.state()["campaign"]["unlocked"])
        with self.assertRaises(RuleError):
            s.switch("throne")
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_treaty_requires_authentic_supply_intelligence(self):
        s = session_with_easy_side_encounters()
        s.switch("gate")
        s.execute({"kind": "start_battle"})
        before = s.digest()
        with self.assertRaises(RuleError):
            s.negotiate_front("gate")
        self.assertEqual(s.digest(), before)
        s.switch("supplies")
        s.execute({"kind": "start_battle"})
        s.execute({"kind": "interact", "object": "supply_cache"})
        s.execute({"kind": "end"})
        s.switch("gate")
        s.negotiate_front("gate")
        self.assertEqual(s.timeline.fronts["gate"]["status"], "negotiated")
        self.assertIn("cut_supply_route", s.applied_links)
        self.assertEqual(s.logistics.supplies["player"], 3)
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_retake_withdrawn_gate_via_playable_counterattack(self):
        s = session_with_easy_side_encounters()
        s.switch("gate")
        s.execute({"kind": "start_battle"})
        s.withdraw_front("gate")
        self.assertEqual(s.state()["campaign"]["status"], "blocked")
        before = s.logistics.supplies["player"]
        result = play_small_battle(s, front="gate", recovery=True)
        self.assertEqual(result, "victory")
        self.assertEqual(s.timeline.fronts["gate"]["status"], "reclaimed")
        self.assertEqual(s.timeline.fronts["gate"]["strength"], 10)
        self.assertEqual(s.logistics.supplies["player"], before - 1)
        self.assertEqual(s.timeline.fronts["throne"]["strength"], 6)
        self.assertEqual(s.state()["campaign"]["status"], "in_progress")
        self.assertEqual(s.recovery_outcomes["gate"], "victory")
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_failed_counterattack_spends_supplies_without_fake_recapture(self):
        raw = siege_content().to_dict()
        mission = next(m for m in raw["missions"]
                       if m["id"] == "castle_gate_recovery")
        mission["units"] = [
            {"id": "relief_captain", "name": "Relief Captain",
             "team": "player", "pos": [1, 3], "hp": 1},
            {"id": "occupying_sergeant", "name": "Occupying Sergeant",
             "team": "enemy", "pos": [2, 3], "speed": 100,
             "attack": 80, "weapon_power": 50},
        ]
        template = siege_session(contested=True, campaign=True, paths=True)
        s = MultiFrontSession(Content.from_dict(raw), template.missions,
                  "supplies", seed=3, specs=template.initial_specs,
                  links=template.links, logistics=template.initial_logistics,
                  campaign=SIEGE_CAMPAIGN_PATHS)
        s.switch("gate")
        s.execute({"kind": "start_battle"})
        s.withdraw_front("gate")
        supplies = s.logistics.supplies["player"]
        s.start_recovery("gate")
        self.assertEqual(s.recovery_battles["gate"].active_id,
                         "occupying_sergeant")
        s.execute_recovery("gate", {
            "kind": "act", "skill": "attack", "cell": [1, 3]})
        self.assertEqual(s.recovery_outcomes["gate"], "defeat")
        self.assertEqual(s.timeline.fronts["gate"]["status"], "withdrawn")
        self.assertEqual(s.logistics.supplies["player"], supplies - 1)
        self.assertFalse(s.recovery_battles)
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_mid_counterattack_checkpoint_and_abandon(self):
        s = session_with_easy_side_encounters()
        s.switch("gate")
        s.execute({"kind": "start_battle"})
        s.withdraw_front("gate")
        s.start_recovery("gate")
        before = s.digest()
        for action in (lambda: s.advance(), lambda: s.switch("courtyard"),
                       lambda: s.execute({"kind": "end"})):
            with self.assertRaises(RuleError):
                action()
        self.assertEqual(s.digest(), before)
        s.execute_recovery("gate", {"kind": "end"})
        self.assertEqual(MultiFrontSession.replay(s.recording()).state(), s.state())
        s.abandon_recovery("gate")
        self.assertEqual(s.recovery_outcomes["gate"], "abandoned")
        self.assertEqual(s.timeline.fronts["gate"]["status"], "withdrawn")
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_recovery_is_not_free_or_repeatable_with_same_status(self):
        s = session_with_easy_side_encounters()
        s.switch("gate")
        s.execute({"kind": "start_battle"})
        s.withdraw_front("gate")
        s.logistics.supplies["player"] = 0
        before = s.digest()
        with self.assertRaises(RuleError):
            s.start_recovery("gate")
        self.assertEqual(s.digest(), before)
        s.logistics.supplies["player"] = 2
        play_small_battle(s, front="gate", recovery=True)
        after = s.digest()
        with self.assertRaises(RuleError):
            s.start_recovery("gate")
        self.assertEqual(s.digest(), after)
        # Direct changes to resources intentionally have no replay journal.
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(s.recording())

    def test_cli_route_and_counterattack_are_journaled(self):
        s = session_with_easy_side_encounters()
        s, msg, _ = handle(s, "route tunnels")
        self.assertIn("ROUTE tunnels", msg)
        with self.assertRaises(RuleError):
            handle(s, "route direct")
        s, msg, _ = handle(s, "focus tunnels")
        self.assertIn("tunnels", msg)
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(),
                         s.digest())

    def test_reject_malformed_policy_and_detect_tamper(self):
        template = siege_session(contested=True, campaign=True, paths=True)
        invalid = []
        for mutate in (
            lambda p: p["routes"]["direct"].update(supplies=0),
            lambda p: p["routes"]["tunnels"]["required"].update(tunnels=["active"]),
            lambda p: p["treaties"]["gate"].update(object="missing"),
            lambda p: p["recovery"]["gate"].update(mission="missing"),
            lambda p: p["recovery"]["gate"].update(supplies=True),
        ):
            spec = deepcopy(SIEGE_CAMPAIGN_PATHS)
            mutate(spec)
            invalid.append(spec)
        for spec in invalid:
            with self.subTest(spec=spec), self.assertRaises(RuleError):
                MultiFrontSession(siege_content(), template.missions,
                                  "supplies", campaign=spec)
        s = session_with_easy_side_encounters()
        r = s.recording()
        tampered = deepcopy(r)
        tampered["campaign"]["routes"]["direct"]["strength_loss"] = 3
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(tampered)


if __name__ == "__main__":
    unittest.main()

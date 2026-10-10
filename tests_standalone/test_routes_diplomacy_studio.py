"""2.5.4.4 campaign route and treaty authoring against real engine contracts."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.siege_fronts import SIEGE_CAMPAIGN, SIEGE_CAMPAIGN_PATHS, siege_session
from examples.siege_scenarios import siege_content
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import RuleError
from sporebound.player_controller import PlayerController
from sporebound.routes_authoring import (
    counteroffensive, delete_choice, delete_counteroffensive,
    delete_recovery, delete_route, delete_treaty, disable, enable,
    negotiation, partial, preview, recovery, retreat, route, treaty)
from sporebound.siege_authoring import replace_siege, validate_blueprint, make_session


class RoutesDiplomacyAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = siege_content()
        cls.reference = siege_session(contested=True, campaign=True, paths=True)

    def blueprint(self):
        s = self.reference
        return {"id": "castle_routes", "campaign_id": "main",
                "fronts": deepcopy(s.missions), "focused": "supplies",
                "specs": deepcopy(s.initial_specs),
                "links": deepcopy(s.links),
                "logistics": deepcopy(s.initial_logistics),
                "campaign": deepcopy(SIEGE_CAMPAIGN)}

    def project(self, bp):
        project = GameProject(campaigns=[
            {"id": "main", "name": "Château", "description": "",
             "start_mission": "castle_supply"}])
        return replace_siege(project, self.content, bp)

    def configured(self):
        bp = enable(self.blueprint(), self.content)
        # The authored castle scenario makes the shortcut costly on purpose.
        bp = route(bp, self.content, "direct", {}, 3, 4)
        bp = route(bp, self.content, "tunnels",
                   {"tunnels": ["victory"]}, 1, 2)
        bp = recovery(bp, self.content, "gate", "castle_gate_recovery",
                      1, 1, 2)
        bp = counteroffensive(bp, self.content, "gate", 5,
                              "castle_gate_recovery", 2, 3)
        bp = treaty(bp, self.content, "gate", "supplies", "interact",
                    "supply_cache", ["royal_guard_left"])
        return bp

    def test_create_routes_and_options_then_match_live_contract(self):
        bp = self.configured()
        project = self.project(bp)
        self.assertEqual(project.sieges[0], bp)
        session = make_session(bp, self.content, seed=3)
        self.assertEqual(set(session.route_policy.routes),
                         {"breach", "direct", "tunnels"})
        self.assertEqual(session.route_policy.counteroffensives["gate"]["after_turn"], 5)
        self.assertEqual(session.route_policy.treaties["gate"]["final_stand_down"],
                         ["royal_guard_left"])
        plan = preview(bp, self.content)
        self.assertTrue(plan["locked"])
        self.assertEqual(plan["available"], ["breach", "direct", "tunnels"])
        self.assertEqual(plan["counteroffensives"], ["gate"])
        self.assertEqual(type(session).replay(session.recording()).digest(),
                         session.digest())

    def test_direct_route_does_not_fake_victory_and_charges_once(self):
        bp = self.configured()
        session = make_session(bp, self.content, seed=3)
        initial = session.digest()
        with self.assertRaises(RuleError):
            session.switch("throne")
        self.assertEqual(session.digest(), initial)
        session.select_route("direct")
        self.assertEqual(session.logistics.supplies["player"], 2)
        self.assertTrue(session.route_locked)
        self.assertEqual(session.timeline.fronts["throne"]["strength"], 3)
        self.assertTrue(session.state()["campaign"]["unlocked"])
        with self.assertRaises(RuleError):
            session.select_route("direct")
        session.switch("throne")
        self.assertIsNone(session.active.result)
        self.assertEqual(type(session).replay(session.recording()).digest(),
                         session.digest())

    def test_contract_rejects_invalid_policies_transactionally(self):
        bp = self.configured()
        saved = deepcopy(bp)
        invalid = (
            lambda: route(bp, self.content, "direct", {}, 0, 0),
            lambda: route(bp, self.content, "tunnels", {"throne": ["victory"]}, 1, 2),
            lambda: route(bp, self.content, "tunnels", {"missing": ["victory"]}, 1, 2),
            lambda: route(bp, self.content, "tunnels", {"tunnels": ["defeat"]}, 1, 2),
            lambda: treaty(bp, self.content, "gate", "supplies",
                           "interact", "not_real", ["royal_guard_left"]),
            lambda: treaty(bp, self.content, "gate", "supplies",
                           "interact", "supply_cache", ["not_an_enemy"]),
            lambda: recovery(bp, self.content, "gate", "missing", 1, 1, 2),
            lambda: counteroffensive(bp, self.content, "throne", 0,
                                    "castle_gate_recovery", 2, 3),
            lambda: delete_route(bp, self.content, "breach"),
            lambda: delete_recovery(bp, self.content, "gate"),
        )
        for action in invalid:
            with self.subTest(action=action), self.assertRaises(RuleError):
                action()
            self.assertEqual(bp, saved)

    def test_objective_negotiation_and_retreat_are_real_effects(self):
        bp = self.blueprint()
        bp = negotiation(bp, self.content, "gate", 3, "throne", 1)
        bp = partial(bp, self.content, "courtyard",
                     "defense_sabotaged", "stone_drop", 1, "throne", 2)
        bp = retreat(bp, self.content, "gate", "courtyard", 2)
        spec = bp["campaign"]
        self.assertEqual(spec["negotiation"]["gate"]["supplies"], 3)
        self.assertEqual(spec["partial"]["courtyard"]["object"], "stone_drop")
        self.assertEqual(spec["retreat"]["gate"]["target_loss"], 2)
        bp = delete_choice(bp, self.content, "partial", "courtyard")
        self.assertEqual(bp["campaign"]["partial"], {})
        with self.assertRaises(RuleError):
            partial(bp, self.content, "courtyard",
                    "interact", "not_real", 1, "throne", 2)

    def test_disable_and_delete_do_not_leave_dangling_rules(self):
        bp = self.configured()
        bp = delete_treaty(bp, self.content, "gate")
        bp = delete_counteroffensive(bp, self.content, "gate")
        bp = delete_recovery(bp, self.content, "gate")
        bp = delete_route(bp, self.content, "tunnels")
        self.assertEqual(sorted(bp["campaign"]["routes"]), ["breach", "direct"])
        bp = disable(bp, self.content)
        self.assertEqual(set(bp["campaign"]),
                         {"final_front", "required_fronts", "partial",
                          "negotiation", "retreat"})
        self.assertIsNone(make_session(bp, self.content).route_policy)

    def test_game_session_player_replay_choice_and_payment(self):
        bp = self.configured()
        project = self.project(bp)
        with TemporaryDirectory() as folder:
            profile = Path(folder) / "castle.game.json"
            player = PlayerController(self.content, project, profile)
            player.new_game("main", 1, seed=3)
            for mid in bp["fronts"].values():
                if mid not in player.session.progress.unlocked:
                    player.session.progress.unlocked.append(mid)
            player.save()
            player.start_configured_siege("castle_routes")
            with self.assertRaises(RuleError):
                player.switch_front("throne")
            player.select_route("direct")
            player.switch_front("throne")
            self.assertEqual(player.session.fronts.route_selected, "direct")
            self.assertTrue(player.session.fronts.route_locked)
            resumed = PlayerController(self.content, project, profile)
            session = resumed.load_game("main", 1)
            self.assertEqual(session.recording(), player.session.recording())
            self.assertEqual(session.fronts.logistics.supplies["player"], 2)
            self.assertIsNone(session.active_battle.result)

    def test_recovery_combat_stays_a_real_battle_after_player_resume(self):
        project = self.project(self.configured())
        with TemporaryDirectory() as folder:
            profile = Path(folder) / "recovery.game.json"
            ui = PlayerController(self.content, project, profile)
            ui.new_game("main", 1, seed=3)
            for mid in project.sieges[0]["fronts"].values():
                if mid not in ui.session.progress.unlocked:
                    ui.session.progress.unlocked.append(mid)
            ui.save()
            ui.start_configured_siege("castle_routes")
            ui.switch_front("gate")
            ui.execute({"kind": "start_battle"})
            ui.withdraw_front("gate")
            self.assertEqual(ui.session.fronts.timeline.fronts["gate"]["status"],
                             "withdrawn")
            ui.start_recovery("gate")
            self.assertEqual(ui.session.active_battle.mission.id,
                             "castle_gate_recovery")
            self.assertIn("gate", ui.session.fronts.recovery_battles)
            resumed = PlayerController(self.content, project, profile)
            restored = resumed.load_game("main", 1)
            self.assertEqual(restored.active_battle.mission.id,
                             "castle_gate_recovery")
            self.assertEqual(restored.recording(), ui.session.recording())
            resumed.execute({"kind": "end"})
            again = PlayerController(self.content, project, profile)
            again.load_game("main", 1)
            self.assertEqual(again.session.recording(), resumed.session.recording())

    def test_saved_blueprint_rejects_invalid_treaties_and_routes(self):
        bp = self.configured()
        broken = deepcopy(bp)
        broken["campaign"]["treaties"]["gate"]["object"] = "forged_evidence"
        with self.assertRaises(RuleError):
            validate_blueprint(broken, self.content, {"main"})
        broken = deepcopy(bp)
        broken["campaign"]["routes"]["direct"]["supplies"] = 0
        with self.assertRaises(RuleError):
            self.project(broken)


if __name__ == "__main__":
    unittest.main()

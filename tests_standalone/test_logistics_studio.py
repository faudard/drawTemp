"""2.5.4.3: canonical LogisticsDirector authoring, Player and replay gates."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from examples.siege_scenarios import siege_content
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.logistics_authoring import (
    configuration, delete_ambush, delete_route, disable, preview,
    rescue_mission, resources, upsert_ambush, upsert_route)
from sporebound.model import RuleError
from sporebound.player_controller import PlayerController
from sporebound.siege_authoring import (
    add_front, make_session, new_blueprint, remove_front, replace_siege)


class LogisticsStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = siege_content()

    def blueprint(self):
        bp = new_blueprint("siege_roads", "main", "castle_ram", front="gate")
        return add_front(bp, "walls", "castle_ramparts",
                         strength=8, opposition=12, doctrine="assault")

    def configured(self):
        bp = self.blueprint()
        bp = resources(bp, self.content, player_reserves=3, enemy_reserves=0,
                       capacity=4, player_supplies=6, enemy_supplies=0,
                       escorts=1)
        bp = upsert_route(bp, self.content, "reserve", "walls", 2)
        bp = upsert_route(bp, self.content, "walls", "gate", 1)
        bp = upsert_ambush(bp, self.content, "reserve", "walls",
                           casualties=0, delay=2, charges=1)
        return bp

    def project(self, bp):
        project = GameProject(campaigns=[
            {"id": "main", "name": "Château", "start_mission": "castle_ram",
             "description": ""}])
        return replace_siege(project, self.content, bp)

    def test_legacy_blueprints_unchanged_and_logistics_opt_in(self):
        old = self.blueprint()
        self.assertNotIn("logistics", old)
        self.assertIsNone(make_session(old, self.content).logistics)
        bp = self.configured()
        self.assertIn("logistics", bp)
        self.assertNotIn("logistics", disable(bp, self.content))
        self.assertEqual(old, disable(bp, self.content))
        restored = self.project(bp)
        self.assertEqual(restored.sieges[0], bp)
        self.assertEqual(preview(bp, self.content)["capacity"], 4)

    def test_route_ambush_resources_and_atomic_failures(self):
        bp = self.configured()
        saved = deepcopy(bp)
        self.assertEqual(len(configuration(bp)["routes"]), 2)
        self.assertEqual(len(configuration(bp)["ambushes"]), 1)
        for transform in (
            lambda: upsert_route(bp, self.content, "reserve", "unknown", 1),
            lambda: upsert_route(bp, self.content, "gate", "gate", 2),
            lambda: upsert_route(bp, self.content, "gate", "walls", 0),
            lambda: upsert_ambush(bp, self.content, "gate", "walls",
                                  casualties=1, delay=2, charges=1),
            lambda: upsert_ambush(bp, self.content, "reserve", "walls",
                                  casualties=15, delay=2, charges=1),
            lambda: delete_route(bp, self.content, "reserve", "walls"),
            lambda: remove_front(bp, "walls"),
            lambda: resources(bp, self.content, player_reserves=1,
                              enemy_reserves=0, capacity=0,
                              player_supplies=1, enemy_supplies=0, escorts=0),
            lambda: rescue_mission(bp, self.content, "not_a_mission")):
            with self.subTest(transform=transform), self.assertRaises(RuleError):
                transform()
            self.assertEqual(bp, saved)
        bp2 = delete_ambush(bp, self.content, "reserve", "walls")
        bp2 = delete_route(bp2, self.content, "reserve", "walls")
        self.assertEqual(len(bp2["logistics"]["routes"]), 1)
        self.assertEqual(len(bp2["logistics"]["ambushes"]), 0)

    def test_real_convoy_deterministic_replay_and_hazards(self):
        bp = self.configured()
        s = make_session(bp, self.content, seed=3)
        convoy = s.send_reserves("walls", [
            {"id": "shield_reserve", "name": "Shield Reserve",
             "team": "player", "pos": [3, 6]}])
        self.assertEqual(convoy, "convoy_1")
        self.assertEqual(s.logistics.reserves["player"], 2)
        self.assertEqual(s.logistics.supplies["player"], 5)
        s.advance()
        self.assertEqual(len(s.logistics.in_transit), 1)
        self.assertTrue(any(e["kind"] == "reserves_dispatched"
                            for e in s.timeline.events))
        self.assertEqual(type(s).replay(s.recording()).digest(), s.digest())

    def test_game_session_player_slot_and_logistics_identity(self):
        bp = self.configured()
        project = self.project(bp)
        with TemporaryDirectory() as folder:
            ui = PlayerController(
                self.content, project, Path(folder) / "siege.game.json")
            ui.new_game("main", 1, seed=9)
            self.assertFalse(ui.available_sieges()[0]["ready"])
            ui.session.progress.unlocked.append("castle_ramparts")
            ui.save()
            ui.start_configured_siege("siege_roads")
            self.assertEqual(ui.session.fronts.initial_logistics, bp["logistics"])
            cid = ui.send_reserves("walls", [
                {"id": "shield_reserve", "name": "Shield Reserve",
                 "team": "player", "pos": [3, 6]}])
            self.assertEqual(cid, "convoy_1")
            ui.advance_fronts()
            restored = PlayerController(
                self.content, project, Path(folder) / "siege.game.json")
            restored.load_game("main", 1)
            self.assertEqual(restored.session.recording(), ui.session.recording())
            self.assertEqual(restored.session.fronts.logistics.reserves["player"], 2)
            self.assertEqual(restored.session.siege_id, "siege_roads")

    def test_rescue_requires_compatible_tactical_mission(self):
        bp = self.configured()
        updated = rescue_mission(bp, self.content, "castle_convoy_rescue")
        self.assertEqual(updated["logistics"]["rescue_mission"],
                         "castle_convoy_rescue")
        self.assertEqual(make_session(updated, self.content).logistics.rescue_mission,
                         "castle_convoy_rescue")


if __name__ == "__main__":
    unittest.main()

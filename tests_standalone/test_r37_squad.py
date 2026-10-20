"""R37.D3 squad radio, bounded roles, transactional alerts and replay tests."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.ai_squad import coordinate_squad, validate_squad
from sporebound.advanced_ai import EXTENSION, MAX_WRITES
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.living_world import EXTENSION as WORLD_EXTENSION
from sporebound.model import RuleError
from tests_standalone.test_r37_perception import fixture as sensor_fixture, sensor, policy


def fixture():
    content, project = sensor_fixture()
    world = project.extensions[WORLD_EXTENSION]["data"]
    world["npcs"].extend([
        {"id": "guard", "schedule": [
            {"minute": 0, "scene": "arrival",
             "activity": "guard", "pos": [0, 0]}]},
        {"id": "scout", "schedule": [
            {"minute": 0, "scene": "arrival",
             "activity": "patrol", "pos": [1, 0]}]},
    ])
    agent = project.extensions[EXTENSION]["data"]["agents"][0]
    agent["squad"] = {"id": "castle_guard", "role": "flanker", "radio_range": 2}
    agents = project.extensions[EXTENSION]["data"]["agents"]
    agents.extend([
        {"id": "guard", "mode": "realtime", "sensor": sensor(
            facing="south", vision=5, hearing=0),
         "squad": {"id": "castle_guard", "role": "officer", "radio_range": 2},
         "policies": [policy(
            "patrol", "patrol", when={"squad_alert": False}, base=1),
            policy("coordinate", "coordinate",
                   when={"enemy_visible": True}, base=5)]},
        {"id": "scout", "mode": "realtime", "sensor": sensor(
            facing="north", vision=3, hearing=0),
         "squad": {"id": "castle_guard", "role": "vanguard", "radio_range": 2},
         "policies": [policy(
            "react", "protect", when={"squad_alert": True}, base=5)]},
    ])
    project.validate(content)
    return content, project


class SquadCoordinationTests(unittest.TestCase):
    def test_direct_alert_no_omniscience_or_multi_hop(self):
        content, project = fixture()
        game = GameSession.new(content, project, "main", seed=29)
        before = game.recording()
        report = game.ai_squad_preview("castle_guard")
        self.assertEqual(report["fresh_sources"], ["guard"])
        by_actor = {row["actor_id"]: row for row in report["members"]}
        self.assertEqual([row["actor_id"] for row in report["members"]],
                         ["guard", "scout", "traveler"])
        self.assertIsNone(by_actor["guard"]["shared_from"])
        self.assertEqual(by_actor["guard"]["intent"], "coordinate")
        self.assertEqual(by_actor["scout"]["shared_from"], "guard")
        self.assertEqual(by_actor["scout"]["received_signal"], "seen")
        self.assertEqual(by_actor["scout"]["known_pos"], [0, 1])
        self.assertTrue(by_actor["scout"]["reachable"])
        self.assertEqual(by_actor["scout"]["next_step"], [0, 0])
        self.assertIsNone(by_actor["traveler"]["shared_from"])
        self.assertIsNone(by_actor["traveler"]["known_pos"])
        self.assertEqual(by_actor["traveler"]["intent"], "patrol")
        self.assertEqual(game.recording(), before)
        self.assertEqual(report, game.ai_squad_preview("castle_guard"))
        scout_ctx = game.ai_decision_context("scout")
        self.assertEqual(scout_ctx["facts"]["squad_role"], "vanguard")
        self.assertTrue(scout_ctx["facts"]["squad_alert"])
        self.assertEqual(game.ai_decision_preview("scout")["action"], "protect")

    def test_broadcast_atomic_once_per_actor_tick_and_checkpoint_roundtrip(self):
        content, project = fixture()
        game = GameSession.new(content, project, "main", seed=13)
        before = game.recording()
        result = game.ai_squad_share("castle_guard")
        self.assertEqual(result["delivered"], [
            {"actor_id": "scout", "source": "guard"}])
        self.assertEqual(game.ai_state("scout")["values"], {
            "alert": True, "suspicion": 3, "last_known_x": 0,
            "last_known_y": 1, "last_known_scene": "arrival",
            "squad_source": "guard", "squad_signal": "seen",
        })
        self.assertEqual(game.ai_state("traveler")["values"], {})
        self.assertEqual(game.ai_state("guard")["values"], {})
        altered = game.recording()
        self.assertEqual(len(altered["advanced_ai"]["history"]), 1)
        with self.assertRaises(RuleError):
            game.ai_squad_share("castle_guard")
        self.assertEqual(game.recording(), altered)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "squad.json"
            game.save(path)
            resumed = GameSession.load(path, content, project)
        self.assertEqual(resumed.recording(), altered)
        self.assertEqual(resumed.ai_squad_preview("castle_guard"),
                         game.ai_squad_preview("castle_guard"))
        self.assertEqual(
            resumed.ai_decision_preview("scout"),
            game.ai_decision_preview("scout"))
        forged = deepcopy(altered)
        forged["advanced_ai"]["blackboards"]["scout"]["values"]["squad_source"] = "traveler"
        forged["digest"] = digest({k: v for k, v in forged.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, content, project)
        self.assertNotEqual(before, altered)

    def test_radio_out_of_range_or_occluded_and_no_fresh_signal(self):
        stage = {"width": 4, "height": 3, "blocked": [[1, 1], [1, 0], [1, 2]]}
        rows = [
            {"actor_id": "a_guard", "role": "officer", "pos": [0, 1],
             "radio_range": 16, "signal": "seen", "known_pos": [0, 2]},
            {"actor_id": "b_guard", "role": "scout", "pos": [3, 1],
             "radio_range": 16, "signal": "none", "known_pos": None},
        ]
        preview = coordinate_squad(
            stage, "group", rows, scene="arrival", tick=2)
        self.assertIsNone(preview["members"][1]["shared_from"])
        self.assertEqual(preview["members"][1]["intent"], "patrol")
        short = deepcopy(rows)
        short[1]["pos"] = [0, 0]
        short[1]["radio_range"] = 0
        preview = coordinate_squad(stage, "group", short,
                                    scene="arrival", tick=2)
        self.assertIsNone(preview["members"][1]["shared_from"])
        no_fresh = deepcopy(short)
        no_fresh[0]["signal"] = "memory"
        preview = coordinate_squad(stage, "group", no_fresh,
                                    scene="arrival", tick=2)
        self.assertEqual(preview["fresh_sources"], [])
        self.assertIsNone(preview["members"][1]["known_pos"])

    def test_roles_use_reachable_grid_cells_and_never_execute(self):
        stage = {"width": 5, "height": 5, "blocked": [[2, 2]]}
        common = [
            {"actor_id": "guard", "role": "vanguard", "pos": [0, 0],
             "radio_range": 10, "signal": "seen", "known_pos": [3, 3]},
            {"actor_id": "healer", "role": "medic", "pos": [3, 2],
             "radio_range": 10, "signal": "memory", "known_pos": [3, 3]},
            {"actor_id": "flank", "role": "flanker", "pos": [4, 0],
             "radio_range": 10, "signal": "none", "known_pos": None},
        ]
        report = coordinate_squad(
            stage, "squad", common, scene="yard", tick=10)
        rows = {r["actor_id"]: r for r in report["members"]}
        self.assertEqual(rows["guard"]["intent"], "protect")
        self.assertEqual(rows["healer"]["intent"], "retreat")
        self.assertEqual(rows["flank"]["intent"], "flank")
        for row in report["members"]:
            if row["route"] is not None:
                for cell in row["route"]:
                    self.assertNotIn(cell, stage["blocked"])
                    self.assertTrue(0 <= cell[0] < 5 and 0 <= cell[1] < 5)
        self.assertEqual(report, coordinate_squad(
            stage, "squad", list(reversed(common)),
            scene="yard", tick=10))
        self.assertEqual(common[0]["pos"], [0, 0])

    def test_project_rejects_invalid_members_and_oversized_squads(self):
        content, project = fixture()
        malformed = [
            lambda a: a["squad"].update(role="god_mode"),
            lambda a: a["squad"].update(radio_range=True),
            lambda a: a["squad"].update(radio_range=17),
            lambda a: a["squad"].update({"script": "python"}),
            lambda a: a["squad"].update(id="../traversal"),
            lambda a: a.pop("sensor"),
            lambda a: a.update(mode="ct"),
        ]
        for edit in malformed:
            p = deepcopy(project)
            edit(p.extensions[EXTENSION]["data"]["agents"][0])
            with self.subTest(edit=edit), self.assertRaises(RuleError):
                p.validate(content)
        p = deepcopy(project)
        agents = p.extensions[EXTENSION]["data"]["agents"]
        prototype = deepcopy(agents[-1])
        for index in range(8):
            row = deepcopy(prototype)
            row["id"] = "extra" + str(index)
            p.extensions[WORLD_EXTENSION]["data"]["npcs"].append({
                "id": row["id"], "schedule": [{
                    "minute": 0, "scene": "arrival",
                    "activity": "guard", "pos": [1, 0]}]})
            agents.append(row)
        with self.assertRaises(RuleError):
            p.validate(content)

    def test_invalid_batch_rolls_back_all_agents_and_legacy_unchanged(self):
        content, project = fixture()
        game = GameSession.new(content, project, "main")
        original = game.recording()
        ai = game._advanced_ai
        with self.assertRaises(RuleError):
            ai.remember_batch([
                {"actor_id": "guard", "changes": {"alert": True}},
                {"actor_id": "scout", "changes": {"suspicion": 99}},
            ], tick=0)
        self.assertEqual(game.recording(), original)
        with self.assertRaises(RuleError):
            ai.remember_batch([
                {"actor_id": "scout", "changes": {"alert": True}},
                {"actor_id": "guard", "changes": {"alert": True}},
            ], tick=0)
        self.assertEqual(game.recording(), original)
        with self.assertRaises(RuleError):
            game.ai_squad_preview("unknown")
        original_world = deepcopy(project)
        original_world.extensions.pop(EXTENSION)
        legacy = GameSession.new(content, original_world, "main")
        self.assertNotIn("advanced_ai", legacy.recording())


if __name__ == "__main__":
    unittest.main()

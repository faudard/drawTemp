"""R35.A headless contract: authored schedules, offline projection, save/replay."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.living_world import EXTENSION, LivingWorld, validate_living_world
from sporebound.model import RuleError
from tests_standalone.test_r25_scene_router import scene_fixture


def fixture():
    content, project = scene_fixture()
    project.extensions[EXTENSION] = {
        "schema_version": 1, "data": {
            "version": 1, "start_minute": 8 * 60 - 1,
            "ticks_per_minute": 2, "clock_policy": "exploration_only",
            "npcs": [
                {"id": "merchant", "schedule": [
                    {"minute": 0, "scene": "arrival", "activity": "sleep"},
                    {"minute": 480, "scene": "arrival", "activity": "trade",
                     "when": {"flag": "market_open", "eq": True}},
                    {"minute": 1020, "scene": "arrival", "activity": "home"}]},
                {"id": "traveler", "schedule": [
                    {"minute": 60, "scene": "arrival", "activity": "rest"},
                    {"minute": 600, "scene": "arrival", "activity": "walk"}]},
            ]},
        "references": []}
    project.validate(content)
    return content, project


class LivingWorldTests(unittest.TestCase):
    def test_daily_schedule_conditions_midnight_and_offfocus_projection(self):
        content, project = fixture()
        sim = LivingWorld(project.extensions[EXTENSION]["data"],
                          set(project.exploration) | set(content.missions))
        original = sim.snapshot()
        absent_market = sim.view({}, scene="arrival")
        self.assertEqual(absent_market["minute"], 479)
        self.assertEqual(absent_market["npcs"][0]["activity"], "sleep")
        sim.advance(2)
        self.assertEqual(sim.minute, 480)
        self.assertEqual(sim.view({}, scene="arrival")["npcs"][0]["activity"],
                         "sleep")
        self.assertEqual(sim.view({"market_open": True})["npcs"][0]["activity"],
                         "trade")
        sim.advance((1440 - 480) * 2)
        self.assertEqual((sim.day, sim.minute), (1, 0))
        self.assertEqual(sim.view({"market_open": True})["npcs"][0]["activity"],
                         "sleep")
        self.assertEqual(original, {"version": 1, "ticks": 0})
        self.assertNotEqual(sim.snapshot(), original)

    def test_reject_unknown_scenes_unsorted_schedule_and_malformed_ticks(self):
        content, project = fixture()
        data = project.extensions[EXTENSION]["data"]
        bad = deepcopy(data)
        bad["npcs"][0]["schedule"][1]["minute"] = 0
        with self.assertRaises(RuleError):
            validate_living_world(bad, set(project.exploration))
        bad = deepcopy(data)
        bad["npcs"][0]["schedule"][0]["scene"] = "missing"
        with self.assertRaises(RuleError):
            validate_living_world(bad, set(project.exploration))
        bad = deepcopy(data)
        bad["ticks_per_minute"] = True
        with self.assertRaises(RuleError):
            validate_living_world(bad, set(project.exploration))
        sim = LivingWorld(data, set(project.exploration))
        for ticks in (True, -1, 0, 1_000_001):
            with self.subTest(ticks=ticks), self.assertRaises(RuleError):
                sim.advance(ticks)
        self.assertEqual(sim.ticks, 0)
        with self.assertRaises(RuleError):
            sim.restore({"version": 1, "ticks": True})
        self.assertEqual(sim.ticks, 0)

    def test_project_is_canonical_and_session_save_is_opt_in(self):
        content, project = fixture()
        raw = project.to_dict()
        self.assertEqual(GameProject.from_dict(deepcopy(raw), content).to_dict(), raw)
        session = GameSession.new(content, project, "main", seed=11)
        self.assertEqual(session.living_world_state()["minute"], 479)
        self.assertEqual(session.living_world_state()["npcs"][0]["activity"], "sleep")
        session.progress.story_flags["market_open"] = True
        session.living_world_advance(2)
        self.assertEqual(session.living_world_state()["npcs"][0]["activity"], "trade")
        before = session.recording()
        self.assertIn("living_world", before)
        with TemporaryDirectory() as temp:
            path = Path(temp) / "village.json"
            session.save(path)
            restored = GameSession.load(path, content, project)
            self.assertEqual(restored.recording(), before)
            self.assertEqual(restored.living_world_state(), session.living_world_state())
        forged = deepcopy(before)
        forged["living_world"]["ticks"] += 1
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, content, project)
        forged["digest"] = digest({k: v for k, v in forged.items()
                                   if k != "digest"})
        self.assertEqual(GameSession.from_recording(
            forged, content, project).living_world_state()["ticks"], 3)

    def test_rt_movement_advances_once_and_ct_does_not(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=17)
        self.assertEqual(session.living_world_state()["ticks"], 0)
        with self.assertRaises(RuleError):
            session.route_realtime_step(2, 0)
        self.assertEqual(session.living_world_state()["ticks"], 0)
        session.route_realtime_step(1, 0)
        self.assertEqual(session.living_world_state()["ticks"], 1)
        session.progress.story_flags["portal_open"] = True
        session.route_transition("to_arena")
        with self.assertRaises(RuleError):
            session.living_world_advance(1)
        self.assertEqual(session.living_world_state()["ticks"], 1)
        self.assertEqual(GameSession.from_recording(
            session.recording(), content, project).living_world_state()["ticks"], 1)

    def test_legacy_save_shape_and_missing_world_checkpoints(self):
        content, project = scene_fixture()
        old = GameSession.new(content, project, "main")
        self.assertNotIn("living_world", old.recording())
        with self.assertRaises(RuleError):
            old.living_world_state()
        content2, project2 = fixture()
        session = GameSession.new(content2, project2, "main")
        forged = session.recording()
        del forged["living_world"]
        forged["digest"] = digest({k: v for k, v in forged.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, content2, project2)


if __name__ == "__main__":
    unittest.main()

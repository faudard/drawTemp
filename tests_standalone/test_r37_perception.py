"""R37.D perception: LOS, audible R25 inputs, R35 navigation and AI replay."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from sporebound.advanced_ai import EXTENSION as AI_EXTENSION
from sporebound.ai_perception import perceive_grid, validate_sensor
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.living_world import EXTENSION as WORLD_EXTENSION
from sporebound.model import RuleError
from tests_standalone.test_r35_living_world import fixture as world_fixture
from tests_standalone.test_r37_ai_session import policy


def sensor(*, facing="west", vision=5, hearing=6):
    return {"version": 1, "facing": facing,
            "vision_range": vision, "hearing_range": hearing}


def fixture():
    content, project = world_fixture()
    npc = next(row for row in project.extensions[WORLD_EXTENSION]["data"]["npcs"]
               if row["id"] == "traveler")
    for stop in npc["schedule"]:
        stop["pos"] = [3, 1]
    project.extensions[AI_EXTENSION] = {
        "schema_version": 1,
        "data": {
            "version": 1,
            "agents": [{
                "id": "traveler", "mode": "realtime",
                "policies": [
                    policy("hunt", "chase",
                           when={"blackboard.alert": True}, base=5),
                    policy("rest", "patrol",
                           when={"alert": False}, base=1),
                ],
                "sensor": sensor(),
            }],
        },
        "references": [],
    }
    project.validate(content)
    return content, project


class R37PerceptionTests(unittest.TestCase):
    def test_corners_and_walls_block_sight_without_fake_sound(self):
        stage = {"width": 4, "height": 4, "blocked": [[1, 0]]}
        seen = perceive_grid(stage, [0, 0], [2, 2],
                             sensor(facing="omni", vision=4, hearing=4))
        self.assertFalse(seen["visible"])
        self.assertFalse(seen["heard"])
        self.assertEqual(seen["signal"], "none")
        self.assertFalse(seen["reachable"])  # No omniscient path leak.
        self.assertIsNone(seen["path_length"])
        self.assertIsNone(seen["next_step"])
        heard = perceive_grid(stage, [0, 0], [2, 2],
                              sensor(facing="omni", vision=4, hearing=4),
                              movement=True)
        self.assertEqual(heard["signal"], "heard")
        self.assertTrue(heard["heard"])
        self.assertTrue(heard["reachable"])
        self.assertEqual(heard["path_length"], 4)
        self.assertEqual(heard["next_step"], [0, 1])
        self.assertEqual(heard["reason"], "audible_movement")
        # A corner-touching wall blocks LOS in either direction.
        mirror = perceive_grid(stage, [2, 2], [0, 0],
                               sensor(facing="omni", vision=4, hearing=4))
        self.assertFalse(mirror["visible"])
        empty = {"width": 4, "height": 4, "blocked": []}
        self.assertTrue(perceive_grid(
            empty, [0, 0], [2, 2],
            sensor(facing="omni", vision=4, hearing=0))["visible"])

    def test_fov_range_noise_path_and_remembered_pursuit(self):
        stage = {"width": 4, "height": 4, "blocked": [[2, 1]]}
        north = perceive_grid(stage, [3, 1], [0, 1],
                              sensor(facing="north", vision=5, hearing=6),
                              movement=True)
        self.assertFalse(north["within_cone"])
        self.assertEqual(north["signal"], "heard")
        self.assertEqual(north["path_length"], 5)
        self.assertEqual(north["next_step"], [3, 0])
        distant = perceive_grid(stage, [3, 1], [0, 1],
                                sensor(facing="north", vision=1, hearing=2),
                                remembered=[0, 1])
        self.assertEqual(distant["signal"], "none")
        self.assertTrue(distant["alert"])
        self.assertEqual(distant["reason"], "remembered_position")
        self.assertEqual(distant["path_length"], 5)
        self.assertFalse(distant["heard"])
        unreachable = {"width": 3, "height": 3,
                       "blocked": [[1, 0], [1, 1], [1, 2]]}
        blocked = perceive_grid(unreachable, [0, 1], [2, 1],
                                sensor(facing="east", vision=4, hearing=6),
                                movement=True)
        self.assertFalse(blocked["visible"])
        self.assertFalse(blocked["heard"])
        self.assertFalse(blocked["reachable"])
        self.assertIsNone(blocked["next_step"])

    def test_reject_duplicate_obstacle_and_tampered_sensor_memory_atomically(self):
        stage = {"width": 3, "height": 3,
                 "blocked": [[1, 1], [1, 1]]}
        with self.assertRaises(RuleError):
            perceive_grid(stage, [0, 0], [2, 2], sensor())
        stage["blocked"] = [[99, 99]]
        with self.assertRaises(RuleError):
            perceive_grid(stage, [0, 0], [2, 2], sensor())
        content, project = fixture()
        game = GameSession.new(content, project, "main")
        initial = game.recording()
        for changes in (
            {"suspicion": True},
            {"suspicion": "high"},
            {"suspicion": 9},
            {"last_known_x": -1},
            {"alert": 1},
            {"observation_kind": "python"},
        ):
            with self.subTest(changes=changes), self.assertRaises(RuleError):
                game.ai_remember("traveler", changes)
            self.assertEqual(game.recording(), initial)

    def test_strict_sensor_and_project_authoring(self):
        valid = sensor()
        for transform in (
            lambda d: d.update(vision_range=True),
            lambda d: d.update(hearing_range=-1),
            lambda d: d.update(facing="javascript"),
            lambda d: d.update(version=2),
            lambda d: d.update(exec="injected"),
        ):
            doc = deepcopy(valid)
            transform(doc)
            with self.subTest(transform=transform), self.assertRaises(RuleError):
                validate_sensor(doc)
        content, project = fixture()
        self.assertEqual(GameProject.from_dict(
            project.to_dict(), content).to_dict(), project.to_dict())
        editor = AuthoringSession.new(content, project)
        original = editor.snapshot().to_dict()
        broken = deepcopy(project.to_dict())
        broken["extensions"][AI_EXTENSION]["data"]["agents"][0][
            "sensor"]["vision_range"] = 30
        with self.assertRaises(AuthoringError):
            editor.preview_project(
                lambda p: {**p, "extensions": broken["extensions"]})
        self.assertEqual(editor.snapshot().to_dict(), original)
        broken = deepcopy(project)
        npc = next(n for n in broken.extensions[WORLD_EXTENSION]["data"]["npcs"]
                   if n["id"] == "traveler")
        npc["schedule"][0].pop("pos")
        with self.assertRaises(RuleError):
            broken.validate(content)
        broken = deepcopy(project)
        agent = broken.extensions[AI_EXTENSION]["data"]["agents"][0]
        agent["mode"] = "ct"
        with self.assertRaises(RuleError):
            broken.validate(content)

    def test_authoring_sensor_undo_and_authored_only_diagnostics(self):
        from drawtemp.studio.ai_sensor_authoring import AISensorDesigner
        content, project = fixture()
        editor = AuthoringSession.new(content, project)
        designer = AISensorDesigner(editor)
        source = editor.snapshot().to_dict()
        self.assertEqual(designer.agents()[0]["id"], "traveler")
        simulated = designer.simulate("traveler", movement=True)
        self.assertTrue(simulated["preview_only"])
        self.assertEqual(simulated["origin"],
                         "first_authored_schedule_stop_and_stage_start")
        self.assertEqual(simulated["report"]["signal"], "heard")
        self.assertEqual(editor.snapshot().to_dict(), source)
        changed = sensor(facing="omni", vision=4, hearing=0)
        pending = designer.preview(
            "traveler", changed, expected_revision=editor.revision)
        self.assertEqual(editor.revision, 0)
        applied = designer.apply(pending)
        self.assertEqual(editor.revision, 1)
        self.assertEqual(designer.agents()[0]["sensor"], changed)
        with self.assertRaises(AuthoringError):
            designer.apply(pending)
        editor.undo()
        self.assertEqual(designer.agents()[0]["sensor"], sensor())
        editor.redo()
        self.assertEqual(designer.agents()[0]["sensor"], changed)
        self.assertEqual(designer.simulate("traveler")["report"]["signal"],
                         "none")
        with self.assertRaises(ValueError):
            designer.preview("traveler", changed, expected_revision=0)
        removal = designer.preview("traveler", None)
        designer.apply(removal)
        self.assertIsNone(designer.agents()[0]["sensor"])
        editor.undo()
        self.assertEqual(designer.agents()[0]["sensor"], changed)

    def test_canonical_world_noise_and_explicit_alert_replay(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=29)
        pristine = session.recording()
        first = session.ai_perception_preview("traveler")
        self.assertEqual(first["perception"]["signal"], "none")
        self.assertFalse(first["perception"]["reachable"])
        self.assertIsNone(first["perception"]["path_length"])
        self.assertFalse(session.ai_decision_context("traveler")["facts"][
            "enemy_visible"])
        self.assertEqual(session.ai_decision_preview("traveler")["action"],
                         "patrol")
        self.assertEqual(session.recording(), pristine)
        with self.assertRaises(RuleError):
            session.ai_observe("merchant")
        session.route_realtime_step(1, 0)
        signal = session.ai_perception_preview("traveler")
        self.assertEqual(signal["perception"]["signal"], "heard")
        observed = session.ai_observe("traveler")
        self.assertEqual(observed["blackboard"]["values"]["suspicion"], 2)
        self.assertEqual(observed["blackboard"]["values"]["last_known_x"], 0)
        self.assertEqual(observed["blackboard"]["values"]["last_known_y"], 1)
        self.assertEqual(session.ai_decision_preview("traveler")["action"],
                         "chase")
        checkpoint = session.recording()
        with self.assertRaises(RuleError):
            session.ai_observe("traveler")
        self.assertEqual(session.recording(), checkpoint)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "ai-perception.json"
            session.save(path)
            restored = GameSession.load(path, content, project)
        self.assertEqual(restored.recording(), checkpoint)
        self.assertEqual(restored.ai_perception_preview("traveler"), signal)
        self.assertEqual(restored.ai_decision_preview("traveler"),
                         session.ai_decision_preview("traveler"))
        restored.route_realtime_step(0, 0)
        self.assertEqual(restored.ai_perception_preview(
            "traveler")["perception"]["signal"], "none")
        self.assertTrue(restored.ai_perception_preview(
            "traveler")["perception"]["alert"])
        self.assertEqual(restored.ai_observe(
            "traveler")["blackboard"]["values"]["suspicion"], 1)
        restored.route_realtime_step(0, 0)
        self.assertEqual(restored.ai_observe(
            "traveler")["blackboard"]["values"]["suspicion"], 0)
        self.assertFalse(restored.ai_perception_preview(
            "traveler")["perception"]["alert"])

    def test_replayed_tamper_and_unexpected_legacy_sensor_are_refused(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main")
        session.ai_observe("traveler")
        checkpoint = session.recording()
        forged = deepcopy(checkpoint)
        forged["advanced_ai"]["history"][0]["changes"]["suspicion"] = 99
        forged["digest"] = digest({k: v for k, v in forged.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, content, project)
        baseline_content, baseline_project = world_fixture()
        baseline = GameSession.new(baseline_content, baseline_project, "main")
        self.assertNotIn("advanced_ai", baseline.recording())
        with self.assertRaises(RuleError):
            baseline.ai_perception_preview("traveler")


if __name__ == "__main__":
    unittest.main()

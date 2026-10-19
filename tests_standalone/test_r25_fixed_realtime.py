"""R25.C regression: integer free movement and GameSession replay recovery."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.reference import reference_project, MISSION
from sporebound.fixed_clock import _digest as tick_digest
from sporebound.fixed_realtime import (
    FreeMovement, UNITS_PER_TILE, AXIS_STEP, DIAGONAL_STEP)
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from tests_standalone.test_r25_scene_router import scene_fixture


class FreeMovementTests(unittest.TestCase):
    def test_integer_clock_and_blocked_wall(self):
        move = FreeMovement({
            "width": 4, "height": 4, "blocked": [[2, 1]]})
        self.assertEqual(UNITS_PER_TILE, 256)
        self.assertEqual((AXIS_STEP, DIAGONAL_STEP), (32, 23))
        position = move.center([0, 1])
        self.assertEqual(position, [128, 384])
        for _ in range(20):
            position = move.advance(position, 1, 0)
        self.assertEqual(position, [480, 384])
        self.assertEqual(move.cell(position), [1, 1])
        for _ in range(20):
            position = move.advance(position, -1, 0)
        self.assertGreaterEqual(position[0], 0)

    def test_diagonal_never_cuts_blocked_corner_and_slides(self):
        movement = FreeMovement({
            "width": 3, "height": 3, "blocked": [[1, 0], [0, 1]]})
        self.assertEqual(movement.advance([255, 255], 1, 1), [255, 255])
        movement = FreeMovement({
            "width": 3, "height": 3, "blocked": [[1, 0]]})
        self.assertEqual(movement.advance([255, 255], 1, 1), [255, 278])
        open_stage = FreeMovement({
            "width": 3, "height": 3, "blocked": []})
        self.assertEqual(open_stage.advance([128, 128], 1, 1), [151, 151])
        self.assertEqual(open_stage.advance([128, 128], 0, 0), [128, 128])

    def test_invalid_inputs_and_positions_rejected(self):
        move = FreeMovement({"width": 4, "height": 4,
                             "blocked": [[2, 1]]})
        for dx, dy in [(True, 0), (2, 0), (0, -2), (0, None)]:
            with self.subTest(dx=dx, dy=dy), self.assertRaises(RuleError):
                move.advance(move.center([0, 1]), dx, dy)
        for pos in ([512, 384], [1024, 128], [True, 2], [-1, 50]):
            with self.subTest(pos=pos), self.assertRaises(RuleError):
                move.cell(pos)


class RoutedRealtimeTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = scene_fixture()
        self.session = GameSession.new(
            self.content, self.project, "main", seed=17)

    def test_tick_motion_replay_load_and_same_campaign(self):
        session = self.session
        session.progress.story_flags["portal_open"] = True
        session.progress.inventory["potion"] = 3
        session.progress.hero("jeanne").xp = 17
        original = session.route_realtime_state()
        self.assertEqual(original["position"], [128, 384])
        self.assertEqual(original["tick"], 0)
        for _ in range(4):
            snapshot = session.route_realtime_step(1, 0)
        self.assertEqual(snapshot["position"], [256, 384])
        self.assertEqual(snapshot["cell"], [1, 1])
        self.assertEqual(snapshot["tick"], 4)
        self.assertEqual(session.route_state()["position"], [1, 1])
        with self.assertRaises(RuleError):
            session.route_move(1, 0)  # No mixing cardinal and subcell controls.
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "realtime.json"
            session.save(path)
            raw = path.read_bytes()
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(restored.recording(), session.recording())
            self.assertEqual(restored.route_realtime_state(), snapshot)
            self.assertEqual(restored.progress.inventory["potion"], 3)
            self.assertEqual(restored.progress.heroes["jeanne"].xp, 17)
            for _ in range(9):
                restored.route_realtime_step(1, 0)
            self.assertEqual(restored.route_realtime_state()["position"],
                             [480, 384])  # Blocked next tile.
            entered = restored.route_transition("to_arena")
            self.assertEqual(entered["mode"], "battle")
            self.assertEqual(entered["scene"], MISSION)
            self.assertEqual(restored.progress.inventory["potion"], 3)
            self.assertEqual(restored.progress.heroes["jeanne"].xp, 17)
            self.assertNotIn("scene_realtime", restored.recording())
            restored.save(path)
            resumed = GameSession.load(path, self.content, self.project)
            self.assertEqual(resumed.mode, "battle")
            self.assertEqual(resumed.active_battle.digest(),
                             restored.active_battle.digest())
            resumed.abandon_encounter()
            resumed.route_transition("retreat")
            self.assertEqual(resumed.route_realtime_state()["position"],
                             [384, 384])
            resumed.route_realtime_step(-1, 0)
            resumed.save(path)
            again = GameSession.load(path, self.content, self.project)
            self.assertEqual(again.recording(), resumed.recording())

    def test_tick_failure_never_mutates_session(self):
        session = self.session
        before = session.recording()
        for dx, dy in ((True, 0), (2, 0), (0, "wrong")):
            with self.subTest(dx=dx, dy=dy), self.assertRaises(RuleError):
                session.route_realtime_step(dx, dy)
            self.assertEqual(session.recording(), before)
        session.route_realtime_step(1, 0)
        before = session.recording()
        with self.assertRaises(RuleError):
            session.route_realtime_step(2, 0)
        self.assertEqual(session.recording(), before)

    def test_corrupted_journal_and_mismatched_campaign_cell_rejected(self):
        session = self.session
        for _ in range(5):
            session.route_realtime_step(1, 0)
        original = session.recording()
        self.assertEqual(original["scene_realtime"]["position"], [288, 384])
        changes = [
            lambda data: data["scene_realtime"]["journal"]["inputs"][0]
                ["command"].update(dx=-1),
            lambda data: data["scene_realtime"].update(position=[300, 384]),
            lambda data: data["scene_realtime"].update(scene="missing"),
            lambda data: data["scene_realtime"]["journal"].update(seed=1234),
            lambda data: data["scene_realtime"]["journal"]["states"].__setitem__(
                0, "0" * 64),
            lambda data: data["progress"]["story_flags"].update(
                {"ex_" + "a" * 12 + "_pos": "2,1"}),
        ]
        for change in changes[:-1]:
            row = deepcopy(original)
            change(row)
            # Re-hash the outer session to exercise validation below that layer.
            row["digest"] = digest({k: v for k, v in row.items()
                                    if k != "digest"})
            with self.subTest(change=change), self.assertRaises(RuleError):
                GameSession.from_recording(row, self.content, self.project)
        # Explicit campaign movement state divergence, even after rehash.
        from sporebound.exploration import _key
        altered = deepcopy(original)
        altered["progress"]["story_flags"][_key("arrival", "pos")] = "2,1"
        altered["digest"] = digest({k: v for k, v in altered.items()
                                    if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(altered, self.content, self.project)

    def test_legacy_save_and_project_digests_remain_byte_identical(self):
        content, project = reference_project()
        session = GameSession.new(content, project, "main", seed=17)
        raw = session.recording()
        self.assertNotIn("scene_realtime", raw)
        self.assertNotIn("scene_route", raw)
        self.assertNotIn("scene_routes", project.to_dict())
        self.assertNotIn("game_modes", project.to_dict())
        self.assertEqual(GameSession.from_recording(
            raw, content, project).recording(), raw)


if __name__ == "__main__":
    unittest.main()

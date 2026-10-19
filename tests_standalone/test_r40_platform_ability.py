"""R40.B.3 real R32 double-jump/portals on canonical R33-authored rooms.

These headless source probes do not constitute a finished Player/metroidvania
certification. They use the actual R32 deterministic runtime and GameSession.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.r40_starters import _platform_room, create_starter_pair
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from sporebound.platform_physics import PlatformPhysics, PhysicsError, _hash


def _advance(game, *moves):
    events = []
    for move, jump in moves:
        events.extend(game.route_platform_step(move=move, jump=jump)["events"])
    return events


def _reach_route(game, route, *, budget=35):
    for _ in range(budget):
        if route in game.route_platform_state()["available_routes"]:
            return
        game.route_platform_step(move=1)
    raise AssertionError("Physical portal not reached: " + route)


def _collect_feather(content, project):
    game = GameSession.new(content, project, "main", seed=29)
    with unittest.TestCase().assertRaises(RuleError):
        game.route_transition("high_gate")
    _reach_route(game, "to_ruins")
    assert game.progress.story_flags.get("r33_pickup_feather") is not True
    assert game.route_platform_travel("to_ruins")["scene"] == "r40_ruins"
    assert game.route_platform_state()["scene"] == "r40_ruins"
    assert game.route_platform_state()["tick"] == 0
    game.route_platform_step(move=1)
    assert game.progress.story_flags["r33_pickup_feather"] is True
    _reach_route(game, "back_to_village")
    assert game.route_platform_travel("back_to_village")["scene"] == "arrival"
    assert game.route_platform_state()["air_jumps_left"] == 1
    return game


class R40PlatformAbilityTests(unittest.TestCase):
    def test_old_r32_checkpoint_contract_is_bitwise_unchanged(self):
        scene = _platform_room("arrival")
        old = PlatformPhysics(scene)
        old.step({"tick": 1, "move": 0, "jump": True})
        for tick in range(2, 5):
            old.step({"tick": tick})
        old_events = old.step({"tick": 5, "jump": True})
        self.assertFalse(any(e["kind"] == "jump" for e in old_events))
        raw = old.recording()
        self.assertNotIn("max_air_jumps", raw)
        self.assertNotIn("air_jumps_left", old.snapshot())
        self.assertEqual(PlatformPhysics.from_recording(
            raw, expected_scene=scene).recording(), raw)

    def test_opt_in_second_jump_consumed_once_and_replayed(self):
        scene = _platform_room("arrival")
        powered = PlatformPhysics(scene, max_air_jumps=1)
        first = powered.step({"tick": 1, "jump": True})
        self.assertIn("jump", [e["kind"] for e in first])
        for tick in range(2, 5):
            powered.step({"tick": tick})
        second = powered.step({"tick": 5, "jump": True})
        self.assertIn("jump", [e["kind"] for e in second])
        self.assertEqual(powered.snapshot()["air_jumps_left"], 0)
        third = powered.step({"tick": 6, "jump": True})
        self.assertNotIn("jump", [e["kind"] for e in third])
        original = powered.recording()
        self.assertEqual(original["max_air_jumps"], 1)
        self.assertEqual(PlatformPhysics.from_recording(
            original, expected_scene=scene).recording(), original)
        for count in (True, -1, 2, "1"):
            with self.subTest(count=count), self.assertRaises(PhysicsError):
                PlatformPhysics(scene, max_air_jumps=count)

    def test_physical_feather_checkpoint_then_double_jump_high_gate(self):
        content, project = create_starter_pair("r40-metroidvania")
        self.assertEqual(set(project.extensions["drawtemp.physics"]["data"]["scenes"]),
                         {"arrival", "r40_ruins", "r40_citadel"})
        self.assertIn("high_gate", [
            row["id"] for row in project.scene_routes["links"]])
        game = _collect_feather(content, project)
        with self.assertRaises(RuleError):
            game.route_transition("high_gate")  # No physical contact yet.
        with TemporaryDirectory() as folder:
            save_path = Path(folder) / "metroidvania.json"
            game.save(save_path)
            resumed = GameSession.load(save_path, content, project)
            self.assertEqual(resumed.recording(), game.recording())
            self.assertEqual(resumed.route_platform_state()["air_jumps_left"], 1)
            for _ in range(8):
                resumed.route_platform_step(move=1)
            start = resumed.route_platform_step(move=1, jump=True)
            self.assertIn("jump", [event["kind"] for event in start["events"]])
            for _ in range(4):
                resumed.route_platform_step(move=1)
            second = resumed.route_platform_step(move=1, jump=True)
            self.assertIn("jump", [event["kind"] for event in second["events"]])
            self.assertEqual(second["state"]["air_jumps_left"], 0)
            for _ in range(6):
                resumed.route_platform_step(move=1)
            self.assertIn("high_gate",
                          resumed.route_platform_state()["available_routes"])
            resumed.save(save_path)
            verified = GameSession.load(save_path, content, project)
            self.assertEqual(verified.recording(), resumed.recording())
            self.assertEqual(
                verified.route_platform_travel("high_gate")["scene"],
                "r40_citadel")
            self.assertEqual(verified.mode, "campaign")
            verified.save(save_path)
            self.assertEqual(GameSession.load(
                save_path, content, project).recording(),
                verified.recording())

    def test_double_jump_forgery_rejected_even_if_outer_hash_is_recomputed(self):
        content, project = create_starter_pair("r40-metroidvania")
        game = _collect_feather(content, project)
        _advance(game, (0, True), (0, False),
                 (0, False), (0, False), (0, True))
        raw = game.recording()
        physics = raw["scene_platform"]["physics"]
        self.assertEqual(physics["max_air_jumps"], 1)
        forged = deepcopy(raw)
        forged_physics = forged["scene_platform"]["physics"]
        forged_physics.pop("max_air_jumps")
        forged_physics["digest"] = _hash({
            key: val for key, val in forged_physics.items() if key != "digest"})
        forged["digest"] = digest({
            key: val for key, val in forged.items() if key != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, content, project)

    def test_unearned_ability_cannot_be_enabled_via_save(self):
        content, project = create_starter_pair("r40-metroidvania")
        game = GameSession.new(content, project, "main", seed=29)
        game.route_platform_step(move=0)
        baseline = game.recording()
        forged = deepcopy(baseline)
        p = forged["scene_platform"]["physics"]
        p["max_air_jumps"] = 1
        p["digest"] = _hash({k: v for k, v in p.items() if k != "digest"})
        forged["digest"] = digest({
            k: v for k, v in forged.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, content, project)


if __name__ == "__main__":
    unittest.main()

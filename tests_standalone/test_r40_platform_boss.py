"""R40.B.4 — authoritative two-phase R32 guardian, replay and save gates.

All tests use the existing R32 platform adapter and, for release evidence,
the canonical GameSession; no fabricated combat state or Qt clock.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.r40_starters import _platform_room, create_starter_pair
from sporebound.exploration import _key
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from sporebound.platform_physics import PlatformPhysics, PhysicsError, _hash


def _citadel_game():
    content, project = create_starter_pair("r40-metroidvania")
    game = GameSession.new(content, project, "main", seed=31)
    for _ in range(8):
        game.route_platform_step(move=1)
    game.route_platform_travel("to_ruins")
    game.route_platform_step(move=1)
    if game.progress.story_flags.get("r33_pickup_feather") is not True:
        raise AssertionError("Authored feather was not physically collected")
    for _ in range(8):
        game.route_platform_step(move=1)
    game.route_platform_travel("back_to_village")
    for _ in range(8):
        game.route_platform_step(move=1)
    game.route_platform_step(move=1, jump=True)
    for _ in range(4):
        game.route_platform_step(move=1)
    game.route_platform_step(move=1, jump=True)
    for _ in range(6):
        game.route_platform_step(move=1)
    game.route_platform_travel("high_gate")
    return content, project, game


def _fight(game):
    for _ in range(9):
        game.route_platform_step(move=1)
    observed = []
    for _ in range(220):
        state = game.route_platform_state()["boss"]
        if state["defeated"]:
            break
        if state["player_defeated"]:
            raise AssertionError("R40 guardian killed the deterministic test hero")
        attack = state["window"] == "recover" and state["cooldown"] == 0
        observed.extend(game.route_platform_step(attack=attack)["events"])
    else:
        raise AssertionError("R40 guardian never reached victory in 220 ticks")
    return observed


class R40PhysicalBossTests(unittest.TestCase):
    def test_boss_is_opt_in_and_legacy_commands_do_not_change(self):
        ordinary = _platform_room("arrival")
        runtime = PlatformPhysics(ordinary)
        baseline = runtime.recording()
        with self.assertRaises(PhysicsError):
            runtime.step({"tick": 1, "attack": True})
        self.assertEqual(runtime.recording(), baseline)
        runtime.step({"tick": 1})
        self.assertNotIn("boss", runtime.snapshot())
        self.assertNotIn("attack", runtime.recording()["commands"][0])
        self.assertEqual(
            PlatformPhysics.from_recording(runtime.recording()).recording(),
            runtime.recording())

    def test_authored_boss_schema_rejects_malformed_parameters(self):
        scene = _platform_room("r40_citadel", citadel=True)
        self.assertTrue(PlatformPhysics(scene).snapshot()["boss"]["hp"] == 4)
        for key, value in [
            ("hp", True), ("hp", 0), ("phase_at", 4),
            ("rect", [0, 0, 90000, 900]), ("strike", [0, 2]),
            ("hero_hp", 0), ("attack_rect", [0, 0, -1, 3]),
        ]:
            altered = deepcopy(scene)
            altered["boss"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(RuleError):
                PlatformPhysics(altered)

    def test_real_boss_telegraph_damage_two_phases_and_canonical_victory(self):
        content, project, game = _citadel_game()
        self.assertEqual(game.route_scene, "r40_citadel")
        self.assertNotIn("to_citadel",
                         [row["id"] for row in project.scene_routes["links"]])
        assert game.route_platform_state()["boss"]["phase"] == 1
        with TemporaryDirectory() as folder:
            path = Path(folder) / "r40.json"
            game.save(path)
            resumed = GameSession.load(path, content, project)
            self.assertEqual(resumed.recording(), game.recording())
            events = _fight(resumed)
            kinds = {row["kind"] for row in events}
            self.assertIn("boss_hit", kinds)
            self.assertIn("boss_phase", kinds)
            self.assertIn("boss_defeated", kinds)
            self.assertTrue(resumed.route_platform_state()["boss"]["defeated"])
            self.assertEqual(resumed.route_platform_state()["boss"]["phase"], 2)
            self.assertGreater(resumed.route_platform_state()["boss"]["hero_hp"], 0)
            self.assertTrue(resumed.progress.story_flags.get(
                _key("r40_citadel", "boss_defeated")))
            resumed.save(path)
            verified = GameSession.load(path, content, project)
            self.assertEqual(verified.recording(), resumed.recording())
            self.assertTrue(verified.route_platform_state()["boss"]["defeated"])

    def test_boss_replay_rejects_rewritten_attack_command(self):
        content, project, game = _citadel_game()
        events = _fight(game)
        self.assertTrue(any(e["kind"] == "boss_defeated" for e in events))
        original = game.recording()
        changed = deepcopy(original)
        inner = changed["scene_platform"]["physics"]
        attacks = [row for row in inner["commands"] if row["attack"]]
        self.assertGreater(len(attacks), 0)
        attacks[0]["attack"] = False
        inner["digest"] = _hash({
            k: v for k, v in inner.items() if k != "digest"})
        changed["digest"] = digest({
            k: v for k, v in changed.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(changed, content, project)
        self.assertEqual(game.recording(), original)

    def test_recomputed_outer_checksum_cannot_forge_boss_victory(self):
        content, project, game = _citadel_game()
        _fight(game)
        raw = game.recording()
        changed = deepcopy(raw)
        changed["progress"]["story_flags"].pop(
            _key("r40_citadel", "boss_defeated"))
        changed["digest"] = digest({
            k: v for k, v in changed.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(changed, content, project)
        self.assertEqual(GameSession.from_recording(
            raw, content, project).recording(), raw)


if __name__ == "__main__":
    unittest.main()

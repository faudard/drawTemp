"""R32.A/B deterministic side-view physics contract; no Qt or CT integration."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys
import unittest

from sporebound.platform_physics import (
    PhysicsError, PlatformPhysics, TICK_HZ, validate_platform_scene,
)


def scene(*, hero=None, colliders=None):
    floor = {"id": "floor", "rect": [0, 5000, 12000, 1000],
             "layer": 1, "mask": 1, "trigger": False, "one_way": False}
    return {
        "id": "r32_room", "width": 12000, "height": 6000, "gravity": 40,
        "hero": hero or {
            "pos": [1000, 4200], "size": [500, 800], "speed": 240,
            "jump": 520, "max_fall": 900, "coyote": 4,
        },
        "colliders": [floor] if colliders is None else colliders,
    }


def block(name, rect, *, trigger=False, one_way=False, layer=1, mask=1, **fields):
    return {"id": name, "rect": rect, "layer": layer, "mask": mask,
            "trigger": trigger, "one_way": one_way, **fields}


def step(game, **kwargs):
    return game.step({"tick": game.tick + 1, **kwargs})


class PlatformPhysicsR32Tests(unittest.TestCase):
    def test_schema_rejects_bools_duplicates_unknown_keys_bad_travel(self):
        good = scene()
        self.assertEqual(validate_platform_scene(good), good)
        bad = [
            {**good, "width": True},
            {**good, "debug_python": "eval"},
            {**good, "colliders": good["colliders"] * 2},
            scene(colliders=[block("bad", [1, 1, 0, 1])]),
            scene(colliders=[block("bad", [11000, 1, 2000, 1])]),
            scene(colliders=[block("bad", [0, 0, 1, 1], mask=True)]),
            scene(colliders=[block("bad", [0, 0, 1, 1],
                                   trigger=True, one_way=True)]),
            scene(colliders=[block("bad", [0, 0, 1, 1],
                                   one_way=True, velocity=30, travel=[40, 50])]),
            scene(colliders=[block("bad", [1200, 4300, 500, 500])]),
        ]
        for invalid in bad:
            with self.subTest(invalid=invalid), self.assertRaises(PhysicsError):
                PlatformPhysics(invalid)

    def test_swept_collision_never_tunnels_thin_wall_even_at_max_speed(self):
        room = scene(colliders=[
            block("floor", [0, 5000, 12000, 1000]),
            block("thin_wall", [3000, 3200, 2, 1800]),
        ])
        game = PlatformPhysics(room)
        for _ in range(15):
            step(game, move=1)
        self.assertEqual(game.actor["x"], 2500)
        self.assertTrue(game.actor["grounded"])
        self.assertEqual(game.actor["ground_id"], "floor")
        self.assertEqual(step(game, move=1)[0]["kind"], "wall")

    def test_fixed_tick_same_hash_at_different_render_refresh_rates(self):
        inputs = [{"move": 1} for _ in range(9)]
        inputs += [{"move": 1, "jump": True}]
        inputs += [{"move": 1} for _ in range(45)]
        records = []
        for render_hz in (30, 60, 120):
            game = PlatformPhysics(scene())
            for frame in inputs:
                step(game, **frame)
                for _ in range(render_hz // 30):
                    _ = game.snapshot()  # Presentation cannot step the simulation.
            self.assertEqual(game.snapshot()["tick_hz"], TICK_HZ)
            records.append(game.digest())
        self.assertEqual(len(set(records)), 1)

    def test_jump_fall_landing_replay_and_coyote_after_edge(self):
        game = PlatformPhysics(scene())
        starting_y = game.actor["y"]
        events = step(game, jump=True)
        self.assertEqual(events[0]["kind"], "jump")
        self.assertLess(game.actor["y"], starting_y)
        landed = False
        for _ in range(50):
            landed |= any(e["kind"] == "land" for e in step(game))
        self.assertTrue(landed)
        self.assertEqual(game.actor["y"], starting_y)
        self.assertEqual(game.digest(),
                         PlatformPhysics.from_recording(game.recording()).digest())
        edge = scene(hero={
            "pos": [1300, 4200], "size": [500, 800], "speed": 240,
            "jump": 520, "max_fall": 900, "coyote": 4,
        }, colliders=[block("ledge", [0, 5000, 1800, 1000])])
        coyote = PlatformPhysics(edge)
        for _ in range(3):
            step(coyote, move=1)
        self.assertFalse(coyote.actor["grounded"])
        self.assertGreater(coyote.actor["coyote_left"], 0)
        self.assertEqual(step(coyote, jump=True)[0]["kind"], "jump")

    def test_one_way_pass_through_from_below_and_land_above(self):
        room = scene(hero={
            "pos": [2200, 4200], "size": [500, 800], "speed": 0,
            "jump": 520, "max_fall": 900, "coyote": 4,
        }, colliders=[
            block("floor", [0, 5000, 12000, 1000]),
            block("bridge", [2000, 3600, 1500, 80], one_way=True),
        ])
        game = PlatformPhysics(room)
        step(game, jump=True)
        landed_on_bridge = False
        for _ in range(45):
            events = step(game)
            landed_on_bridge |= any(e.get("collider") == "bridge"
                                    and e["kind"] == "land" for e in events)
        self.assertTrue(landed_on_bridge)
        self.assertEqual(game.actor["y"], 3600 - 800)
        self.assertEqual(game.actor["ground_id"], "bridge")

    def test_moving_platform_carries_rider_and_replay_stays_identical(self):
        room = scene(hero={
            "pos": [2100, 3000], "size": [500, 800], "speed": 240,
            "jump": 520, "max_fall": 900, "coyote": 4,
        }, colliders=[
            block("lift", [1800, 3800, 1800, 100], one_way=True,
                  velocity=100, travel=[1800, 2400]),
            block("floor", [0, 5000, 12000, 1000]),
        ])
        game = PlatformPhysics(room)
        self.assertEqual(game.actor["ground_id"], "lift")
        for _ in range(4):
            step(game)
        self.assertEqual(game.actor["x"], 2500)
        self.assertEqual(game.movers["lift"]["x"], 2200)
        self.assertEqual(game.actor["ground_id"], "lift")
        for _ in range(16):
            step(game)
        self.assertEqual(game.digest(),
                         PlatformPhysics.from_recording(game.recording(),
                                                        expected_scene=room).digest())

    def test_triggers_are_nonblocking_filterable_and_transition_once(self):
        room = scene(colliders=[
            block("floor", [0, 5000, 12000, 1000]),
            block("door_sensor", [1600, 4200, 120, 700], trigger=True),
            block("inert_sensor", [2000, 4200, 120, 700],
                  trigger=True, mask=2),
        ])
        game = PlatformPhysics(room)
        events = sum((step(game, move=1) for _ in range(8)), [])
        self.assertEqual([e["kind"] for e in events],
                         ["trigger_enter", "trigger_exit"])
        self.assertTrue(all(e["collider"] == "door_sensor" for e in events))
        self.assertEqual(game.actor["x"], 1000 + 8 * 240)

    def test_failure_atomic_tamper_replay_changed_scene_and_file_checkpoint(self):
        room = scene()
        game = PlatformPhysics(room)
        before = game.recording()
        for invalid in ({"tick": 2}, {"tick": 1, "move": True},
                        {"tick": 1, "jump": 1}, {"tick": 1, "command": "exec"}):
            with self.assertRaises(PhysicsError):
                game.step(invalid)
            self.assertEqual(game.recording(), before)
        for _ in range(8):
            step(game, move=1)
        with TemporaryDirectory() as temp:
            path = Path(temp) / "physics.json"
            game.save(path)
            previous_bytes = path.read_bytes()
            restored = PlatformPhysics.load(path, expected_scene=room)
            self.assertEqual(restored.digest(), game.digest())
            self.assertEqual(path.read_bytes(), previous_bytes)
            tampered = json.loads(previous_bytes)
            tampered["commands"][0]["move"] = -1
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(PhysicsError):
                PlatformPhysics.load(path)
            changed = deepcopy(room)
            changed["gravity"] = 41
            with self.assertRaises(PhysicsError):
                PlatformPhysics.from_recording(game.recording(), expected_scene=changed)
            path.write_text('{"version":', encoding="utf-8")
            with self.assertRaises(PhysicsError):
                PlatformPhysics.load(path)

    def test_snapshots_cannot_mutate_owned_state_and_module_is_headless(self):
        game = PlatformPhysics(scene())
        snap = game.snapshot()
        snap["actor"]["x"] = -9000
        snap["movers"]["fake"] = {}
        self.assertEqual(game.actor["x"], 1000)
        program = """
import sys
class Block:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("PySide6", "PyQt5", "PyQt6", "tkinter"):
            raise RuntimeError(fullname)
sys.meta_path.insert(0, Block())
from sporebound.platform_physics import PlatformPhysics
from sporebound.game_session import GameSession
assert PlatformPhysics and GameSession
"""
        subprocess.run([sys.executable, "-c", program],
                       check=True, capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    unittest.main()

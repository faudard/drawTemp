"""R65.C gate: actual coordinated combat, real boss phases and save/replay."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.r65_arena_controller import ActionArenaController
from sporebound.action_arena_r65 import ActionArenaR65, arena_demo, validate_arena
from sporebound.action_combat_r65 import ActionCombatR65
from sporebound.action_runtime import ActionError, ActionRuntime


def game():
    return ActionArenaR65(*arena_demo())


def command(runtime, **kwargs):
    return runtime.step({"tick": runtime.tick + 1, **kwargs})


class R65ArenaTests(unittest.TestCase):
    def test_strict_arena_requires_two_distinct_flankers_and_boss_phases(self):
        scene, preset, setup = arena_demo()
        self.assertEqual(validate_arena(scene, preset, setup)[2], setup)
        for bad in (
            {**setup, "flankers": ["scout_left", "scout_left"]},
            {**setup, "boss_id": "nonexistent"},
            {**setup, "unknown": 1},
            {**setup, "flankers": [True, "scout_right"]},
        ):
            with self.subTest(bad=bad), self.assertRaises(ActionError):
                validate_arena(scene, preset, bad)
        invalid = deepcopy(preset)
        invalid["boss_patterns"][1]["hp_at_or_below"] = 100
        with self.assertRaises(ActionError):
            validate_arena(scene, invalid, setup)
        invalid = deepcopy(preset)
        invalid["boss_patterns"][0]["phase"] = 2
        with self.assertRaises(ActionError):
            validate_arena(scene, invalid, setup)
        extra = deepcopy(scene)
        extra["enemies"].append({
            "id": "stranger", "hp": 3, "pos": [2, 2], "patrol": []})
        with self.assertRaises(ActionError):
            validate_arena(extra, preset, setup)

    def test_two_flankers_act_in_stable_order_boss_telegraphs_before_action(self):
        runner = game()
        self.assertEqual(list(runner.flankers), ["scout_left", "scout_right"])
        events = []
        for _ in range(35):
            events.extend(command(runner))
        types = [row["kind"] for row in events]
        self.assertIn("boss_telegraph", types)
        self.assertIn("boss_action", types)
        self.assertLess(types.index("boss_telegraph"), types.index("boss_action"))
        self.assertNotEqual(runner.enemies["scout_left"]["pos"], [5500, 2500])
        self.assertNotEqual(runner.enemies["scout_right"]["pos"], [5500, 6500])
        self.assertNotEqual(runner.enemies["scout_left"]["pos"],
                            runner.enemies["scout_right"]["pos"])
        self.assertEqual(runner.digest(),
                         ActionArenaR65.from_recording(runner.recording()).digest())

    def test_boss_projectile_uses_real_collision_and_can_damage_hero(self):
        runner = game()
        events = []
        for _ in range(35):
            events.extend(command(runner))
        kinds = [row["kind"] for row in events]
        self.assertIn("boss_projectile", kinds)
        self.assertIn("boss_projectile_impact", kinds)
        self.assertLess(runner.hero["hp"], 40)
        # A wall separates the boss and the hero; it stops the hostile shot.
        scene, preset, setup = arena_demo()
        scene["walls"].append([6, 4])
        blocked = ActionArenaR65(scene, preset, setup)
        events = []
        for _ in range(35):
            events.extend(command(blocked))
        self.assertIn("boss_projectile_blocked", [row["kind"] for row in events])

    def test_real_melee_hit_transitions_boss_to_phase_two(self):
        scene, preset, setup = arena_demo()
        scene["hero"]["pos"] = [7, 4]
        preset["rules"]["combo"][0].update(
            damage=14, windup=1, active=1, recovery=3)
        runner = ActionArenaR65(scene, preset, setup)
        events = []
        for n in range(12):
            events.extend(command(runner, dx=1 if n == 0 else 0,
                                  attack=n == 0))
        self.assertLessEqual(runner.enemies["warden"]["hp"], 12)
        self.assertEqual(runner.boss["phase"], 2)
        self.assertTrue(any(row["kind"] == "boss_phase" and row["phase"] == 2
                            for row in events))
        self.assertTrue(any(row["kind"] == "enemy_hit" and
                            row["enemy"] == "warden"
                            for row in events))
        self.assertEqual(runner.digest(),
                         ActionArenaR65.from_recording(runner.recording()).digest())

    def test_replay_v3_save_mid_cast_and_corruption_rollback(self):
        scene, preset, setup = arena_demo()
        runner = ActionArenaR65(scene, preset, setup,
                                initial_inventory={"potion": 2})
        for _ in range(9):
            command(runner)
        self.assertGreater(runner.tick, 0)
        snapshot = runner.snapshot()
        snapshot["arena"]["boss"]["phase"] = 99
        self.assertEqual(runner.boss["phase"], 1)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "arena-v3.json"
            runner.save(path)
            original = path.read_bytes()
            reloaded = ActionArenaR65.load(
                path, expected_scene=scene, expected_preset=preset,
                expected_setup=setup)
            self.assertEqual(reloaded.digest(), runner.digest())
            self.assertEqual(reloaded.initial_inventory, {"potion": 2})
            self.assertEqual(path.read_bytes(), original)
            for _ in range(12):
                command(reloaded)
            self.assertNotEqual(reloaded.digest(), runner.digest())

            altered = json.loads(original.decode("utf8"))
            altered["commands"][0]["tick"] = 700
            path.write_text(json.dumps(altered), encoding="utf8")
            with self.assertRaises(ActionError):
                ActionArenaR65.load(path)
            altered = json.loads(original.decode("utf8"))
            altered["preset"]["rules"]["projectile"]["speed"] += 1
            path.write_text(json.dumps(altered), encoding="utf8")
            with self.assertRaises(ActionError):
                ActionArenaR65.load(path)
            changed = deepcopy(preset)
            changed["rules"]["combo"][0]["damage"] += 1
            with self.assertRaises(ActionError):
                ActionArenaR65.from_recording(runner.recording(),
                                             expected_preset=changed)

    def test_atomic_invalid_tick_and_cross_version_rejection(self):
        arena = game()
        before = arena.recording()
        for bad in (
            {"tick": 2},
            {"tick": 1, "fire": "yes"},
            {"tick": 1, "parry": 1},
            {"tick": 1, "attack": True, "spell": "unknown"},
            {"tick": 1, "interact": "not_found"},
        ):
            with self.subTest(bad=bad), self.assertRaises(ActionError):
                arena.step(bad)
            self.assertEqual(arena.recording(), before)
        scene, preset, setup = arena_demo()
        v1 = ActionRuntime(scene)
        v2 = ActionCombatR65(scene, preset["rules"])
        self.assertEqual(v1.digest(), ActionRuntime.from_recording(
            v1.recording()).digest())
        self.assertEqual(v2.digest(), ActionCombatR65.from_recording(
            v2.recording()).digest())
        for old in (v1.recording(), v2.recording()):
            with self.assertRaises(ActionError):
                ActionArenaR65.from_recording(old)

    def test_render_reads_and_frame_cadence_never_change_tick_inputs(self):
        frames = [0, 1, 2, 3]
        output = []
        for reads in frames:
            runner = game()
            for tick in range(1, 72):
                for _ in range(reads):
                    view = runner.snapshot()
                    view["arena"]["boss"]["phase"] = -1
                runner.step({"tick": tick, "fire": tick % 12 == 1,
                             "dx": 1 if tick < 5 else 0,
                             "parry": tick in (12, 36)})
            output.append(runner.digest())
        self.assertEqual(len(set(output)), 1)

    def test_player_pause_save_load_and_failed_load_is_atomic(self):
        with TemporaryDirectory() as tmp:
            scene, preset, setup = arena_demo()
            path = Path(tmp) / "arena.json"
            player = ActionArenaController(scene, preset, setup, save_path=path)
            self.assertEqual(player.state()["mode"], "R65_ARENA")
            player.step(dx=1, fire=True)
            player.toggle_pause()
            tick = player.runtime.tick
            self.assertEqual(player.step(dx=1), [])
            self.assertEqual(tick, player.runtime.tick)
            player.toggle_pause()
            player.step(dx=1)
            checkpoint = player.runtime.digest()
            player.save()
            player.step(dx=1)
            player.load()
            self.assertEqual(player.runtime.digest(), checkpoint)
            before = player.runtime.digest()
            forged = json.loads(path.read_text(encoding="utf8"))
            forged["commands"][0]["dx"] = -1
            path.write_text(json.dumps(forged), encoding="utf8")
            with self.assertRaises(ActionError):
                player.load()
            self.assertEqual(player.runtime.digest(), before)
            self.assertEqual(player.runtime.tick, tick + 1)


if __name__ == "__main__":
    unittest.main()

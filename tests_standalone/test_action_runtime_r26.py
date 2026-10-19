"""R26 first incremental gate: real-time rules independent of Qt and render FPS."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from sporebound.action_runtime import (
    ActionError, ActionRuntime, SCALE, TICK_HZ, validate_scene,
)


def scene(*, walls=None, enemies=None, objects=None, hero=None):
    return {
        "id": "r26_reference", "width": 8, "height": 8,
        "walls": walls if walls is not None else [[4, 4]],
        "hero": hero if hero is not None else {"pos": [1, 1], "hp": 12},
        "enemies": enemies if enemies is not None else [],
        "objects": objects if objects is not None else [],
    }


def enemy(name="wolf", pos=None, hp=2, patrol=None):
    return {"id": name, "pos": pos if pos is not None else [2, 1],
            "hp": hp, "patrol": patrol if patrol is not None else []}


class ActionRuntimeR26Tests(unittest.TestCase):
    def command(self, runtime, **fields):
        return runtime.step({"tick": runtime.tick + 1, **fields})

    def test_validation_rejects_unknown_fields_collisions_and_invalid_coordinates(self):
        base = scene()
        for broken in (
            {**base, "unexpected": True},
            {**base, "walls": [[4, 4], [4, 4]]},
            {**base, "hero": {"pos": [4, 4], "hp": 1}},
            {**base, "enemies": [enemy(pos=[1, 1])]},
            {**base, "objects": [{"id": "no_item", "kind": "chest",
                                  "pos": [2, 2], "item": "", "requires": ""}]},
        ):
            with self.subTest(broken=broken), self.assertRaises(ActionError):
                validate_scene(broken)
        self.assertEqual(validate_scene(base), base)

    def test_fixed_point_cardinal_and_diagonal_replay_independent_of_draw_frequency(self):
        cardinal, diagonal, repeated = [ActionRuntime(scene()) for _ in range(3)]
        for _ in range(6):
            self.command(cardinal, dx=1)
            self.command(diagonal, dx=1, dy=1)
            self.command(repeated, dx=1, dy=1)
        self.assertEqual(cardinal.hero["pos"], [1500 + 6 * 160, 1500])
        self.assertEqual(diagonal.hero["pos"], [1500 + 6 * 113, 1500 + 6 * 113])
        self.assertEqual(diagonal.digest(), repeated.digest())
        self.assertEqual(diagonal.snapshot()["tick_hz"], TICK_HZ)
        # An immutable detached UI snapshot cannot corrupt authoritative gameplay.
        projected = diagonal.snapshot()
        projected["hero"]["hp"] = 0
        self.assertEqual(diagonal.hero["hp"], 12)
        self.assertEqual(diagonal.digest(),
                         ActionRuntime.from_recording(diagonal.recording()).digest())

    def test_walls_bounds_and_dynamic_actors_block_movement(self):
        blocked = ActionRuntime(scene(walls=[[2, 1]]))
        for _ in range(12):
            self.command(blocked, dx=1)
        self.assertLess(blocked.hero["pos"][0] + 240, 2 * SCALE)
        self.assertEqual(blocked.hero["pos"][1], 1500)
        dynamic = ActionRuntime(scene(enemies=[enemy(hp=9)]))
        for _ in range(4):
            self.command(dynamic, dx=1)
        separation = abs(dynamic.hero["pos"][0] - dynamic.enemies["wolf"]["pos"][0])
        self.assertGreaterEqual(separation, 480)

    def test_attack_cooldown_enemy_death_and_reward_once(self):
        game = ActionRuntime(scene(enemies=[enemy()]))
        first = self.command(game, dx=1, attack=True)
        self.assertTrue(any(row["kind"] == "enemy_hit" for row in first))
        self.assertEqual(game.enemies["wolf"]["hp"], 1)
        self.command(game, attack=True)
        self.assertEqual(game.enemies["wolf"]["hp"], 1, "Cooldown must prevent spam")
        for _ in range(11):
            self.command(game)
        second = self.command(game, attack=True)
        self.assertTrue(any(row["kind"] == "enemy_dead" for row in second))
        self.assertEqual(game.inventory["coin"], 1)
        for _ in range(24):
            self.command(game, attack=True)
        self.assertEqual(game.inventory["coin"], 1)
        self.assertTrue(game.flags["defeated:wolf"])
        self.assertEqual(game.enemies["wolf"]["state"], "dead")

    def test_guard_dodge_stamina_and_temporary_invulnerability(self):
        guarded = ActionRuntime(scene(enemies=[enemy(hp=5)]))
        all_events = []
        for _ in range(8):
            all_events += self.command(guarded, guard=True)
        self.assertIn("guard", [event["kind"] for event in all_events])
        self.assertEqual(guarded.hero["hp"], 12)
        before = guarded.hero["hp"]
        self.command(guarded, dodge=True)
        self.assertEqual(guarded.hero["dodge_left"], 6)
        self.assertGreater(guarded.hero["invulnerable"], 0)
        self.assertLess(guarded.hero["stamina"], 100)
        for _ in range(4):
            self.command(guarded)
        self.assertEqual(guarded.hero["hp"], before)

    def test_enemy_patrol_chase_damage_and_stable_replay(self):
        game = ActionRuntime(scene(enemies=[
            enemy(pos=[4, 1], hp=5, patrol=[[4, 1], [4, 2]])
        ], hero={"pos": [1, 1], "hp": 20}))
        events = []
        for _ in range(42):
            events += self.command(game)
        self.assertIn("enemy_attack", [row["kind"] for row in events])
        self.assertLess(game.hero["hp"], 20)
        self.assertIn(game.enemies["wolf"]["state"], ("attack", "chase"))
        self.assertEqual(game.digest(), ActionRuntime.from_recording(game.recording()).digest())

    def test_objects_require_distance_keys_and_one_shot_loot(self):
        game = ActionRuntime(scene(objects=[
            {"id": "chest", "kind": "chest", "pos": [1, 2],
             "item": "key", "requires": ""},
            {"id": "door", "kind": "door", "pos": [2, 1],
             "item": "", "requires": "key"},
        ]))
        events = self.command(game, interact="door")
        self.assertEqual(events[0]["kind"], "interaction_locked")
        self.command(game, interact="chest")
        self.assertEqual(game.inventory["key"], 1)
        self.command(game, interact="chest")
        self.assertEqual(game.inventory["key"], 1, "No duplicate chest reward")
        self.command(game, interact="door")
        self.assertEqual(game.inventory["key"], 0)
        self.assertTrue(game.flags["opened:door"])
        self.assertTrue(game.objects["door"]["opened"])

    def test_invalid_actions_rollback_and_strict_tick_order(self):
        game = ActionRuntime(scene())
        old = game.recording()
        for bad in ({"tick": 2}, {"tick": 1, "dx": True},
                    {"tick": 1, "attack": 1}, {"tick": 1, "interact": "missing"}):
            with self.assertRaises(ActionError):
                game.step(bad)
            self.assertEqual(game.recording(), old)
        self.command(game)
        with self.assertRaises(ActionError):
            game.step({"tick": 1})

    def test_save_resume_detects_changed_rules_tamper_and_truncated_json(self):
        game = ActionRuntime(scene(objects=[
            {"id": "chest", "kind": "chest", "pos": [1, 2],
             "item": "key", "requires": ""}
        ]))
        self.command(game, dx=1)
        self.command(game, interact="chest")
        with TemporaryDirectory() as tmp:
            slot = Path(tmp) / "r26_action.json"
            game.save(slot)
            saved = slot.read_bytes()
            resumed = ActionRuntime.load(slot, expected_scene=game.scene)
            self.assertEqual(resumed.digest(), game.digest())
            self.assertEqual(saved, slot.read_bytes(), "Loading must not rewrite saves")
            self.command(resumed, dy=1)
            self.assertNotEqual(resumed.digest(), game.digest())
            changed_scene = deepcopy(game.scene)
            changed_scene["id"] = "different"
            with self.assertRaises(ActionError):
                ActionRuntime.load(slot, expected_scene=changed_scene)
            tampered = json.loads(saved.decode("utf-8"))
            tampered["commands"][0]["dx"] = 0
            slot.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(ActionError):
                ActionRuntime.load(slot)
            slot.write_text('{"version":', encoding="utf-8")
            with self.assertRaises(ActionError):
                ActionRuntime.load(slot)

    def test_replay_rejects_forged_clock_even_with_forged_state_hash(self):
        game = ActionRuntime(scene())
        self.command(game, dx=1)
        bad = game.recording()
        bad["commands"][0]["tick"] = 7
        with self.assertRaises(ActionError):
            ActionRuntime.from_recording(bad)


if __name__ == "__main__":
    unittest.main()

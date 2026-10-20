"""Headless R65.A regression: fixed tick, collisions, combo, parry and replay."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from sporebound.action_runtime import ActionError, ActionRuntime
from sporebound.action_combat_r65 import ActionCombatR65, validate_combat_rules


def rules():
    return {
        "version": 1,
        "combo": [
            {"windup": 1, "active": 2, "recovery": 2, "range": 1250,
             "damage": 2, "stagger": 5, "burn_ticks": 25},
            {"windup": 1, "active": 1, "recovery": 2, "range": 1250,
             "damage": 3, "stagger": 8, "burn_ticks": 0},
        ],
        "projectile": {"speed": 900, "ttl": 12, "cooldown": 8,
                       "damage": 2, "stagger": 4, "burn_ticks": 0},
    }


def scene(*, enemies=None, walls=None, hero=None):
    return {
        "id": "r65_arena", "width": 8, "height": 8,
        "walls": [] if walls is None else walls,
        "hero": hero if hero is not None else {"pos": [1, 1], "hp": 20},
        "enemies": [] if enemies is None else enemies,
        "objects": [],
    }


def enemy(name="guard", *, x=2, y=1, hp=12):
    return {"id": name, "pos": [x, y], "hp": hp, "patrol": []}


class ActionCombatR65Tests(unittest.TestCase):
    def advance(self, runner, **extra):
        return runner.step({"tick": runner.tick + 1, **extra})

    def test_strict_rules_copy_and_invalid_inputs(self):
        spec = rules()
        game = ActionCombatR65(scene(), spec)
        spec["combo"][0]["damage"] = 500
        self.assertEqual(game.rules["combo"][0]["damage"], 2)
        for broken in (
            {**rules(), "unknown": 1},
            {**rules(), "version": True},
            {**rules(), "combo": []},
            {**rules(), "combo": [dict(rules()["combo"][0], damage=True)]},
            {**rules(), "projectile": dict(rules()["projectile"], speed=10000)},
        ):
            with self.subTest(broken=broken), self.assertRaises(ActionError):
                validate_combat_rules(broken)
        before = game.recording()
        for invalid in ({"tick": 2}, {"tick": 1, "fire": 1},
                        {"tick": 1, "parry": "yes"}, {"tick": 1, "spell": "eval"},
                        {"tick": 1, "interact": "missing", "parry": True}):
            with self.subTest(invalid=invalid), self.assertRaises(ActionError):
                game.step(invalid)
            self.assertEqual(game.recording(), before)

    def test_melee_windup_single_hit_and_stagger(self):
        game = ActionCombatR65(scene(enemies=[enemy(hp=12)]), rules())
        self.advance(game, dx=1, attack=True)
        self.assertEqual(game.enemies["guard"]["hp"], 12, "windup cannot hit")
        self.advance(game)
        self.assertEqual(game.enemies["guard"]["hp"], 12)
        events = self.advance(game)
        self.assertTrue(any(e["kind"] == "enemy_hit" and e["source"] == "melee"
                            for e in events))
        self.assertEqual(game.enemies["guard"]["hp"], 10)
        self.assertGreater(game.enemies["guard"]["stun"], 0)
        for _ in range(2):
            self.advance(game)
        self.assertEqual(game.enemies["guard"]["hp"], 10,
                         "multi-tick active hitbox must not double-hit")

    def test_combo_can_queue_only_during_recovery(self):
        game = ActionCombatR65(scene(enemies=[enemy(hp=15)]), rules())
        self.advance(game, dx=1, attack=True)  # stage zero
        self.advance(game)                       # startup -> active
        self.advance(game)                       # hit
        self.advance(game)                       # active -> recovery
        self.advance(game, attack=True)          # queue stage one
        self.advance(game)                       # recovery -> stage one
        self.assertEqual(game.combo["stage"], 1)
        self.assertEqual(game.combo["phase"], "windup")
        self.advance(game)                       # windup -> active
        self.advance(game)                       # stage one hit
        self.assertEqual(game.enemies["guard"]["hp"], 10)
        self.assertEqual(game.digest(),
                         ActionCombatR65.from_recording(game.recording()).digest())

    def test_projectile_swept_collision_and_wall_occlusion(self):
        free = ActionCombatR65(scene(enemies=[enemy(x=3, hp=12)]), rules())
        hits = self.advance(free, dx=1, fire=True)
        for _ in range(8):
            hits += self.advance(free)
        self.assertTrue(any(e["kind"] == "enemy_hit" and e["source"] == "projectile"
                            for e in hits))
        self.assertEqual(free.inventory.get("coin", 0), 0)
        blocked = ActionCombatR65(scene(enemies=[enemy(x=3, hp=12)],
                                         walls=[[2, 1]]), rules())
        hits = self.advance(blocked, dx=1, fire=True)
        for _ in range(7):
            hits += self.advance(blocked)
        self.assertEqual(blocked.enemies["guard"]["hp"], 12)
        self.assertTrue(any(e["kind"] == "projectile_blocked" for e in hits))

    def test_parry_stuns_attacker_dodge_keeps_native_invulnerability(self):
        game = ActionCombatR65(scene(enemies=[enemy(hp=12)]), rules())
        self.advance(game)
        self.advance(game)
        self.advance(game)
        hp = game.hero["hp"]
        events = self.advance(game, parry=True)
        self.assertIn("hero_parry", [e["kind"] for e in events])
        self.assertEqual(game.hero["hp"], hp)
        self.assertGreater(game.enemies["guard"]["stun"], 0)
        self.assertLess(game.hero["stamina"], 100)
        dodging = ActionCombatR65(scene(enemies=[enemy(hp=12)]), rules())
        self.advance(dodging, dodge=True)
        self.assertGreater(dodging.hero["invulnerable"], 0)

    def test_status_burn_cannot_mint_extra_rewards(self):
        low = rules()
        low["combo"][0]["damage"] = 1
        game = ActionCombatR65(scene(enemies=[enemy(hp=2)]), low)
        self.advance(game, dx=1, attack=True)
        for _ in range(16):
            self.advance(game)
        self.assertEqual(game.enemies["guard"]["hp"], 0)
        self.assertEqual(game.inventory["coin"], 1)
        for _ in range(35):
            self.advance(game)
        self.assertEqual(game.inventory["coin"], 1)
        self.assertTrue(game.flags["defeated:guard"])

    def test_fps_independence_snapshot_defensive_copy_and_replay(self):
        commands = [{"tick": i + 1, "dx": 1 if i < 3 else 0,
                     "attack": i == 0, "fire": i in (2, 15),
                     "parry": i == 10} for i in range(40)]
        digests = []
        for frames_per_tick in (0.5, 1, 2):  # 30/60/120 display frames/sec
            game = ActionCombatR65(scene(enemies=[enemy(hp=12)]), rules())
            for command in commands:
                for _ in range(int(frames_per_tick)):
                    screen = game.snapshot()
                    screen["r65"]["combo"]["phase"] = "forged"
                game.step(command)
            digests.append(game.digest())
            self.assertEqual(game.digest(),
                             ActionCombatR65.from_recording(game.recording()).digest())
        self.assertEqual(len(set(digests)), 1)

    def test_atomic_checkpoint_integrity_and_legacy_unchanged(self):
        old = ActionRuntime(scene())
        old.step({"tick": 1, "attack": True})
        self.assertEqual(old.digest(),
                         ActionRuntime.from_recording(old.recording()).digest())
        game = ActionCombatR65(scene(enemies=[enemy()]), rules(),
                               initial_inventory={"key": 2})
        self.advance(game, dx=1, fire=True)
        self.advance(game, attack=True)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "r65.json"
            game.save(path)
            loaded = ActionCombatR65.load(path, expected_scene=game.scene,
                                           expected_rules=game.rules)
            self.assertEqual(loaded.digest(), game.digest())
            self.assertEqual(loaded.initial_inventory["key"], 2)
            self.advance(loaded)
            self.assertNotEqual(loaded.digest(), game.digest())
            tampered = json.loads(path.read_text(encoding="utf8"))
            tampered["rules"]["projectile"]["damage"] += 1
            path.write_text(json.dumps(tampered), encoding="utf8")
            with self.assertRaises(ActionError):
                ActionCombatR65.load(path)
            tampered = game.recording()
            tampered["commands"][0]["tick"] = 99
            with self.assertRaises(ActionError):
                ActionCombatR65.from_recording(tampered)
            different = deepcopy(game.rules)
            different["combo"][0]["damage"] += 1
            with self.assertRaises(ActionError):
                ActionCombatR65.from_recording(game.recording(),
                                               expected_rules=different)
            with self.assertRaises(ActionError):
                ActionCombatR65.from_recording(old.recording())


if __name__ == "__main__":
    unittest.main()

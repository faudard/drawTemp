"""R27.B runtime-and-Studio gates for canonical puzzle interactions."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.dungeon_authoring import DungeonStudio
from drawtemp.studio.map_authoring import MapStudio
from sporebound.engine import Battle
from sporebound.model import RuleError
from sporebound.tactical_rpg3 import authored_rules_for_document


class PuzzleRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.maps = MapStudio.reference()
        self.dungeon = DungeonStudio(self.maps)
        self.dungeon.create_dungeon("r27b", "Temple des mécanismes",
                                    width=16, height=16)
        self.dungeon.build_room((3, 3), (12, 12), entrance=(7, 3))
        self.maps.paint([(8, 8)], "goal")

    def battle(self, hero_pos):
        original = self.maps.snapshot()["content"]
        mission = next(m for m in original["missions"] if m["id"] == "r27b")
        hero = next(u for u in mission["units"] if u["team"] == "player")
        hero["pos"] = list(hero_pos)
        hero["speed"] = 50
        enemy = next(u for u in mission["units"] if u["team"] == "enemy")
        enemy["speed"] = 1
        rules = authored_rules_for_document(original)
        content = Content.from_dict(original, rules=rules)
        return Battle(content, "r27b", seed=17, rules=rules), hero["id"], rules

    def activate(self, battle, hero_id):
        for _ in range(1000):
            if battle.active_id == hero_id:
                return
            if battle.result or battle.active_id is None:
                self.fail("Battle finished before hero could act")
            battle.execute({"kind": "end", "unit": battle.active_id})
        self.fail("Hero did not activate")

    def interact(self, battle, hero_id, object_id):
        self.activate(battle, hero_id)
        battle.execute({"kind": "interact", "unit": hero_id,
                        "object": object_id})
        battle.execute({"kind": "end", "unit": hero_id})

    def test_key_unlocks_actual_door_and_replay_digest(self):
        self.dungeon.place_puzzle("key_a", "key", (7, 2), door_id="room_door")
        report = self.dungeon.puzzle_report()
        self.assertTrue(report["complete"])
        self.assertEqual(report["unreachable_goals"], [])
        self.assertIn("collect key_a", report["witness"])
        battle, hero_id, rules = self.battle((7, 2))
        self.interact(battle, hero_id, "key_a")
        self.activate(battle, hero_id)
        battle.execute({"kind": "interact", "unit": hero_id,
                        "object": "room_door"})
        self.assertTrue(next(o for o in battle.mission.objects
                             if o["id"] == "room_door")["open"])
        self.assertFalse(battle.board.tile((7, 3)).blocked)
        self.assertEqual(Battle.replay(battle.recording(), rules=rules).digest(),
                         battle.digest())

    def test_key_inside_locked_room_is_detected_as_unreachable(self):
        self.dungeon.place_puzzle("lost_key", "key", (8, 7),
                                  door_id="room_door")
        report = self.dungeon.puzzle_report()
        self.assertTrue(report["complete"])
        self.assertEqual(report["unreachable_goals"], [[8, 8]])
        self.assertIn("lost_key", report["unreachable_objects"])

    def test_switch_sequence_wrong_input_resets_and_saves(self):
        self.dungeon.place_object("s1", "switch", (6, 2),
                                  link="room_door")
        self.dungeon.place_object("s2", "switch", (8, 2),
                                  link="room_door")
        self.dungeon.set_sequence("room_door", ["s1", "s2"])
        report = self.dungeon.puzzle_report()
        self.assertEqual(report["unreachable_goals"], [])
        self.assertIn("sequence s1", report["witness"])
        self.assertIn("sequence s2", report["witness"])
        battle, hero_id, rules = self.battle((7, 2))
        self.interact(battle, hero_id, "s2")  # Wrong first step.
        door = next(o for o in battle.mission.objects
                    if o["id"] == "room_door")
        self.assertEqual(door["sequence_progress"], 0)
        self.assertFalse(door.get("open", False))
        self.interact(battle, hero_id, "s1")
        self.assertEqual(door["sequence_progress"], 1)
        self.assertTrue(next(o for o in battle.mission.objects
                             if o["id"] == "s1")["used"])
        self.interact(battle, hero_id, "s2")
        self.assertEqual(door["sequence_progress"], 2)
        self.assertTrue(door["open"])
        self.assertEqual(Battle.replay(battle.recording(), rules=rules).digest(),
                         battle.digest())

    def test_push_block_activates_latching_plate_and_replays(self):
        self.dungeon.place_puzzle("pad", "plate", (6, 2),
                                  door_id="room_door", latch=True)
        self.dungeon.place_puzzle("stone_box", "block", (7, 2))
        report = self.dungeon.puzzle_report()
        self.assertEqual(report["unreachable_goals"], [])
        self.assertGreater(report["states"], 0)
        # The pressure plate can also be reached by walking. The real push
        # command is tested separately, not inferred from a shortest witness.
        battle, hero_id, rules = self.battle((8, 2))
        self.activate(battle, hero_id)
        self.assertTrue(battle.board.tile((7, 3)).blocked)
        battle.execute({"kind": "puzzle_push", "object": "stone_box",
                        "direction": [-1, 0]})
        self.assertFalse(battle.board.tile((7, 3)).blocked)
        self.assertEqual(next(o for o in battle.mission.objects
                              if o["id"] == "stone_box")["pos"], [6, 2])
        self.assertEqual(Battle.replay(battle.recording(), rules=rules).digest(),
                         battle.digest())

    def test_invalid_push_rolls_back_all_runtime_state(self):
        self.dungeon.place_puzzle("stone_box", "block", (7, 2))
        battle, hero_id, rules = self.battle((8, 2))
        self.activate(battle, hero_id)
        before = battle.digest()
        with self.assertRaises(RuleError):
            battle.execute({"kind": "puzzle_push", "object": "stone_box",
                            "direction": [1, 0]})
        self.assertEqual(battle.digest(), before)
        self.assertEqual(battle.commands, [])

    def test_bad_references_and_mixed_gate_policies_are_atomic(self):
        snapshot = self.maps.snapshot()
        with self.assertRaises(AuthoringError):
            self.dungeon.place_puzzle("broken", "key", (4, 2),
                                      door_id="unknown")
        self.assertEqual(self.maps.snapshot(), snapshot)
        with self.assertRaises(AuthoringError):
            self.dungeon.set_sequence("room_door", ["missing", "s2"])
        self.assertEqual(self.maps.snapshot(), snapshot)
        self.dungeon.place_puzzle("key_a", "key", (7, 2),
                                  door_id="room_door")
        current = self.maps.snapshot()
        with self.assertRaises(AuthoringError):
            self.dungeon.place_puzzle("pad", "plate", (6, 2),
                                      door_id="room_door")
        self.assertEqual(self.maps.snapshot(), current)

    def test_undo_redo_and_canonical_save_roundtrip(self):
        initial = self.maps.snapshot()
        self.dungeon.place_puzzle("pad", "plate", (6, 2),
                                  door_id="room_door")
        self.dungeon.place_puzzle("stone_box", "block", (7, 2))
        graph = self.dungeon.puzzle_graph()
        self.assertEqual(graph["revision"], self.maps.authoring.revision)
        self.assertIn({"from": "pad", "to": "room_door", "type": "plate"},
                      graph["edges"])
        self.maps.undo()
        self.assertFalse(any(o["kind"] == "block"
                             for o in self.maps.mission()["objects"]))
        self.maps.redo()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "r27b.json"
            self.maps.save_as(path)
            restored = MapStudio.open(path)
            restored.select_map("r27b")
            self.assertEqual(restored.mission(), self.maps.mission())
            self.assertEqual(DungeonStudio(restored).puzzle_report()
                             ["unreachable_goals"], [])
        self.assertNotEqual(initial["revision"], self.maps.snapshot()["revision"])


if __name__ == "__main__":
    unittest.main()

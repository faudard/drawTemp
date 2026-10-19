"""R27.A/R27.B incremental gates: canonical edits and bounded puzzle analysis."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.dungeon_authoring import DungeonStudio
from drawtemp.studio.map_authoring import MapStudio


class R27DungeonStudioTests(unittest.TestCase):
    def setUp(self):
        self.maps = MapStudio.reference()
        self.origin = self.maps.mission_id
        self.dungeon = DungeonStudio(self.maps)
        self.dungeon.create_dungeon(
            "r27_ruins", "Les ruines", width=16, height=16,
            from_map=self.origin)

    def room(self):
        self.dungeon.build_room((3, 3), (12, 12), entrance=(7, 3))
        self.maps.paint([(8, 8)], "goal")

    def test_create_dungeon_links_real_campaign_in_one_undo_step(self):
        graph = self.dungeon.world_graph()
        self.assertIn((self.origin, "r27_ruins"), graph["edges"])
        self.assertIn("r27_ruins", self.maps.map_ids())
        self.assertEqual(self.maps.mission_id, "r27_ruins")
        self.assertEqual(self.maps.mission()["board"]["tiles"], [])
        self.maps.undo()
        self.assertNotIn("r27_ruins", self.maps.map_ids())
        self.assertNotIn(
            "r27_ruins", next(m["next_missions"] for m in
                              self.maps.snapshot()["content"]["missions"]
                              if m["id"] == self.origin))
        self.maps.redo()
        self.maps.select_map("r27_ruins")
        self.assertIn((self.origin, "r27_ruins"),
                      self.dungeon.world_graph()["edges"])

    def test_room_has_real_door_and_shared_player_collision(self):
        self.room()
        mission = self.maps.mission()
        door = next(o for o in mission["objects"] if o["id"] == "room_door")
        self.assertEqual(door["kind"], "door")
        self.assertTrue(door["locked"])
        self.assertEqual(door["pos"], [7, 3])
        tiles = {tuple(t["pos"]): t for t in mission["board"]["tiles"]}
        self.assertTrue(tiles[(7, 3)]["blocked"])
        self.assertEqual(tiles[(7, 3)]["feature"], "")
        self.assertEqual(tiles[(3, 7)]["feature"], "stone_wall")
        self.assertFalse(tiles[(8, 8)]["blocked"])
        self.assertIsInstance(Content.from_dict(self.maps.snapshot()["content"]),
                              Content)

    def test_switch_outside_room_reaches_chest_and_goal(self):
        self.room()
        report = self.dungeon.puzzle_report()
        self.assertTrue(report["complete"])
        self.assertEqual(report["unreachable_goals"], [[8, 8]])
        self.dungeon.place_object("lever1", "switch", (7, 2), link="room_door")
        self.dungeon.place_object("treasure", "chest", (8, 7), amount=120)
        solved = self.dungeon.puzzle_report()
        self.assertTrue(solved["complete"])
        self.assertEqual(solved["unreachable_goals"], [])
        self.assertEqual(solved["unreachable_objects"], [])
        self.assertEqual(solved["reachable_goals"], [[8, 8]])
        self.maps.undo()  # Chest removal, switch still unlocks the door.
        self.assertEqual(self.dungeon.puzzle_report()["unreachable_goals"], [])
        self.maps.undo()  # Undo the lever: closed door is no longer passable.
        self.assertEqual(self.dungeon.puzzle_report()["unreachable_goals"],
                         [[8, 8]])
        self.maps.redo()
        self.maps.redo()
        self.assertEqual(self.dungeon.puzzle_report()["unreachable_goals"], [])

    def test_switch_inside_a_locked_room_reports_softlock_risk(self):
        self.room()
        self.dungeon.place_object("lever1", "switch", (7, 5), link="room_door")
        report = self.dungeon.puzzle_report()
        self.assertTrue(report["complete"])
        self.assertIn("lever1", report["unreachable_objects"])
        self.assertIn([8, 8], report["unreachable_goals"])

    def test_invalid_room_or_link_is_atomic(self):
        original = self.maps.snapshot()
        with self.assertRaises((AuthoringError, ValueError)):
            self.dungeon.build_room((2, 2), (3, 3), entrance=(2, 3))
        self.assertEqual(self.maps.snapshot(), original)
        with self.assertRaises((AuthoringError, ValueError)):
            self.dungeon.link_maps("missing")
        self.assertEqual(self.maps.snapshot(), original)
        self.room()
        committed = self.maps.snapshot()
        with self.assertRaises((AuthoringError, ValueError)):
            self.dungeon.build_room((4, 4), (10, 10), entrance=(7, 4))
        self.assertEqual(self.maps.snapshot(), committed)
        with self.assertRaises((AuthoringError, ValueError)):
            self.dungeon.place_object("badlever", "switch", (2, 2),
                                      link="unknown_door")
        self.assertEqual(self.maps.snapshot(), committed)

    def test_puzzle_state_budget_never_reports_false_success(self):
        self.room()
        inconclusive = self.dungeon.puzzle_report(state_budget=1)
        self.assertFalse(inconclusive["complete"])
        self.assertTrue(any("budget" in w.lower()
                            for w in inconclusive["warnings"]))

    def test_canonical_save_roundtrip_without_new_sidecar(self):
        self.room()
        self.dungeon.place_object("lever1", "switch", (7, 2), link="room_door")
        documents = self.maps.snapshot()
        with TemporaryDirectory() as tmp:
            content_file = Path(tmp) / "r27.json"
            self.maps.save_as(content_file)
            restored = MapStudio.open(content_file)
            restored.select_map("r27_ruins")
            self.assertEqual(restored.mission(), self.maps.mission())
            self.assertEqual(
                GameProject.from_dict(
                    restored.snapshot()["project"],
                    Content.from_dict(restored.snapshot()["content"])).to_dict(),
                documents["project"])
            self.assertFalse(restored.snapshot()["dirty"])
            self.assertEqual(DungeonStudio(restored).puzzle_report()
                             ["unreachable_goals"], [])


if __name__ == "__main__":
    unittest.main()

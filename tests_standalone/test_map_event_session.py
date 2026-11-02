"""Editor/Events map-mode contracts: shared session and safe selection."""
import unittest

from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.map_event_session import MapEventSession


class MapEventSessionTests(unittest.TestCase):
    def setUp(self):
        self.map = MapStudio.reference()
        self.events = MapEventSession(self.map)

    def test_clicking_empty_cell_does_not_paint_or_create_event(self):
        before = self.map.snapshot()
        self.assertEqual(self.events.select_cell(1, 1), "")
        self.assertEqual(self.events.focus_cell, (1, 1))
        self.assertEqual(self.map.snapshot(), before)

    def test_create_inspect_and_undo_use_one_shared_authoring_session(self):
        self.events.select_cell(1, 1)
        self.events.create_at_focus("map_event_11", "Hello!")
        self.assertEqual(self.events.selected_id, "map_event_11")
        self.assertTrue(any(marker["event_id"] == "map_event_11"
                            for marker in self.events.markers()))
        self.assertIn("map_event_11", [row["id"] for row in self.map.mission()["triggers"]])
        self.map.authoring.undo()
        self.assertNotIn("map_event_11", [row["id"] for row in self.map.mission()["triggers"]])
        self.assertEqual(self.events.events(), [])
        self.assertEqual(self.events.selected_id, "")

    def test_edit_message_and_delete_are_undoable(self):
        self.events.select_cell(2, 1)
        self.events.create_at_focus("map_message", "Before")
        self.events.replace_first_message("After")
        self.assertEqual(self.events.events_studio.event(
            self.events.mission_id, "map_message")["actions"][0]["text"], "After")
        self.map.authoring.undo()
        self.assertEqual(self.events.events_studio.event(
            self.events.mission_id, "map_message")["actions"][0]["text"], "Before")
        self.events.delete_selected()
        self.assertFalse(any(e["id"] == "map_message" for e in self.events.events()))
        self.map.authoring.undo()
        self.assertTrue(any(e["id"] == "map_message" for e in self.events.events()))

    def test_invalid_cell_and_duplicate_id_do_not_modify_content(self):
        self.assertRaises(ValueError, self.events.select_cell, -1, 0)
        self.events.select_cell(2, 2)
        self.events.create_at_focus("duplicated_event", "Hello")
        before = self.map.snapshot()
        with self.assertRaises(ValueError):
            self.events.create_at_focus("duplicated_event", "Again")
        self.assertEqual(self.map.snapshot(), before)

    def test_mission_switch_clears_event_and_cell_selection(self):
        self.events.select_cell(1, 1)
        self.events.create_at_focus("map_switch_event", "Hello")
        self.map.create("other_map_for_events", "Other map", 6, 6)
        self.assertEqual(self.events.mission_id, "other_map_for_events")
        self.assertEqual(self.events.selected_id, "")
        self.assertIsNone(self.events.focus_cell)
        self.assertFalse(self.events.events())


if __name__ == "__main__":
    unittest.main()

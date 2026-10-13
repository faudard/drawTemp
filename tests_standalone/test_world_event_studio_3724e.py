"""3.7.24E: headless visual Studio authoring of canonical road events."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.world_event_authoring import (
    authored_roads, closest_road, delete_road_event, events_on_road,
    preview_road_event, set_road_choice, upsert_road_event,
)
from sporebound.world_map import default_world


class WorldEventAuthoringTests(TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.project.world = default_world(self.content, self.project.campaigns)
        self.project.story = {"scenes": [{
            "id": "road_scene", "title": "La caravane",
            "speaker": "Marchande", "text": "Choisissez votre chemin.",
            "choices": [
                {"id": "forward", "label": "Poursuivre"},
                {"id": "back", "label": "Revenir"},
                {"id": "fork", "label": "Prendre une autre route",
                 "effects": [{"kind": "unlock_mission", "mission": "hold"}]},
            ],
        }]}
        self.start = self.project.campaigns[0]["start_mission"]
        self.end = self.content.missions[self.start].next_missions[0]
        self.assertIn((self.start, self.end),
                      authored_roads(self.project.world, self.content))
        self.original_content = deepcopy(self.content.to_dict())

    def _new(self, event_id, step=2):
        return {"id": event_id, "from": self.start, "to": self.end,
                "scene": "road_scene", "step": step}

    def save(self, event, *, original_id=None):
        self.project.world = upsert_road_event(
            self.project.world, self.content, self.project.campaigns,
            self.project.story, event, original_id=original_id)
        self.project.validate(self.content)

    def test_create_many_edit_choices_preview_and_save_roundtrip(self):
        self.save(self._new("merchant", step=2))
        self.save(self._new("toll", step=6))
        self.assertEqual([x["id"] for x in events_on_road(
            self.project.world, self.start, self.end)], ["merchant", "toll"])
        self.project.world = set_road_choice(
            self.project.world, self.content, self.project.campaigns,
            self.project.story, "merchant", "back", "return")
        self.project.world = set_road_choice(
            self.project.world, self.content, self.project.campaigns,
            self.project.story, "merchant", "fork", "destination", "hold")
        preview = preview_road_event(self.project.world, self.project.story,
                                     "merchant")
        self.assertIn("La caravane", preview)
        self.assertIn("revenir au carrefour", preview)
        self.assertIn("bifurquer vers hold", preview)
        self.assertIn("1 effet(s) StoryBook", preview)
        self.assertEqual(self.original_content, self.content.to_dict())
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "travel.game.json"
            self.project.save(path, self.content)
            restored = GameProject.load(path, self.content)
            self.assertEqual(restored.world, self.project.world)
            self.assertEqual(restored.story, self.project.story)

    def test_edit_selected_event_preserves_others_and_updates_id(self):
        self.save(self._new("first"))
        self.save(self._new("second", 6))
        renamed = self._new("renamed", 3)
        self.save(renamed, original_id="first")
        self.assertEqual(
            {x["id"] for x in self.project.world["events"]},
            {"renamed", "second"})
        self.project.world = delete_road_event(
            self.project.world, self.content, self.project.campaigns,
            self.project.story, "second")
        self.assertEqual(self.project.world["events"], [renamed])
        self.project.world = delete_road_event(
            self.project.world, self.content, self.project.campaigns,
            self.project.story, "renamed")
        self.assertNotIn("events", self.project.world)

    def test_duplicate_physical_position_and_unknown_choices_are_atomic(self):
        self.save(self._new("first", step=2))
        old = deepcopy(self.project.world)
        failures = [
            self._new("second", step=2),
            {**self._new("reverse", step=6),
             "from": self.end, "to": self.start},
            {**self._new("invalid", step=6), "scene": "missing_scene"},
            {**self._new("invalid", step=6), "step": 0},
            {**self._new("invalid", step=6), "to": self.start},
        ]
        for event in failures:
            with self.subTest(event=event), self.assertRaises(RuleError):
                upsert_road_event(self.project.world, self.content,
                                  self.project.campaigns, self.project.story,
                                  event)
            self.assertEqual(self.project.world, old)
        for choice, kind, target in (
                ("absent", "continue", ""),
                ("forward", "shortcut", ""),
                ("fork", "destination", "missing"),
                ("fork", "destination", self.start)):
            with self.subTest(choice=choice, kind=kind), self.assertRaises(RuleError):
                set_road_choice(self.project.world, self.content,
                                self.project.campaigns, self.project.story,
                                "first", choice, kind, target)
            self.assertEqual(self.project.world, old)

    def test_continue_is_default_and_restores_original_choice_route(self):
        self.save(self._new("first"))
        updated = set_road_choice(self.project.world, self.content,
                                  self.project.campaigns, self.project.story,
                                  "first", "back", "return")
        updated = set_road_choice(updated, self.content,
                                  self.project.campaigns, self.project.story,
                                  "first", "back", "continue")
        self.assertNotIn("routes", updated["events"][0])
        self.assertEqual(self.project.world["events"][0],
                         updated["events"][0])

    def test_map_hit_test_only_picks_canonical_roads(self):
        positions = {row["mission"]: (row["x"], row["y"])
                     for row in self.project.world["nodes"]}
        ax, ay = positions[self.start]
        bx, by = positions[self.end]
        selected = closest_road(
            self.project.world, self.content, ((ax + bx) / 2, (ay + by) / 2))
        self.assertEqual(selected, (self.start, self.end))
        self.assertIsNone(closest_road(self.project.world, self.content,
                                       (-500, -500)))

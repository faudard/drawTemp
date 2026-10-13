"""3.7.24A World Map gates: authoring, navigation, validation, save compatibility."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject, load_slot, save_slot
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.world_map import (
    WORLD_THEMES, default_world, remove_location, upsert_location,
    validate_world, world_hit_test, world_projection)


class WorldMapTests(TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.legacy = GameProject.default(self.content)
        self.world = default_world(self.content, self.legacy.campaigns)

    def test_default_is_opt_in_and_legacy_project_roundtrips_exactly(self):
        raw = self.legacy.to_dict()
        self.assertNotIn("world", raw)
        self.assertEqual(GameProject.from_dict(raw, self.content).to_dict(), raw)
        self.assertEqual(self.legacy.world, {})
        self.assertEqual(set(self.world), {"width", "height", "theme", "nodes"})
        self.assertEqual({n["mission"] for n in self.world["nodes"]},
                         set(self.content.missions))

    def test_world_manifest_save_reopen_without_content_or_campaign_changes(self):
        content_before = deepcopy(self.content.to_dict())
        old = deepcopy(self.legacy.to_dict())
        project = GameProject.from_dict({**old, "world": self.world}, self.content)
        self.assertEqual(project.world, self.world)
        self.assertEqual(self.content.to_dict(), content_before)
        self.assertEqual(project.campaigns, self.legacy.campaigns)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "jeanne.game.json"
            project.save(path, self.content)
            reopened = GameProject.load(path, self.content)
            self.assertEqual(reopened.to_dict(), project.to_dict())
            # World layout is not part of the Campaign slot schema.
            progress = reopened.new_game(reopened.campaigns[0]["id"], self.content)
            slot = save_slot(path, reopened, self.content,
                             reopened.campaigns[0]["id"], 1, progress)
            loaded = load_slot(path, reopened, self.content,
                               reopened.campaigns[0]["id"], 1)
            self.assertTrue(slot.exists())
            self.assertEqual(loaded.to_dict(), progress.to_dict())
        self.assertEqual(self.content.to_dict(), content_before)

    def test_drag_region_and_removal_do_not_rewrite_tactical_links(self):
        before = deepcopy(self.content.to_dict())
        old_world = deepcopy(self.world)
        mid = self.world["nodes"][0]["mission"]
        moved = upsert_location(
            self.world, self.content, self.legacy.campaigns,
            mid, (242, 242), region="Royaume de France")
        self.assertEqual(self.world, old_world)
        place = next(n for n in moved["nodes"] if n["mission"] == mid)
        self.assertEqual((place["x"], place["y"]), (242, 242))
        self.assertEqual(place["region"], "Royaume de France")
        self.assertEqual(self.content.to_dict(), before)
        self.assertEqual(
            world_projection(moved, self.content)["edges"],
            world_projection(old_world, self.content)["edges"])
        if len(self.world["nodes"]) > 1:
            removable = next((n["mission"] for n in moved["nodes"]
                              if n["mission"] not in {
                                  c["start_mission"] for c in self.legacy.campaigns}), None)
            if removable:
                changed = remove_location(
                    moved, self.content, self.legacy.campaigns, removable)
                self.assertNotIn(removable, [n["mission"] for n in changed["nodes"]])
                self.assertIn(removable, self.content.missions)

    def test_invalid_world_rejected_atomically(self):
        old = deepcopy(self.world)
        mid = self.world["nodes"][0]["mission"]
        cases = [
            {"nodes": [*self.world["nodes"], deepcopy(self.world["nodes"][0])]},
            {"nodes": [{**self.world["nodes"][0], "mission": "invalid_mission"},
                       *self.world["nodes"][1:]]},
            {"nodes": [{**self.world["nodes"][0], "x": True},
                       *self.world["nodes"][1:]]},
            {"nodes": [{**self.world["nodes"][0], "y": 99999},
                       *self.world["nodes"][1:]]},
            {"theme": "invalid_theme"},
            {"nodes": []},
        ]
        for updates in cases:
            candidate = {**deepcopy(self.world), **updates}
            with self.subTest(updates=updates), self.assertRaises(RuleError):
                validate_world(candidate, self.content, self.legacy.campaigns)
            self.assertEqual(self.world, old)
        with self.assertRaises(RuleError):
            upsert_location(self.world, self.content, self.legacy.campaigns,
                            mid, (-1, 0))
        self.assertEqual(self.world, old)

    def test_world_projection_never_unlocks_a_mission(self):
        # Headless GameSession is authoritative; the map only visualizes
        # the actually available IDs and cannot grant extra unlocks.
        project = GameProject.from_dict(
            {**self.legacy.to_dict(), "world": self.world}, self.content)
        session = GameSession.new(self.content, project, project.campaigns[0]["id"])
        available = set(session.available_missions())
        projected = world_projection(
            project.world, self.content, available=available,
            completed=session.progress.completed)
        for node in projected["nodes"]:
            if node["mission"] in available:
                self.assertEqual(node["status"], "available")
            else:
                self.assertEqual(node["status"], "locked")
        for a, b in projected["edges"]:
            self.assertIn(b, self.content.missions[a].next_missions)
        if any(m["mission"] not in available for m in projected["nodes"]):
            locked = next(m["mission"] for m in projected["nodes"]
                          if m["mission"] not in available)
            with self.assertRaises(RuleError):
                session.start_mission(locked)
        first = projected["nodes"][0]
        self.assertEqual(world_hit_test(
            projected, (first["x"], first["y"])), first["mission"])
        self.assertIsNone(world_hit_test(projected, (-99, -99)))
        available_id = next(iter(available))
        session.start_mission(available_id)
        self.assertEqual(session.active_battle.mission.id, available_id)

    def test_all_themes_are_defined(self):
        from sporebound.world_map_view import THEMES
        self.assertEqual(set(THEMES), set(WORLD_THEMES))

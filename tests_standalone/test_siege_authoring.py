"""2.5.4.1 siege plan authoring, strict schemas, Player persistence and replay."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController
from sporebound.siege_authoring import (
    delete_front, delete_route, new_plan, put_front, put_route,
    set_focus, set_logistics, strategy_preview, validate_plan)


class SiegeAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.ids = sorted(self.content.missions)
        self.assertGreaterEqual(len(self.ids), 2)
        self.first, self.second = self.ids[:2]
        self.plan = new_plan(self.content, self.first, self.second)

    def test_validate_roundtrip_and_preserve_v1_default(self):
        original = self.project.to_dict()
        self.assertNotIn("sieges", original)
        project_data = deepcopy(original)
        project_data["sieges"] = {"main": self.plan}
        restored = GameProject.from_dict(project_data, self.content)
        self.assertEqual(restored.to_dict()["sieges"]["main"], self.plan)
        self.assertEqual(self.project.to_dict(), original)
        with self.assertRaises(RuleError):
            GameProject.from_dict({**original, "sieges": {"unknown": self.plan}},
                                  self.content)

    def test_front_and_routes_are_atomic_and_checked(self):
        before = deepcopy(self.plan)
        with self.assertRaises(RuleError):
            put_front(self.plan, self.content, "third", self.second, 4, 5, "hold")
        with self.assertRaises(RuleError):
            put_front(self.plan, self.content, "third", "missing", 4, 5, "hold")
        with self.assertRaises(RuleError):
            put_front(self.plan, self.content, "third", self.first, -1, 5, "hold")
        with self.assertRaises(RuleError):
            put_route(self.plan, self.content, self.first, self.first, 2)
        with self.assertRaises(RuleError):
            put_route(self.plan, self.content, "reserve", self.second, 0)
        self.assertEqual(self.plan, before)
        updated = put_route(self.plan, self.content, "reserve", self.second, 2)
        self.assertEqual(updated["logistics"]["routes"][0]["turns"], 2)
        updated = put_route(updated, self.content, "reserve", self.second, 3)
        self.assertEqual(len(updated["logistics"]["routes"]), 1)
        self.assertEqual(updated["logistics"]["routes"][0]["turns"], 3)
        updated = delete_route(updated, self.content, "reserve", self.second)
        self.assertFalse(updated["logistics"]["routes"])
        updated = set_logistics(updated, self.content, 8, 0, 2)
        self.assertEqual(updated["logistics"]["capacity"], 2)
        self.assertEqual(self.plan, before)

    def test_preview_does_not_mutate_and_focus_is_respected(self):
        first, second = self.first, self.second
        plan = set_focus(self.plan, self.content, second)
        before = deepcopy(plan)
        frames = strategy_preview(plan, self.content, 5)
        self.assertEqual(len(frames), 6)
        self.assertEqual(frames[5]["turn"], 5)
        self.assertEqual(frames[5]["fronts"][second]["opposition"], 10)
        self.assertEqual(plan, before)
        with self.assertRaises(RuleError):
            strategy_preview(plan, self.content, 31)
        with self.assertRaises(RuleError):
            delete_front(plan, self.content, first)

    def test_player_launch_respects_unlocks_and_checkpoint(self):
        # Campaigns start with just one unlocked mission; a siege must not
        # bypass story progression or enable arbitrary locked missions.
        project_data = self.project.to_dict()
        project_data["sieges"] = {"main": self.plan}
        project = GameProject.from_dict(project_data, self.content)
        with TemporaryDirectory() as folder:
            player = PlayerController(self.content, project, Path(folder) / "demo.game.json")
            session = player.new_game("main", 1)
            original = deepcopy(session.recording())
            with self.assertRaises(RuleError):
                player.start_configured_siege()
            self.assertEqual(player.session.recording(), original)
            # Add the actual front mission unlocks as if story gates completed.
            player.session.progress.unlocked = list(dict.fromkeys(
                player.session.progress.unlocked + [self.first, self.second]))
            player.save()
            player.start_configured_siege()
            self.assertEqual(player.session.mode, "fronts")
            self.assertEqual(player.session.fronts.missions, self.plan["missions"])
            self.assertEqual(player.session.fronts.timeline.focused, self.first)
            self.assertEqual(player.session.fronts.initial_specs, self.plan["specs"])
            restored = GameSession.load(player.path_for("main", 1), self.content, project)
            self.assertEqual(restored.recording(), player.session.recording())


if __name__ == "__main__":
    unittest.main()

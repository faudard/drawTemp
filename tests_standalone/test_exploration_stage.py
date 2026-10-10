"""Generic narrative exploration: backward compatibility, validation, and drawing."""
from copy import deepcopy
from pathlib import Path
import unittest

from sporebound.exploration import validate_exploration
from sporebound.exploration_view import draw_exploration, draw_story_backdrop
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound" / "content" / "jeanne.json"
PROJECT = ROOT / "sporebound" / "content" / "jeanne.game.json"
LEGACY = ROOT / "sporebound" / "content" / "core.json"


class DummyCanvas:
    def __init__(self):
        self.calls = []

    def delete(self, *args, **kwargs):
        self.calls.append("delete")

    def configure(self, *args, **kwargs):
        self.calls.append("configure")

    def create_rectangle(self, *args, **kwargs):
        self.calls.append("rectangle")

    def create_oval(self, *args, **kwargs):
        self.calls.append("oval")

    def create_line(self, *args, **kwargs):
        self.calls.append("line")

    def create_polygon(self, *args, **kwargs):
        self.calls.append("polygon")

    def create_text(self, *args, **kwargs):
        self.calls.append("text")


class ExplorationStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT)
        cls.project = GameProject.load(PROJECT, cls.content)

    def test_two_authored_stages_are_valid(self):
        self.assertEqual(set(self.project.exploration),
                         {"sc_p0_champs", "sc_p0_cendres"})
        validate_exploration(self.project.exploration, self.project.story)
        session = GameSession.new(self.content, self.project, "jeanne", seed=42)
        state = session.exploration_state()
        self.assertEqual(state["position"], [1, 5])
        self.assertEqual(state["theme"], "fields")
        self.assertEqual(len(state["interactions"]), 4)

    def test_invalid_coordinates_and_unreachable_exit_rejected(self):
        base = deepcopy(self.project.exploration)
        story = self.project.story
        invalid = deepcopy(base)
        invalid["sc_p0_champs"]["start"] = [30, 30]
        with self.assertRaises(RuleError):
            validate_exploration(invalid, story)
        invalid = deepcopy(base)
        invalid["sc_p0_champs"]["blocked"] = [
            [7, 3], [8, 3], [9, 3], [7, 4], [9, 4], [7, 5], [8, 5], [9, 5]]
        # The exit is at [8,4], isolated by its neighbors and itself reachable
        # only if there is a route around; no route should pass through blocked.
        with self.assertRaises(RuleError):
            validate_exploration(invalid, story)

    def test_legacy_project_has_no_exploration_or_schema_change(self):
        content = Content.load(LEGACY)
        project = GameProject.load(LEGACY.with_suffix(".game.json"), content)
        self.assertEqual(project.exploration, {})
        self.assertNotIn("exploration", project.to_dict())
        session = GameSession.new(content, project, "relique")
        self.assertIsNone(session.exploration_state())
        self.assertEqual(session.available_choices()[0]["id"], "guard")

    def test_renderer_only_reads_state(self):
        session = GameSession.new(self.content, self.project, "jeanne")
        stage = session.exploration_state()
        before = deepcopy(stage)
        canvas = DummyCanvas()
        draw_exploration(canvas, stage)
        self.assertEqual(stage, before)
        self.assertIn("rectangle", canvas.calls)
        self.assertIn("text", canvas.calls)
        for scene in ("sc_p0_visions", "sc_p0_fumee", "sc_p0_cendres"):
            canvas = DummyCanvas()
            self.assertTrue(draw_story_backdrop(canvas, scene, phase=3))
            self.assertIn("polygon", canvas.calls)
        self.assertFalse(draw_story_backdrop(DummyCanvas(), "not_jeanne"))


if __name__ == "__main__":
    unittest.main()

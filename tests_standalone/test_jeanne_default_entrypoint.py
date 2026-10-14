"""Jeanne is the only out-of-the-box player campaign; legacy fixtures stay opt-in."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from drawtemp.__main__ import main
from sporebound.__main__ import DEFAULT_CONTENT, DEFAULT_GAME_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.profile_paths import default_profile_path


class JeanneDefaultEntrypointTests(unittest.TestCase):
    def test_default_content_and_project_are_jeanne(self):
        self.assertEqual(DEFAULT_GAME_CONTENT.name, "jeanne.json")
        content = Content.load(DEFAULT_GAME_CONTENT)
        project = GameProject.load(DEFAULT_GAME_CONTENT.with_suffix(".game.json"), content)
        self.assertEqual([c["id"] for c in project.campaigns], ["jeanne"])
        self.assertEqual(project.campaigns[0]["start_mission"], next(iter(content.missions)))
        self.assertIn("Jeanne", project.title)
        self.assertNotIn("garden", content.missions)

    def test_cli_validates_jeanne_without_arguments(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["validate"]), 0)
        self.assertIn("Valid:", output.getvalue())

    def test_legacy_content_remains_opt_in(self):
        content = Content.load(DEFAULT_CONTENT)
        self.assertIn("garden", content.missions)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["validate", "--content", str(DEFAULT_CONTENT)]), 0)
        self.assertIn("Valid:", output.getvalue())

    def test_profile_path_preserves_legacy_campaign_slots(self):
        with tempfile.TemporaryDirectory() as home:
            with patch.object(Path, "home", return_value=Path(home)):
                current = Path(home) / ".drawtemp" / "jeanne.game.json"
                legacy = Path(home) / ".sporebound" / "jeanne.game.json"
                self.assertEqual(default_profile_path("jeanne.game.json"), current)
                legacy.with_name(legacy.stem + "_saves").mkdir(parents=True)
                self.assertEqual(default_profile_path("jeanne.game.json"), legacy)
                current.with_name(current.stem + "_session_saves").mkdir(parents=True)
                self.assertEqual(default_profile_path("jeanne.game.json"), current)


if __name__ == "__main__":
    unittest.main()

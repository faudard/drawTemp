"""R36.B3 opt-in authored R28/R36 action Player GUI boot in offscreen Qt."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
HAS_QT = importlib.util.find_spec("PySide6") is not None


@unittest.skipUnless(HAS_QT, "Requires optional PySide6")
class BoundActorQtTests(unittest.TestCase):
    def test_canonical_project_binds_hero_visual_pose_in_qml_smoke(self):
        from drawtemp.player.action_app import main
        from drawtemp.studio.animation_graph_authoring import AnimationControllerAuthoring
        from drawtemp.studio.animation_timeline_authoring import AnimationTimelineAuthoring
        from tests_standalone.test_r36_animation_graph import authored, graph
        from tests_standalone.test_r36_animation_timeline import timeline

        session = authored()
        controller = AnimationControllerAuthoring(session)
        controller.apply(controller.preview(graph()))
        markers = AnimationTimelineAuthoring(session)
        markers.apply(markers.preview(timeline()))
        with TemporaryDirectory() as directory:
            content_path = Path(directory) / "game.json"
            session.save_as(content_path)
            project_path = content_path.with_suffix(".game.json")
            self.assertTrue(project_path.is_file())
            from tests_standalone.test_r36_sprite_rendering import write_sprite_art
            write_sprite_art(Path(directory))
            report = Path(directory) / "cpu-profile.json"
            self.assertEqual(main([
                "--smoke", "--content", str(content_path),
                "--animation-project", str(project_path),
                "--hero-controller", "hero_animation",
                "--profile-r36", str(report),
                "--save-dir", directory]), 0)
            self.assertTrue(report.is_file())
            measured = json.loads(report.read_text(encoding="utf-8"))
            self.assertGreaterEqual(measured["samples"], 1)
            self.assertGreaterEqual(measured["max_actors"], 1)
            self.assertIsNotNone(measured["cpu_ms"])


if __name__ == "__main__":
    unittest.main()

"""R36.C2 screenshot candidate matrix cannot certify or self-approve itself."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.quality.r14_goldens import EXPECTED, case_id
from scripts.r36_visual_candidates import KIND, main


class R36CandidateContractTests(unittest.TestCase):
    def test_matrix_has_all_12_distinct_studio_player_dpi_zoom_cases(self):
        capture = StringIO()
        with redirect_stdout(capture):
            self.assertEqual(main(["matrix"]), 0)
        report = json.loads(capture.getvalue())
        self.assertEqual(report["kind"], KIND)
        self.assertEqual(len(report["cases"]), 12)
        self.assertEqual(set(report["cases"]), {case_id(*case) for case in EXPECTED})

    def test_approval_rejects_incomplete_or_conflicting_r36_evidence(self):
        with TemporaryDirectory() as folder:
            source = Path(folder)
            (source / "r36-visual.json").write_text(json.dumps({
                "kind": KIND, "capture_complete": False,
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "complete"):
                main(["approve", "--capture", folder, "--reviewer", "QA"])
            (source / "r36-visual.json").write_text(json.dumps({
                "kind": KIND, "capture_complete": True,
            }), encoding="utf-8")
            (source / "r14-visual.json").write_text("{}",
                                                   encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "differ"):
                main(["approve", "--capture", folder, "--reviewer", "QA"])

    @unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                         "Optional real Qt reference fixture")
    def test_reference_session_uses_real_pngs_and_valid_r36_r1_documents(self):
        from scripts.r36_visual_candidates import make_reference_session
        from drawtemp.player.action_controller import ActionPlayerController, demo_scene
        from drawtemp.assets.r36_runtime import R36PresentationAssets
        from drawtemp.render.iso_scene import scene_from_action, render_items, Camera, TopDownProjection

        with TemporaryDirectory() as folder:
            session, project_file = make_reference_session(folder)
            self.assertTrue(project_file.is_file())
            self.assertEqual(len(session.snapshot().to_dict()["project"][
                "extensions"]["org.drawtemp.animation"]["data"]["controllers"]), 1)
            project = session.snapshot().to_dict()["project"]
            player = ActionPlayerController(
                demo_scene(), animation_project=project,
                animation_bindings={"hero": "r36_demo"})
            player.step(attack=True)
            visual = scene_from_action(
                player.runtime, animation_frames=player.animation.frames())
            assets = R36PresentationAssets(
                player.animation.registry, Path(folder))
            rows = assets.decorate(render_items(
                visual, Camera(), TopDownProjection()))
            hero = next(row for row in rows
                        if row["kind"] == "actor" and row["id"] == "hero")
            self.assertEqual(hero["assetId"], "r36_s_attack")
            self.assertTrue(hero["spriteReady"])
            self.assertEqual(assets.diagnostics()["invalid"], 0)
            self.assertTrue((Path(folder) / "art/attack.png").is_file())


if __name__ == "__main__":
    unittest.main()

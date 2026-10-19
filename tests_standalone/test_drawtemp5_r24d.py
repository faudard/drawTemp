"""R24.D — independent second game, same Core/Studio/Player and fail-closed QA."""
from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject
from drawtemp.export.r15 import ExportError, export_game, preflight, verify_bundle
from drawtemp.export.templates import TEMPLATES, create_template
from drawtemp.quality.r24_platform import (
    PlatformGateError, R24_TRACE, second_game_software_report, source_paths,
)
from drawtemp.sdk import AuthoringSession, Simulation, certify_trace
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.replay import ReplayCommand, verify_recording


def second_game():
    a, b = source_paths()
    content = Content.from_dict(json.loads(a.read_text(encoding="utf-8")))
    project = GameProject.from_dict(json.loads(b.read_text(encoding="utf-8")), content)
    return content, project


class SecondGameGateTests(unittest.TestCase):
    def test_game_is_not_rebadged_jeanne(self):
        content, project = second_game()
        jeanne, legacy_project = reference_project()
        self.assertEqual(set(content.missions), {"signal_depot", "reactor_vault"})
        self.assertEqual(len(content.archetypes), 4)
        self.assertEqual(len(content.skills), 3)
        self.assertNotEqual(content.to_dict(), jeanne.to_dict())
        self.assertNotEqual(project.to_dict(), legacy_project.to_dict())
        self.assertEqual({row["team"] for row in content.to_dict()["missions"][0]["units"]},
                         {"player", "enemy"})
        self.assertTrue(all("jeanne" not in text.lower()
                            for text in json.dumps(content.to_dict()).split()))
        self.assertIn("org.drawtemp.example.asterion", project.extensions)
        self.assertEqual(GameProject.from_dict(project.to_dict(), content).to_dict(),
                         project.to_dict())

    def test_creator_template_open_and_atomic_editor_undo(self):
        self.assertIn("asterion", TEMPLATES)
        with TemporaryDirectory() as folder:
            root = Path(folder)
            output = create_template("asterion", root / "new-game")
            self.assertTrue(preflight(output / "game.json")["passed"])
            content = Content.load(output / "game.json")
            project = GameProject.load(output / "game.game.json", content)
            self.assertEqual(set(content.missions), {"signal_depot", "reactor_vault"})
            self.assertEqual(project.title, "Asterion — Les Veilleurs du Signal")
            studio = AuthoringSession.open(output / "game.json")
            before = studio.snapshot().to_dict()["project"]
            studio.apply(studio.preview_project(
                lambda p: {**p, "title": "Asterion — Projet personnalisé"}))
            studio.undo()
            self.assertEqual(studio.snapshot().to_dict()["project"], before)
            studio.redo()
            studio.save()
            reopened = AuthoringSession.open(output / "game.json")
            self.assertEqual(reopened.snapshot().project["title"],
                             "Asterion — Projet personnalisé")
            with self.assertRaises(ExportError):
                create_template("asterion", output)

    def test_actual_player_story_battle_checkpoint_and_replay(self):
        content, project = second_game()
        simulation = Simulation.new(content, project, "main", seed=17)
        self.assertEqual(simulation.snapshot().scene["id"], "briefing")
        self.assertEqual(simulation.snapshot().missions, ())
        simulation.choose_story_option("launch")
        self.assertIn("signal_depot", simulation.snapshot().missions)
        simulation.start_mission("signal_depot")
        self.assertEqual(simulation.snapshot().mode, "battle")
        simulation.execute({"kind": "end", "facing": [0, 1]})
        self.assertEqual(simulation.snapshot().mode, "battle")
        self.assertIsNotNone(simulation.snapshot().battle)
        recorded = simulation.recording()
        replayed = verify_recording(recorded, content, project)
        self.assertEqual(replayed.recording(), recorded)
        with TemporaryDirectory() as folder:
            save_file = Path(folder) / "save.json"
            simulation.save(save_file)
            loaded = Simulation.load(save_file, content, project)
            self.assertEqual(loaded.recording(), recorded)

    def test_full_software_matrix_is_green_without_fake_release(self):
        report = second_game_software_report()
        self.assertTrue(report["software_passed"])
        self.assertTrue(all(report["tests"].values()))
        self.assertEqual([row["seed"] for row in report["seeds"]], [1, 17, 221])
        self.assertTrue(all(len(row["rng_sha256"]) == 64 and
                            len(row["ct_sha256"]) == 64 for row in report["seeds"]))
        self.assertFalse(report["release_certified"])
        self.assertFalse(report["native_player_export_certified"])
        self.assertFalse(report["gpu_visual_certified"])
        self.assertFalse(report["art_licenses_certified"])
        self.assertGreaterEqual(len(report["release_blockers"]), 4)
        # No source data mutation occurred during certification.
        self.assertEqual(second_game()[1].title, "Asterion — Les Veilleurs du Signal")

    def test_r14_r15_export_proves_package_structure_only_not_native(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            output = create_template("asterion", root / "game")
            runtime = root / "runtime"
            runtime.mkdir()
            # Mock binary is deliberately NOT treated as clean-machine proof.
            native = "DrawTempPlayer.exe" if os.name == "nt" else "DrawTempPlayer"
            (runtime / native).write_bytes(b"unit-test-only-not-executable")
            bundle = export_game(output / "game.json", runtime, root / "bundle")
            manifest = verify_bundle(bundle)
            self.assertEqual(manifest["certification"], "R14 not certified")
            self.assertEqual(manifest["kind"], "drawtemp5-standalone-game")
            self.assertEqual(manifest["content"], "game/game.json")
            self.assertTrue((bundle / "game/game.game.json").is_file())
            # A corrupted asset/content cannot be distributed as a valid bundle.
            (bundle / "game/game.game.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ExportError):
                verify_bundle(bundle)

    def test_bad_inputs_and_incompatible_extension_fail_closed(self):
        with self.assertRaises(PlatformGateError) as caught:
            second_game_software_report(seeds=())
        self.assertEqual(caught.exception.code, "invalid_seeds")
        for seeds in ((1, 1), (-1,), ("17",)):
            with self.subTest(seeds=seeds), self.assertRaises(PlatformGateError):
                second_game_software_report(seeds=seeds)
        with TemporaryDirectory() as folder:
            root = Path(folder)
            output = create_template("asterion", root / "game")
            p = output / "game.game.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            data["extensions"]["org.drawtemp.example.asterion"]["schema_version"] = 2
            p.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(PlatformGateError):
                second_game_software_report(content_path=output / "game.json")
            self.assertFalse(preflight(output / "game.json")["passed"])

    def test_cli_headless_and_release_gate_explicitly_blocked(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            report_file = root / "report.json"
            env = dict(os.environ)
            command = [sys.executable, "-m", "scripts.certify_r24_second_game",
                       "--report", str(report_file)]
            result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, env=env, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(report_file.read_text(encoding="utf-8"))
            self.assertTrue(report["software_passed"])
            self.assertFalse(report["release_certified"])
            strict = subprocess.run(
                [sys.executable, "-m", "scripts.certify_r24_second_game",
                 "--require-release"],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True, text=True, env=env, timeout=90)
            self.assertEqual(strict.returncode, 2, strict.stdout + strict.stderr)
            self.assertIn("OPEN", strict.stderr)

    def test_sdk_headless_without_qt_or_jeanne_fixture_dependency(self):
        script = """
import sys
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("tkinter", "PySide6", "PyQt5", "PyQt6"):
            raise AssertionError("UI dependency: " + fullname)
sys.meta_path.insert(0, Guard())
from drawtemp.quality.r24_platform import second_game_software_report
from drawtemp.export.templates import create_template
from tempfile import TemporaryDirectory
from pathlib import Path
with TemporaryDirectory() as root:
    folder = create_template("asterion", Path(root) / "new-game")
    assert (folder / "game.game.json").is_file()
assert second_game_software_report(seeds=(17,))["software_passed"]
"""
        process = subprocess.run([sys.executable, "-c", script],
                                 cwd=Path(__file__).resolve().parents[1],
                                 capture_output=True, text=True, timeout=90)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 optional")
class QtSecondGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["r24-second-game"])

    def test_creator_project_opens_in_same_studio_and_workspace(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as folder:
            root = Path(folder)
            target = create_template("asterion", root / "sample")
            session = AuthoringSession.open(target / "game.json")
            win = StudioWindow(
                session, content_path=target / "game.json",
                settings=QSettings(str(root / "studio.ini"), QSettings.IniFormat))
            try:
                win.show()
                self.assertIn("Asterion", win.windowTitle())
                self.assertTrue(any(row.resource_id == "signal_depot"
                                    for row in win._resource_by_key.values()))
                win.navigate("maps")
                self.assertIn("maps", win.pages)
            finally:
                win.hide()
                win.deleteLater()


if __name__ == "__main__":
    unittest.main()

"""R24.E controlled story hooks: permissions, deterministic effects and replay."""
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
from drawtemp.sdk import (
    AuthoringError, AuthoringSession, Simulation, certify_trace,
    SDK_FEATURES, install_script, preview_script, read_script_manifest,
    validate_script_manifest, StudioScriptError, verify_compiled_scripts,
)
from drawtemp.sdk.replay import ReplayCommand, verify_recording, verify_sequence
from drawtemp.quality.r24_platform import source_paths
from sporebound.game_session import gameplay_project_digest


SAMPLE = Path(__file__).resolve().parents[1] / "examples/scripts/asterion-scan.json"
TRACE = (
    ReplayCommand("choose_story_option", ("launch",)),
    ReplayCommand("start_mission", ("signal_depot",)),
    ReplayCommand("execute", ({"kind": "end", "facing": [0, 1]},)),
)


def script():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def source():
    content_path, project_path = source_paths()
    content = Content.from_dict(json.loads(content_path.read_text(encoding="utf-8")))
    project = GameProject.from_dict(json.loads(project_path.read_text(encoding="utf-8")), content)
    return content, project


def editor():
    return AuthoringSession.new(*source())


class ManifestTests(unittest.TestCase):
    def test_contract_is_copy_and_capability_is_explicit(self):
        document = script()
        self.assertIn("controlled-scripting.v1", SDK_FEATURES)
        self.assertEqual(validate_script_manifest(document), document)
        detached = validate_script_manifest(document)
        detached["hooks"][0]["effects"][0]["value"] = False
        self.assertEqual(script()["hooks"][0]["effects"][0]["value"], True)
        self.assertEqual(read_script_manifest(SAMPLE), document)

    def test_forbidden_code_hooks_extra_fields_and_wrong_permissions(self):
        source_doc = script()
        mutations = [
            ({"schema_version": 2}, "unsupported_schema"),
            ({"schema_version": True}, "unsupported_schema"),
            ({"sdk_api": [2, 0]}, "incompatible_sdk"),
            ({"sdk_api": [1, 1]}, "incompatible_sdk"),
            ({"namespace": "../escape"}, "invalid_script"),
            ({"permissions": ["story.flags.write"]}, "invalid_permission"),
            ({"permissions": ["story.flags.write", "filesystem.write"]}, "invalid_permission"),
            ({"hooks": [{**source_doc["hooks"][0], "trigger": "simulation.tick"}]},
             "unsupported_hook"),
            ({"hooks": [{**source_doc["hooks"][0],
                         "effects": [{"kind": "python", "source": "import os"}]}]},
             "unsupported_effect"),
            ({"hooks": [source_doc["hooks"][0], source_doc["hooks"][0]]},
             "duplicate_hook"),
        ]
        for changes, code in mutations:
            with self.subTest(changes=changes):
                with self.assertRaises(StudioScriptError) as caught:
                    validate_script_manifest({**deepcopy(source_doc), **changes})
                self.assertEqual(caught.exception.code, code)
        hook = deepcopy(source_doc)
        hook["hooks"][0]["callback"] = "os.system"
        with self.assertRaises(StudioScriptError):
            validate_script_manifest(hook)
        bad = deepcopy(source_doc)
        bad["hooks"][0]["effects"][0]["value"] = object()
        with self.assertRaises(StudioScriptError):
            validate_script_manifest(bad)
        big = deepcopy(source_doc)
        big["hooks"][0]["effects"] = [{"kind": "set_flag", "flag": "x",
                                     "value": "a" * 65000}]
        with self.assertRaises(StudioScriptError):
            validate_script_manifest(big)

    def test_file_requires_safe_json_without_duplicate_keys(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            duplicated = root / "double.json"
            duplicated.write_text('{"id":"first","id":"second"}', encoding="utf-8")
            with self.assertRaises(StudioScriptError):
                read_script_manifest(duplicated)
            large = root / "large.json"
            large.write_bytes(b"a" * 70000)
            with self.assertRaises(StudioScriptError) as caught:
                read_script_manifest(large)
            self.assertEqual(caught.exception.code, "size_limit")
            link = root / "link.json"
            try:
                link.symlink_to(SAMPLE)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(StudioScriptError) as caught:
                    read_script_manifest(link)
                self.assertEqual(caught.exception.code, "unsafe_path")


class CompiledHookTests(unittest.TestCase):
    def setUp(self):
        self.authoring = editor()
        self.manifest = script()

    def install(self, doc=None, grants=None):
        data = self.manifest if doc is None else doc
        return install_script(self.authoring, data,
                              granted_permissions=data["permissions"] if grants is None else grants,
                              expected_revision=self.authoring.revision)

    def test_explicit_permission_denied_no_mutation_and_stale_refusal(self):
        prior = self.authoring.snapshot().to_dict()
        for permission in ((), ["story.flags.write"],
                           ["story.flags.write", "campaign.gold.write", "filesystem.write"]):
            with self.subTest(permission=permission), self.assertRaises(StudioScriptError):
                self.install(grants=permission)
            self.assertEqual(self.authoring.snapshot().to_dict(), prior)
        with self.assertRaises(StudioScriptError) as caught:
            preview_script(self.authoring, self.manifest,
                           granted_permissions=self.manifest["permissions"], expected_revision=3)
        self.assertEqual(caught.exception.code, "stale_revision")
        self.assertEqual(self.authoring.revision, 0)

    def test_atomic_canonical_compilation_undo_redo_save_load(self):
        original = self.authoring.snapshot().to_dict()
        plan = preview_script(
            self.authoring, self.manifest,
            granted_permissions=self.manifest["permissions"], expected_revision=0)
        self.assertEqual(self.authoring.snapshot().to_dict(), original)
        self.authoring.apply(plan)
        self.assertEqual(self.authoring.revision, 1)
        changed = self.authoring.snapshot().to_dict()
        self.assertEqual(original["content"], changed["content"])
        effects = changed["project"]["story"]["scenes"][0]["choices"][0]["effects"]
        self.assertEqual(effects[-2:], self.manifest["hooks"][0]["effects"])
        namespace = self.manifest["namespace"]
        receipt = changed["project"]["extensions"][namespace]
        self.assertEqual(receipt["schema_version"], 1)
        self.assertEqual(receipt["data"]["kind"], "r24e.story-choice-hooks")
        self.assertEqual(len(receipt["data"]["bindings"][0]["sha256"]), 64)
        with self.assertRaises(AuthoringError):
            self.install()
        self.assertEqual(self.authoring.snapshot().to_dict(), changed)
        self.authoring.undo()
        self.assertEqual(self.authoring.snapshot().to_dict(), original)
        self.authoring.redo()
        self.assertEqual(self.authoring.snapshot().to_dict(), changed)
        with TemporaryDirectory() as folder:
            location = Path(folder) / "game.json"
            self.authoring.save_as(location)
            opened = AuthoringSession.open(location)
            self.assertEqual(opened.snapshot().to_dict()["project"], changed["project"])

    def test_invalid_targets_collisions_and_native_validation(self):
        bad = deepcopy(self.manifest)
        bad["hooks"][0]["scene"] = "missing"
        before = self.authoring.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            self.install(doc=bad)
        self.assertEqual(self.authoring.snapshot().to_dict(), before)
        bad = deepcopy(self.manifest)
        bad["hooks"][0]["effects"][0] = {
            "kind": "unlock_mission", "mission": "nonexistent"}
        bad["permissions"] = ["campaign.missions.unlock", "campaign.gold.write"]
        with self.assertRaises(AuthoringError):
            self.install(doc=bad)
        self.assertEqual(self.authoring.snapshot().to_dict(), before)
        self.install()
        competing = deepcopy(self.manifest)
        competing["namespace"] = "org.drawtemp.example.asterion.competing"
        competing["id"] = "competing-scan"
        with self.assertRaises(AuthoringError) as caught:
            self.install(doc=competing)
        self.assertEqual(caught.exception.code, "invalid_edit")

    def test_actual_story_effects_checkpoints_and_save_compatibility(self):
        content, unmodified = source()
        unmodified_digest = gameplay_project_digest(unmodified)
        self.install()
        modified = GameProject.from_dict(
            self.authoring.snapshot().to_dict()["project"], content)
        self.assertNotEqual(gameplay_project_digest(modified), unmodified_digest)
        sim = Simulation.new(content, modified, "main", seed=17)
        self.assertEqual(sim.snapshot().scene["id"], "briefing")
        self.assertNotIn("signal_scan", sim.snapshot().progress["story_flags"])
        sim.choose_story_option("launch")
        self.assertEqual(sim.snapshot().progress["story_flags"]["signal_scan"], True)
        self.assertEqual(sim.snapshot().progress["gold"], 15)
        recorded = sim.recording()
        self.assertEqual(verify_recording(recorded, content, modified).recording(), recorded)
        with self.assertRaises(Exception):
            verify_recording(recorded, content, unmodified)
        with TemporaryDirectory() as folder:
            location = Path(folder) / "save.json"
            sim.save(location)
            resumed = Simulation.load(location, content, modified)
            self.assertEqual(resumed.recording(), recorded)
        for seed in (1, 17, 221):
            with self.subTest(seed=seed):
                report = certify_trace(content, modified, "main", TRACE, seed=seed)
                replay = verify_sequence(content, modified, "main", TRACE, seed=seed)
                self.assertTrue(report.verified)
                self.assertTrue(replay.verified)
                self.assertEqual(len(report.steps), 4)
                self.assertEqual(report.steps[-1].mode, "battle")
                self.assertIsNotNone(report.steps[-1].rng_sha256)
                self.assertIsNotNone(report.steps[-1].ct_sha256)


    def test_compilation_integrity_blocks_export_if_effects_are_changed(self):
        from drawtemp.export.r15 import preflight
        self.install()
        project = self.authoring.snapshot().to_dict()["project"]
        self.assertEqual(verify_compiled_scripts(project), [])
        with TemporaryDirectory() as folder:
            target = Path(folder) / "game.json"
            self.authoring.save_as(target)
            self.assertTrue(preflight(target)["passed"])
            path = target.with_name("game.game.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            data["story"]["scenes"][0]["choices"][0]["effects"][-1]["amount"] = 99
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertTrue(verify_compiled_scripts(data))
            report = preflight(target)
            self.assertFalse(report["passed"])
            self.assertTrue(any("Compiled effects differ" in x
                                for x in report["errors"]))

    def test_headless_no_third_party_import(self):
        program = """
import sys, json
class Block:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("PySide6", "tkinter", "PyQt5", "PyQt6"):
            raise AssertionError("UI import: " + name)
sys.meta_path.insert(0, Block())
from drawtemp.sdk import AuthoringSession, install_script
from drawtemp.quality.r24_platform import _content_project
from pathlib import Path
content, project = _content_project()
editor = AuthoringSession.new(content, project)
manifest = json.loads(Path("examples/scripts/asterion-scan.json").read_text())
install_script(editor, manifest, granted_permissions=manifest["permissions"])
assert "org.drawtemp.example.asterion.hooks" in editor.snapshot().project["extensions"]
"""
        result = subprocess.run([sys.executable, "-c", program],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "Qt 6 is optional")
class QtHookImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["r24e-qt"])

    def test_studio_import_uses_the_live_authoring_session(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        content, project = source()
        with TemporaryDirectory() as folder:
            win = StudioWindow(AuthoringSession.new(content, project),
                               settings=QSettings(str(Path(folder) / "studio.ini"),
                                                  QSettings.IniFormat))
            try:
                win.show()
                self.assertIsNotNone(win.session)
                before = win.session.snapshot().to_dict()
                win.apply_controlled_hooks(SAMPLE, grants=script()["permissions"])
                self.assertEqual(win.session.revision, 1)
                self.assertIn(script()["namespace"], win.session.snapshot().project["extensions"])
                win.undo()
                after = win.session.snapshot().to_dict()
                self.assertEqual(after["content"], before["content"])
                self.assertEqual(after["project"], before["project"])
                self.assertEqual(win.session.revision, 2)
            finally:
                win.hide()
                win.deleteLater()


if __name__ == "__main__":
    unittest.main()

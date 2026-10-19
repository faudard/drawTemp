"""R24.B controlled declarative Studio plugins: permissions, validation and Qt."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.plugins import (
    StudioPluginError, StudioPluginRegistry, read_studio_manifest,
    validate_studio_manifest,
)
from drawtemp.export.extensions import validate_extension_manifest

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/plugins/quest-helper.json"


def manifest():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def editor():
    return AuthoringSession.new(*reference_project())


class ManifestContractTests(unittest.TestCase):
    def test_valid_and_old_r15_stays_compatible(self):
        data = manifest()
        value = validate_studio_manifest(data)
        self.assertEqual(value, data)
        value["contributions"]["templates"][0]["data"]["chapter"] = 100
        self.assertNotEqual(value, data)
        legacy = {"api_version": 1, "id": "old-helper", "name": "Old",
                  "capabilities": ["asset-catalog"]}
        self.assertEqual(validate_extension_manifest(legacy), legacy)
        with self.assertRaises(StudioPluginError):
            validate_studio_manifest(legacy)

    def test_invalid_manifest_version_permission_and_script_fields(self):
        initial = manifest()
        bad = [
            ({"sdk_api": [2, 0]}, "incompatible_sdk"),
            ({"sdk_api": [1, 1]}, "incompatible_sdk"),
            ({"api_version": True}, "unsupported_api"),
            ({"namespace": "../invalid"}, "invalid_manifest"),
            ({"permissions": ["project.read"]}, "invalid_permission"),
            ({"permissions": ["project.read", "filesystem.write"]}, "invalid_manifest"),
            ({"capabilities": ["python-exec"]}, "invalid_manifest"),
            ({"required_sdk_features": []}, "invalid_manifest"),
            ({"contributions": {"panels": [], "templates": []}}, "invalid_manifest"),
        ]
        for changes, code in bad:
            with self.subTest(changes=changes), self.assertRaises(StudioPluginError) as caught:
                validate_studio_manifest({**deepcopy(initial), **changes})
            self.assertEqual(caught.exception.code, code)
        script = deepcopy(initial)
        script["contributions"]["templates"][0]["entrypoint"] = "os.system"
        with self.assertRaises(StudioPluginError):
            validate_studio_manifest(script)
        bad_field = deepcopy(initial)
        bad_field["contributions"]["panels"][0]["fields"] = ["project.secret"]
        with self.assertRaises(StudioPluginError):
            validate_studio_manifest(bad_field)
        duplicate = deepcopy(initial)
        duplicate["contributions"]["panels"].append(deepcopy(duplicate["contributions"]["panels"][0]))
        with self.assertRaises(StudioPluginError) as caught:
            validate_studio_manifest(duplicate)
        self.assertEqual(caught.exception.code, "duplicate_contribution")

    def test_file_guard_and_json_duplicates(self):
        with TemporaryDirectory() as root:
            folder = Path(root)
            dupe = folder / "dupe.json"
            dupe.write_text('{"api_version":2,"api_version":2}', encoding="utf-8")
            with self.assertRaises(StudioPluginError):
                read_studio_manifest(dupe)
            huge = folder / "huge.json"
            huge.write_bytes(b"A" * 66000)
            with self.assertRaises(StudioPluginError) as error:
                read_studio_manifest(huge)
            self.assertEqual(error.exception.code, "size_limit")
            link = folder / "link.json"
            try:
                link.symlink_to(EXAMPLE)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(StudioPluginError) as error:
                    read_studio_manifest(link)
                self.assertEqual(error.exception.code, "unsafe_path")


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.data = manifest()
        self.registry = StudioPluginRegistry()
        self.registry.install(self.data)
        self.editor = editor()

    def enable(self):
        return self.registry.enable("quest-helper", grants=self.data["permissions"])

    def test_permissions_revocation_quarantine_and_collisions(self):
        self.assertFalse(self.registry.status("quest-helper")["enabled"])
        with self.assertRaises(StudioPluginError):
            self.registry.panel_state("quest-helper", "overview", self.editor.snapshot())
        for denied in ([], ["project.read"], ["project.read", "project.extensions.write",
                                               "filesystem.write"]):
            with self.subTest(denied=denied), self.assertRaises(StudioPluginError):
                self.registry.enable("quest-helper", grants=denied)
        self.enable()
        self.registry.disable("quest-helper")
        with self.assertRaises(StudioPluginError):
            self.registry.apply_template("quest-helper", "first-quest", self.editor)
        self.enable()
        self.registry.quarantine("quest-helper", ValueError("isolated failure"))
        state = self.registry.status("quest-helper")
        self.assertTrue(state["quarantined"])
        self.assertFalse(state["enabled"])
        self.assertEqual(state["grants"], [])
        with self.assertRaises(StudioPluginError):
            self.enable()
        with self.assertRaises(StudioPluginError) as caught:
            self.registry.install(self.data)
        self.assertEqual(caught.exception.code, "duplicate_plugin")
        another = deepcopy(self.data)
        another["id"] = "another-helper"
        with self.assertRaises(StudioPluginError) as caught:
            self.registry.install(another)
        self.assertEqual(caught.exception.code, "namespace_collision")

    def test_panels_read_only_and_follow_project_state(self):
        self.enable()
        state = self.registry.panel_state("quest-helper", "overview", self.editor.snapshot())
        self.assertEqual(state["fields"][0][0], "project.title")
        self.assertEqual(state["fields"][0][1], self.editor.snapshot().project["title"])
        self.assertEqual(dict(state["fields"])["project.campaign_count"], 1)
        plan = self.editor.preview_project(lambda p: {**p, "title": "New title"})
        self.editor.apply(plan)
        state = self.registry.panel_state("quest-helper", "overview", self.editor.snapshot())
        self.assertEqual(dict(state["fields"])["project.title"], "New title")

    def test_template_undo_redo_and_stale_refusal(self):
        self.enable()
        initial = self.editor.snapshot().to_dict()
        transition = self.registry.apply_template(
            "quest-helper", "first-quest", self.editor, expected_revision=0)
        self.assertEqual(transition.snapshot.revision, 1)
        modified = self.editor.snapshot().to_dict()
        self.assertEqual(modified["content"], initial["content"])
        self.assertEqual(modified["project"]["extensions"]["org.example.quest"]
                         ["data"]["chapter"], 1)
        with self.assertRaises(AuthoringError):
            self.registry.apply_template("quest-helper", "first-quest", self.editor)
        self.assertEqual(modified, self.editor.snapshot().to_dict())
        self.editor.undo()
        self.assertEqual(self.editor.snapshot().to_dict()["project"], initial["project"])
        self.editor.redo()
        self.assertEqual(self.editor.snapshot().to_dict()["project"], modified["project"])
        with self.assertRaises(StudioPluginError) as caught:
            self.registry.apply_template("quest-helper", "first-quest", self.editor,
                                         expected_revision=0)
        self.assertEqual(caught.exception.code, "stale_revision")

    def test_bad_references_leave_editor_intact_and_other_plugin_works(self):
        self.enable()
        other = deepcopy(self.data)
        other["id"] = "broken-helper"
        other["namespace"] = "org.example.broken"
        other["contributions"]["templates"][0]["references"] = [
            {"kind": "mission", "id": "missing"}]
        self.registry.install(other)
        self.registry.enable("broken-helper", grants=other["permissions"])
        initial = self.editor.snapshot().to_dict()
        with self.assertRaises(AuthoringError) as caught:
            self.registry.apply_template("broken-helper", "first-quest", self.editor)
        self.assertEqual(caught.exception.code, "invalid_edit")
        self.assertEqual(initial, self.editor.snapshot().to_dict())
        self.registry.apply_template("quest-helper", "first-quest", self.editor)
        self.assertTrue(self.registry.status("broken-helper")["enabled"])

    def test_headless_no_qt_plugin_exec(self):
        program = """
import sys, json
from pathlib import Path
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("tkinter", "PySide6", "PyQt5", "PyQt6"):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Guard())
from drawtemp.studio.plugins import StudioPluginRegistry
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.authoring import AuthoringSession
m = json.loads(Path("examples/plugins/quest-helper.json").read_text())
r = StudioPluginRegistry()
r.install(m)
r.enable("quest-helper", grants=m["permissions"])
s = AuthoringSession.new(*reference_project())
r.apply_template("quest-helper", "first-quest", s)
assert "org.example.quest" in s.snapshot().to_dict()["project"]["extensions"]
"""
        subprocess.run([sys.executable, "-c", program],
                       cwd=Path(__file__).resolve().parents[1],
                       check=True, capture_output=True, text=True)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "Qt is optional")
class QtPluginDockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["r24-b"])

    def test_native_panel_template_click_and_disable(self):
        from PySide6.QtCore import QSettings, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QPushButton
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as root:
            win = StudioWindow(editor(), settings=QSettings(
                str(Path(root) / "studio.ini"), QSettings.IniFormat))
            win.show()
            try:
                win.install_plugin_manifest(EXAMPLE, grants=manifest()["permissions"])
                self.assertIn("quest-helper", win._plugin_docks)
                self.assertTrue(win.plugins.status("quest-helper")["enabled"])
                self.assertIn(("quest-helper", "overview", "project.title"),
                              win._plugin_fields)
                button = next(item for item in win._plugin_docks["quest-helper"]
                              .findChildren(QPushButton)
                              if item.accessibleName() == "Plugin quest-helper first-quest")
                QTest.mouseClick(button, Qt.LeftButton)
                self.assertEqual(win.session.revision, 1)
                self.assertIn("org.example.quest",
                              win.session.snapshot().to_dict()["project"]["extensions"])
                win.undo()
                self.assertNotIn("extensions", win.session.snapshot().to_dict()["project"])
                win.plugins.disable("quest-helper")
                win._unmount_plugin("quest-helper")
                self.assertNotIn("quest-helper", win._plugin_docks)
                self.assertEqual(win.plugins.status("quest-helper")["grants"], [])
            finally:
                win.hide()
                win.deleteLater()


if __name__ == "__main__":
    unittest.main()

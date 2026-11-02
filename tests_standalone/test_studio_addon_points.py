"""PR 2: safe Studio extension points and Qt integration smoke tests."""
import copy
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.addons import AddonManager
from drawtemp.studio.addon_points import (
    StudioAddonPointError, project_field_values,
    studio_contributions, validate_studio_contribution,
)
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project

ROOT = Path(__file__).resolve().parents[1]
BRUSH = ROOT / "examples/addons/terrain-brush.json"
INSPECTOR = ROOT / "examples/addons/studio-inspector-demo.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def manager_for(path):
    manager = AddonManager()
    manifest = read(path)
    manager.register(manifest)
    manager.enable(manifest["id"], grants=manifest["permissions"])
    return manager


class StudioPointsTests(unittest.TestCase):
    def test_inert_tool_preset_and_allowlisted_dock_menu(self):
        for path, expected in (
            (BRUSH, {"studio.tool"}),
            (INSPECTOR, {"studio.menu", "studio.dock"}),
        ):
            with self.subTest(path=path):
                manager = manager_for(path)
                points = studio_contributions(manager)
                self.assertEqual({p["point"] for p in points}, expected)
                points[0]["config"].clear()
                self.assertTrue(studio_contributions(manager)[0]["config"])

    def test_disabled_and_legacy_addons_cannot_contribute(self):
        manager = AddonManager()
        manager.register(read(INSPECTOR))
        self.assertEqual(studio_contributions(manager), ())
        manager.register({"api_version": 1, "id": "legacy-test",
                          "name": "Legacy", "capabilities": ["asset-catalog"]})
        self.assertEqual(studio_contributions(manager), ())

    def test_only_host_owned_commands_and_canonical_fields(self):
        template = read(INSPECTOR)
        for contribution in template["contributions"]:
            validate_studio_contribution(contribution)
        menu = copy.deepcopy(template["contributions"][1])
        menu["config"]["command"] = "subprocess.run"
        with self.assertRaises(StudioAddonPointError):
            validate_studio_contribution(menu)
        dock = copy.deepcopy(template["contributions"][0])
        dock["config"]["fields"] = ["project.secrets"]
        with self.assertRaises(StudioAddonPointError):
            validate_studio_contribution(dock)
        dock["config"]["fields"] = ["project.title", "project.title"]
        with self.assertRaises(StudioAddonPointError):
            validate_studio_contribution(dock)

    def test_invalid_brush_shape_radius_material_not_accepted(self):
        source = read(BRUSH)["contributions"][0]
        for key, value in (("material", "../../private"),
                           ("radius", True), ("radius", 100),
                           ("shape", "unknown")):
            with self.subTest(key=key, value=value):
                bad = copy.deepcopy(source)
                bad["config"][key] = value
                with self.assertRaises(StudioAddonPointError):
                    validate_studio_contribution(bad)
        bad = copy.deepcopy(source)
        bad["config"]["algorithm"] = "unknown"
        with self.assertRaises(StudioAddonPointError):
            validate_studio_contribution(bad)

    def test_readonly_fields_follow_authoring_snapshot(self):
        editor = AuthoringSession.new(*reference_project())
        before = project_field_values(editor.snapshot())
        plan = editor.preview_project(lambda p: {**p, "title": "Changed"})
        editor.apply(plan)
        after = project_field_values(editor.snapshot())
        self.assertEqual(after["project.title"], "Changed")
        self.assertEqual(after["content.mission_count"],
                         before["content.mission_count"])
        editor.undo()
        self.assertEqual(project_field_values(editor.snapshot()), before)

    def test_locale_catalog_has_labels_in_en_and_fr(self):
        from drawtemp.localization.ui import ui_text
        self.assertEqual(ui_text("tool.addons_manage", "en"), "Add-on Manager…")
        self.assertEqual(ui_text("tool.addons_manage", "fr"),
                         "Gestionnaire d’extensions…")


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class QtStudioAddonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["addon-extension-points"])

    def test_enable_dock_menu_disable_project_switch(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as directory:
            win = StudioWindow(settings=QSettings(
                str(Path(directory) / "studio.ini"), QSettings.IniFormat))
            win.show()
            try:
                status = win.install_addon_manifest(INSPECTOR)
                self.assertFalse(status["enabled"])
                self.assertEqual(len(win._addon_docks), 0)
                win.enable_addon(status["id"], ["project.read"])
                self.assertIn(("studio-inspector-demo", "overview"), win._addon_docks)
                self.assertEqual(len(win._addon_actions), 1)
                self.assertIn(("studio-inspector-demo", "overview"),
                              [key for (key, _field) in win._addon_fields])
                self.assertIn("project.title", next(iter(
                    v.text() for (key, field), v in win._addon_fields.items()
                    if field == "project.title")))
                self.assertEqual(win._addon_actions[0].text(), "Open Event Editor")
                self.assertEqual(win.addons.status(status["id"])["code_executed"], False)
                self.assertEqual(win.session.revision, 0)
                win.disable_addon(status["id"])
                self.assertEqual(win._addon_docks, {})
                self.assertEqual(win._addon_actions, [])
                win.enable_addon(status["id"], ["project.read"])
                win._install_document(AuthoringSession.new(*reference_project()), None)
                self.assertEqual(win.addons.statuses(), ())
                self.assertEqual(win._addon_fields, {})
            finally:
                win.hide()
                win.deleteLater()

    def test_map_brush_reuses_native_map_editor(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as directory:
            win = StudioWindow(settings=QSettings(
                str(Path(directory) / "studio.ini"), QSettings.IniFormat))
            win.show()
            try:
                status = win.install_addon_manifest(BRUSH)
                win.enable_addon(status["id"], status["required_permissions"])
                win.navigate("maps")
                editor = win._models["maps"]
                self.assertEqual(editor.addon_brushes.count(), 2)
                editor.addon_brushes.setCurrentIndex(1)
                self.assertEqual(editor.tools.currentText(), "Pinceau")
                self.assertEqual(editor.material.currentText(), "grass")
                self.assertEqual(editor.brush_radius.value(), 1)
                self.assertEqual(editor.brush_shape.currentData(), "diamond")
                self.assertEqual(win.session.revision, 0)
                win.disable_addon(status["id"])
                self.assertEqual(editor.addon_brushes.count(), 1)
            finally:
                win.hide()
                win.deleteLater()


if __name__ == "__main__":
    unittest.main()

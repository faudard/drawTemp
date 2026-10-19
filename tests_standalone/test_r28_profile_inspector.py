"""R28.B profile inspector gates: canonical R25 data, R1 transactions and Qt UI."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.profile_authoring import (
    ProfileEditorError, apply_profile_edit, inspect_profile,
    preview_profile_edit, profile_targets,
)
from sporebound.game_modes import PRESETS
from sporebound.game_project import GameProject


def editor():
    return AuthoringSession.new(*reference_project())


class ProfileAuthoringTests(unittest.TestCase):
    def test_reading_legacy_modes_is_non_destructive(self):
        s = editor()
        before = s.snapshot().to_dict()
        data = inspect_profile(s.snapshot())
        self.assertEqual(data["source"], "legacy")
        self.assertEqual(data["effective"], PRESETS["srpg"])
        self.assertNotIn("game_modes", before["project"])
        self.assertIn(MISSION, dict(profile_targets(s.snapshot())))
        plan = preview_profile_edit(s, None, None)
        self.assertFalse(plan.report["changed"])
        self.assertEqual(s.revision, 0)
        self.assertEqual(s.snapshot().to_dict(), before)
        with self.assertRaises(AuthoringError):
            apply_profile_edit(s, plan)
        self.assertNotIn("game_modes", s.snapshot().to_dict()["project"])

    def test_global_action_profile_preserves_tactical_scenes_in_one_undo(self):
        s = editor()
        old = s.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            preview_profile_edit(s, None, {"preset": "action"})
        self.assertEqual(s.snapshot().to_dict(), old)
        planned = preview_profile_edit(s, None, {"preset": "action"},
                                       protect_tactical=True)
        self.assertTrue(planned.report["changed"])
        self.assertIn(MISSION, planned.report["pinned_tactical_missions"])
        self.assertEqual(s.revision, 0)
        result = apply_profile_edit(s, planned)
        self.assertEqual(result.snapshot.revision, 1)
        modes = s.snapshot().to_dict()["project"]["game_modes"]
        self.assertEqual(modes["default"], {"preset": "action"})
        self.assertEqual(modes["scenes"][MISSION], {"preset": "srpg"})
        self.assertEqual(inspect_profile(s.snapshot())["effective"],
                         PRESETS["action"])
        self.assertEqual(inspect_profile(s.snapshot(), MISSION)["effective"],
                         PRESETS["srpg"])
        self.assertEqual(s.snapshot().to_dict()["content"], old["content"])
        s.undo()
        self.assertEqual(s.snapshot().to_dict()["project"], old["project"])
        s.redo()
        self.assertEqual(s.snapshot().to_dict()["project"]["game_modes"], modes)

    def test_scene_override_and_reset_use_one_canonical_manifest(self):
        s = editor()
        initial = s.snapshot().to_dict()
        planned = preview_profile_edit(s, "arrival", {"preset": "narrative"})
        self.assertTrue(planned.report["changed"])
        apply_profile_edit(s, planned)
        self.assertEqual(inspect_profile(s.snapshot(), "arrival")["source"], "scene")
        self.assertEqual(inspect_profile(s.snapshot(), "arrival")["effective"]["combat"],
                         "NONE")
        apply_profile_edit(s, preview_profile_edit(s, "arrival", None))
        self.assertEqual(s.snapshot().to_dict()["project"], initial["project"])
        self.assertEqual(inspect_profile(s.snapshot(), "arrival")["source"],
                         "inherited")
        s.undo()
        self.assertEqual(inspect_profile(s.snapshot(), "arrival")["source"], "scene")

    def test_scene_inheritance_with_non_ct_default_after_pins(self):
        s = editor()
        apply_profile_edit(s, preview_profile_edit(
            s, None, {"preset": "hybrid"}, protect_tactical=True))
        preview = preview_profile_edit(s, "arrival", {"preset": "narrative"})
        apply_profile_edit(s, preview)
        self.assertEqual(inspect_profile(s.snapshot(), "arrival")["effective"],
                         PRESETS["narrative"])
        apply_profile_edit(s, preview_profile_edit(s, "arrival", None))
        info = inspect_profile(s.snapshot(), "arrival")
        self.assertEqual(info["source"], "inherited")
        self.assertEqual(info["effective"], PRESETS["hybrid"])

    def test_reject_invalid_mission_mode_missing_scene_and_bad_custom(self):
        s = editor()
        before = s.snapshot().to_dict()
        for scene, selection in (
            (MISSION, {"preset": "action"}),
            ("missing", {"preset": "narrative"}),
            (None, {"preset": "unknown"}),
            (None, {"profile": {"movement": "FREE_REALTIME"}}),
            (None, {"preset": "action", "unknown": True}),
        ):
            with self.subTest(scene=scene, selection=selection):
                with self.assertRaises((ProfileEditorError, AuthoringError)):
                    preview_profile_edit(s, scene, selection, protect_tactical=False)
        self.assertEqual(s.snapshot().to_dict(), before)

    def test_custom_capabilities_validated_by_r25_not_ui_fallback(self):
        s = editor()
        custom = deepcopy(PRESETS["srpg"])
        custom["camera"] = "TOP_DOWN"
        apply_profile_edit(s, preview_profile_edit(
            s, MISSION, {"profile": custom}))
        self.assertEqual(inspect_profile(s.snapshot(), MISSION)["selection"],
                         {"profile": custom})
        invalid = deepcopy(custom)
        invalid["movement"] = "FREE_REALTIME"
        with self.assertRaises(AuthoringError):
            preview_profile_edit(s, MISSION, {"profile": invalid})

    def test_stale_foreign_and_revision_mismatch_are_rejected(self):
        first, other = editor(), editor()
        prepared = preview_profile_edit(first, "arrival", {"preset": "narrative"})
        with self.assertRaises(AuthoringError):
            apply_profile_edit(other, prepared)
        next_edit = preview_profile_edit(first, MISSION, None)
        # An unchanged edit still produces a plan, but is never committed.
        with self.assertRaises(AuthoringError):
            apply_profile_edit(first, next_edit)
        first_change = preview_profile_edit(first, None, {"preset": "srpg"})
        with self.assertRaises(AuthoringError):
            apply_profile_edit(first, first_change)
        apply_profile_edit(first, prepared)
        before = first.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            apply_profile_edit(first, prepared)
        with self.assertRaises(ProfileEditorError):
            preview_profile_edit(first, "arrival", None, expected_revision=0)
        self.assertEqual(first.snapshot().to_dict(), before)

    def test_save_reopen_uses_gameproject_and_preserves_project_version(self):
        s = editor()
        apply_profile_edit(s, preview_profile_edit(
            s, None, {"preset": "action"}, protect_tactical=True))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "game.json"
            s.save_as(path)
            reopened = AuthoringSession.open(path)
            self.assertEqual(reopened.snapshot().to_dict()["project"]["version"], 1)
            self.assertEqual(
                reopened.snapshot().to_dict()["project"]["game_modes"],
                s.snapshot().to_dict()["project"]["game_modes"])
            assert path.with_name("game.game.json").is_file()
            source, _ = reference_project()
            migrated = GameProject.from_dict(
                json.loads(path.with_name("game.game.json").read_text(encoding="utf-8")),
                source)
            self.assertEqual(migrated.game_modes["default"]["preset"], "action")


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 is not installed")
class ProfileQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_ui_previews_and_applies_then_undo_without_shadow_registry(self):
        from drawtemp.studio.profile_editor_qt import ProfileEditorWidget
        s = editor()
        view = ProfileEditorWidget(s)
        self.assertEqual(view.scope.count(), len(profile_targets(s.snapshot())))
        self.assertFalse(view.apply_button.isEnabled())
        self.assertEqual(s.revision, 0)
        view.selection.setCurrentIndex(view.selection.findData("action"))
        self.assertTrue(view.apply_button.isEnabled())
        self.assertIn("pinned_tactical_missions", view.diagnostics.toPlainText())
        self.assertEqual(s.revision, 0)
        view.apply_changes()
        self.assertEqual(s.revision, 1)
        self.assertEqual(inspect_profile(s.snapshot(), MISSION)["effective"],
                         PRESETS["srpg"])
        s.undo()
        view.refresh()
        self.assertEqual(inspect_profile(s.snapshot())["source"], "legacy")
        view.close()

    def test_qt_shell_profiles_workspace_shares_authoring_session(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as directory:
            s = editor()
            prefs = QSettings(str(Path(directory) / "studio.ini"), QSettings.IniFormat)
            window = StudioWindow(s, settings=prefs)
            window.navigate("profiles")
            inspector = window._models["profiles"]
            self.assertIs(inspector.session, s)
            self.assertEqual(window.workspace_tabs.currentWidget(), inspector)
            self.assertIn("go_profiles", window.commands)
            inspector.selection.setCurrentIndex(
                inspector.selection.findData("action"))
            inspector.apply_changes()
            self.assertEqual(window.session.revision, 1)
            window.undo()
            self.assertEqual(inspect_profile(s.snapshot())["source"], "legacy")
            window.close()


if __name__ == "__main__":
    unittest.main()

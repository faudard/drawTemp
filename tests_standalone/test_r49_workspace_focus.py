"""R49.B1: semantic focus persistence with Qt Studio integration tests."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.studio.r18_navigation import WORKSPACES
from drawtemp.studio.r49_workspaces import (
    FOCUS_REGIONS, WorkspaceFocusMemory, focus_settings_key,
)


class FocusContractsTests(unittest.TestCase):
    def test_stored_preferences_are_bounded_to_known_regions(self):
        memory = WorkspaceFocusMemory({
            "project": "search",
            "maps": "/home/private/secret.json",
            "events": "workspace",
            "unrecognized": "resources",
        })
        self.assertEqual(memory.preferred("project"), "search")
        self.assertEqual(memory.preferred("events"), "workspace")
        self.assertIsNone(memory.preferred("maps"))
        self.assertNotIn("unrecognized", memory.snapshot())
        self.assertFalse(memory.remember("project", "search"))
        self.assertTrue(memory.remember("project", "inspector"))
        self.assertEqual(memory.preferred("project"), "inspector")

    def test_unknown_workspace_and_region_fail_closed(self):
        memory = WorkspaceFocusMemory()
        for workspace in ("", "../../custom", "fake", None):
            with self.subTest(workspace=workspace), self.assertRaises(ValueError):
                memory.preferred(workspace)
            with self.subTest(workspace=workspace), self.assertRaises(ValueError):
                focus_settings_key(workspace)
        with self.assertRaises(ValueError):
            memory.remember("project", "custom_widget:123")
        with self.assertRaises(TypeError):
            WorkspaceFocusMemory("project=search")
        with self.assertRaises(TypeError):
            memory.resolve("project", "search")
        with self.assertRaises(ValueError):
            memory.resolve("project", {"search", "unknown"})

    def test_preference_survives_reinitialization_from_validated_snapshot(self):
        source = WorkspaceFocusMemory()
        for workspace in WORKSPACES:
            source.remember(workspace, "workspace")
        source.remember("maps", "resources")
        saved = source.snapshot()
        cloned = WorkspaceFocusMemory(saved)
        self.assertEqual(cloned.preferred("maps"), "resources")
        self.assertEqual(cloned.preferred("project"), "workspace")
        saved["maps"] = "invalid"
        self.assertEqual(cloned.preferred("maps"), "resources")
        self.assertEqual(set(FOCUS_REGIONS),
                         {"workspace", "search", "resources", "inspector", "diagnostics"})

    def test_missing_region_falls_back_only_to_visible_regions(self):
        memory = WorkspaceFocusMemory({"project": "inspector"})
        self.assertEqual(memory.resolve("project", {"resources", "search"}),
                         "search")
        self.assertEqual(memory.resolve("project", {"workspace", "search"}),
                         "workspace")
        self.assertEqual(memory.resolve("project", {"inspector", "workspace"}),
                         "inspector")
        self.assertIsNone(memory.resolve("project", set()))

    def test_safe_keys_never_contain_user_identifiers(self):
        for identifier in WORKSPACES:
            self.assertEqual(focus_settings_key(identifier), "ux/r49/focus/" + identifier)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 not installed")
class FocusStudioQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_navigation_focus_and_saved_preference_roundtrip(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as temp:
            settings = QSettings(str(Path(temp) / "focus.ini"), QSettings.IniFormat)
            first = StudioWindow(settings=settings)
            first.show()
            self.app.processEvents()
            first.search.setFocus()
            self.app.processEvents()
            self.assertEqual(first._r49_focus.preferred("project"), "search")
            first.navigate("publication")
            self.app.processEvents()
            self.assertEqual(first._active_workspace, "publication")
            self.assertTrue(first.focus_workspace())
            self.app.processEvents()
            self.assertEqual(first._r49_focus.preferred("publication"), "workspace")
            first.navigate("project")
            self.app.processEvents()
            self.assertIs(self.app.focusWidget(), first.search)
            self.assertEqual(settings.value(focus_settings_key("project")), "search")
            self.assertEqual(settings.value(focus_settings_key("publication")),
                             "workspace")
            with patch.object(first, "_confirm_leave", return_value=True):
                first.close()
            first.deleteLater()
            self.app.processEvents()

            settings2 = QSettings(str(Path(temp) / "focus.ini"), QSettings.IniFormat)
            second = StudioWindow(settings=settings2)
            second.show()
            self.app.processEvents()
            self.assertEqual(second._r49_focus.preferred("project"), "search")
            second.navigate("publication")
            self.app.processEvents()
            self.assertEqual(second._r49_focus.preferred("publication"),
                             "workspace")
            self.assertTrue(second.commands["focus_workspace"].isEnabled())
            self.assertEqual(second.commands["focus_workspace"].shortcut().toString(),
                             "Ctrl+3")
            with patch.object(second, "_confirm_leave", return_value=True):
                second.close()
            second.deleteLater()

    def test_corrupt_saved_focus_is_ignored_and_no_nonexistent_page_created(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as temp:
            settings = QSettings(str(Path(temp) / "corrupt.ini"), QSettings.IniFormat)
            settings.setValue(focus_settings_key("maps"), "/tmp/another-game.json")
            window = StudioWindow(settings=settings)
            window.show()
            self.app.processEvents()
            self.assertIsNone(window._r49_focus.preferred("maps"))
            self.assertNotIn("maps", window.pages)
            self.assertFalse(window._r49_restore_focus("maps"))
            self.assertNotIn("maps", window.pages)
            with patch.object(window, "_confirm_leave", return_value=True):
                window.close()
            window.deleteLater()


if __name__ == "__main__":
    unittest.main()

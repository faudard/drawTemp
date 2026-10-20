"""R57.C accessibility preferences, player projections and Qt focus regression."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.player.r57_accessibility import (
    AccessibilityError, AccessibilityPreferences, defaults,
    filtered_cinematic_frame, presentation_animation, validate,
)
from drawtemp.quality.r57_a11y import (
    ContrastError, contrast_ratio, audit_contrast,
)


class R57CAccessibilityTests(unittest.TestCase):
    def test_persistent_independent_from_gameplay_saves_and_v1(self):
        from drawtemp.player.qt_app import build_controller
        with TemporaryDirectory() as folder:
            path = Path(folder)
            controller = build_controller(reference=True, save_dir=path)
            original = controller.state()
            self.assertEqual(original["accessibility"]["language"], "fr")
            self.assertEqual(original["settings"]["display"]["text_scale"], 1.0)
            controller.new_game()
            controller.save(1)
            saved = (path / "slot_1.json").read_bytes()
            revision = controller.state()["revision"]
            controller.set_accessibility("language", "en")
            controller.set_accessibility("subtitle_scale", 1.7)
            controller.set_accessibility("reduce_motion", True)
            controller.set_accessibility("reduce_flashes", True)
            view = controller.state()
            self.assertEqual(view["revision"], revision)
            self.assertEqual((path / "slot_1.json").read_bytes(), saved)
            self.assertFalse((path / "player-preferences.json").exists())
            self.assertTrue((path / "r57-accessibility.json").is_file())
            reopened = build_controller(reference=True, save_dir=path)
            self.assertEqual(reopened.state()["accessibility"], {
                "version": 1, "language": "en", "subtitle_scale": 1.7,
                "reduce_motion": True, "reduce_flashes": True,
            })

    def test_schema_boundaries_are_atomic(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "r57-accessibility.json"
            prefs = AccessibilityPreferences(path, default_language="en")
            self.assertEqual(prefs.view()["language"], "en")
            prefs.update("subtitle_scale", 1.4)
            snapshot = prefs.view()
            disk = path.read_bytes()
            for field, bad in [
                    ("subtitle_scale", "1.2"), ("subtitle_scale", True),
                    ("subtitle_scale", 0.4), ("subtitle_scale", 3.0),
                    ("reduce_motion", 1), ("reduce_flashes", "false"),
                    ("language", "de"), ("language", ""),
                    ("unknown", True), ("version", 2)]:
                with self.subTest(field=field, value=bad):
                    with self.assertRaises(AccessibilityError):
                        prefs.update(field, bad)
                    self.assertEqual(prefs.view(), snapshot)
                    self.assertEqual(path.read_bytes(), disk)
            detached = prefs.view()
            detached["language"] = "bad"
            self.assertEqual(prefs.view(), snapshot)
            with patch.object(prefs, "_persist", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    prefs.update("reduce_motion", True)
            self.assertEqual(prefs.view(), snapshot)
            self.assertEqual(path.read_bytes(), disk)

    def test_invalid_legacy_document_preserved_on_first_save(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "r57-accessibility.json"
            for data in ("not json", json.dumps({"version": 99})):
                path.write_text(data, encoding="utf-8")
                backup = path.with_suffix(".json.invalid")
                backup.unlink(missing_ok=True)
                prefs = AccessibilityPreferences(path)
                self.assertTrue(prefs.warning)
                self.assertEqual(path.read_text(encoding="utf-8"), data)
                prefs.update("language", "en")
                self.assertEqual(backup.read_text(encoding="utf-8"), data)
                self.assertEqual(prefs.view()["language"], "en")
                self.assertFalse(AccessibilityPreferences(path).warning)
            path.write_text("bad again", encoding="utf-8")
            prefs = AccessibilityPreferences(path)
            with self.assertRaises(AccessibilityError):
                prefs.update("subtitle_scale", 1.2)
            self.assertEqual(path.read_text(encoding="utf-8"), "bad again")

    def test_symlink_settings_refused(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "r57-accessibility.json"
            target = Path(folder) / "not-a-settings.json"
            target.write_text("sentinel", encoding="utf-8")
            try:
                path.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation unavailable")
            prefs = AccessibilityPreferences(path)
            self.assertTrue(prefs.warning)
            with self.assertRaises(AccessibilityError):
                prefs.update("language", "en")
            self.assertEqual(target.read_text(encoding="utf-8"), "sentinel")

    def test_filtered_visuals_do_not_mutate_canonical_plan(self):
        frame = {
            "effects": [
                {"kind": "camera_shake", "power": 0.7},
                {"kind": "light", "power": 1},
                {"kind": "rain", "power": 0.5},
            ],
            "fadeOpacity": 0.5, "transitionOpacity": 0.7, "timeMs": 90,
        }
        access = defaults()
        original = json.dumps(frame, sort_keys=True)
        self.assertEqual(filtered_cinematic_frame(frame, access), frame)
        access["reduce_motion"] = True
        access["reduce_flashes"] = True
        projected = filtered_cinematic_frame(frame, access)
        self.assertEqual([x["kind"] for x in projected["effects"]], ["rain"])
        self.assertEqual(projected["fadeOpacity"], 0)
        self.assertEqual(projected["transitionOpacity"], 0)
        self.assertEqual(json.dumps(frame, sort_keys=True), original)
        plan = {"serial": 3, "revision": 8,
                "clips": [{"kind": "move", "actor": "jeanne"}]}
        reduced = presentation_animation(plan, access)
        self.assertEqual(reduced["clips"], [])
        self.assertEqual(reduced["serial"], 3)
        self.assertEqual(len(plan["clips"]), 1)

    def test_contrast_fixed_palette_and_failures(self):
        rows = audit_contrast()
        self.assertTrue(rows)
        self.assertTrue(all(row["pass"] for row in rows))
        self.assertGreaterEqual(contrast_ratio("#ffffff", "#000000"), 20.9)
        self.assertEqual(contrast_ratio("#000000", "#000000"), 1.0)
        self.assertFalse(audit_contrast({"bad": ("#aaaaaa", "#bbbbbb", 4.5)})[0]["pass"])
        for value in ("#12", "#fg0000", "red", "#fff00000"):
            with self.assertRaises(ContrastError):
                contrast_ratio(value, "#000000")

    def test_no_qt_import_in_preferences(self):
        import subprocess
        import sys
        subprocess.run([
            sys.executable, "-c",
            "import sys; from drawtemp.player.r57_accessibility import defaults; "
            "from drawtemp.quality.r57_a11y import audit_contrast; "
            "assert 'PySide6' not in sys.modules"
        ], check=True)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 unavailable")
class R57CQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_bridge_saved_language_visual_changes_without_gameplay_mutation(self):
        from drawtemp.player.qt_app import build_controller, create_bridge
        with TemporaryDirectory() as folder:
            controller = build_controller(reference=True, save_dir=folder)
            bridge = create_bridge(controller, object())
            revision = bridge.view["revision"]
            bridge.selectLanguage("en")
            bridge.setAccessibilityBool("reduce_motion", True)
            bridge.setAccessibilityBool("reduce_flashes", True)
            bridge.setSubtitleScale(1.6)
            self.assertEqual(bridge.view["accessibility"]["language"], "en")
            self.assertEqual(bridge.view["accessibility"]["subtitle_scale"], 1.6)
            self.assertEqual(bridge.view["revision"], revision)
            self.assertEqual(controller.state()["revision"], revision)
            bridge.selectLanguage("unsupported")
            self.assertEqual(bridge.view["accessibility"]["language"], "en")
            reopened = build_controller(reference=True, save_dir=folder)
            self.assertEqual(reopened.state()["accessibility"]["language"], "en")
            bridge.deleteLater()

    def test_translation_studio_plural_forms_are_structured_after_save(self):
        from drawtemp.localization import Catalog, seeded_for_project, sidecar_path
        from PySide6.QtCore import Qt
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        from drawtemp.sdk.simulation import thaw
        from drawtemp.studio.r57_translation_qt import TranslationStudioDialog
        from unittest.mock import patch as mock_patch

        with TemporaryDirectory() as folder:
            source = Path(folder) / "game.json"
            session = AuthoringSession.new(*reference_project())
            session.save_as(source)
            catalog, _ = seeded_for_project(thaw(session.snapshot().project))
            data = catalog.data
            data["entries"]["inventory.items"] = {
                "source": {
                    "one": "{count} objet", "other": "{count} objets"},
                "context": "Inventory subtitle with plural count",
                "max_length": 80, "translations": {},
            }
            Catalog(data).save(sidecar_path(source))
            dialog = TranslationStudioDialog(session, source)
            dialog.show()
            try:
                items = dialog.keys.findItems(
                    "inventory.items", Qt.MatchExactly)
                self.assertEqual(len(items), 1)
                dialog.keys.setCurrentItem(items[0])
                self.assertTrue(dialog.plural_form.isVisible())
                self.assertEqual(dialog.plural_form.currentData(), "one")
                dialog.text.setPlainText("{count} item")
                self.assertEqual(dialog.drafts[("inventory.items", "en")],
                                 {"one": "{count} item", "other": ""})
                dialog.plural_form.setCurrentIndex(1)
                self.assertEqual(dialog.text.toPlainText(), "")
                dialog.text.setPlainText("{count} items")
                dialog.plural_form.setCurrentIndex(0)
                self.assertEqual(dialog.text.toPlainText(), "{count} item")
                with mock_patch(
                        "drawtemp.studio.r57_translation_qt.QMessageBox.warning") as warning:
                    dialog.save()
                    warning.assert_not_called()
                result = Catalog.load(sidecar_path(source))
                translation = result.data["entries"]["inventory.items"]["translations"]["en"]
                self.assertEqual(translation, {
                    "one": "{count} item", "other": "{count} items"})
                self.assertEqual(result.render(
                    "inventory.items", "en", count=1), "1 item")
                self.assertEqual(result.render(
                    "inventory.items", "en", count=3), "3 items")
            finally:
                dialog.close()

    def test_translation_studio_keyboard_search_and_context(self):
        from PySide6.QtCore import QSettings, Qt
        from PySide6.QtTest import QTest
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        from drawtemp.studio.r57_translation_qt import TranslationStudioDialog
        with TemporaryDirectory() as folder:
            root = Path(folder)
            content = root / "game.json"
            session = AuthoringSession.new(*reference_project())
            session.save_as(content)
            dialog = TranslationStudioDialog(session, content)
            dialog.show()
            try:
                dialog.search.setFocus()
                QTest.keyClicks(dialog.search, "story")
                self.assertTrue(dialog.keys.count() >= 1)
                self.assertIn("story", dialog.keys.item(0).text())
                dialog.keys.setFocus()
                QTest.keyClick(dialog.keys, Qt.Key_Down)
                self.assertIsNotNone(dialog.keys.currentItem())
                dialog.text.setFocus()
                QTest.keyClicks(dialog.text, "E")
                self.assertTrue(dialog.text.toPlainText().endswith("E"))
                self.assertTrue(dialog.context.toPlainText())
                # R57 keyboard commands change the focused control only.
                dialog.search_shortcut.activated.emit()
                self.app.processEvents()
                self.assertTrue(dialog.search.hasFocus())
                dialog.list_shortcut.activated.emit()
                self.app.processEvents()
                self.assertTrue(dialog.keys.hasFocus())
                dialog.edit_shortcut.activated.emit()
                self.app.processEvents()
                self.assertTrue(dialog.text.hasFocus())

                # Reject stale authored source while preserving the persisted
                # sidecar even if an editor changes after this dialog opened.
                from types import SimpleNamespace
                from unittest.mock import patch as mocked
                catalog_path = dialog.path
                before = catalog_path.read_bytes() if catalog_path.exists() else None
                dialog.text.setPlainText("Unpublished")
                changed = SimpleNamespace(
                    dirty=False, revision=dialog.source_revision + 1)
                with mocked.object(session, "snapshot", return_value=changed), \
                        mocked("drawtemp.studio.r57_translation_qt.QMessageBox.warning") as warning:
                    dialog.save()
                    warning.assert_called_once()
                after = catalog_path.read_bytes() if catalog_path.exists() else None
                self.assertEqual(before, after)
            finally:
                dialog.close()


if __name__ == "__main__":
    unittest.main()

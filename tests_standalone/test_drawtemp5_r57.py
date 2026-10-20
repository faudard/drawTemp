"""R57: deterministic localization, migration, fallback and UI integration."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.localization import (
    Catalog, LocalizationError, file_revision, localize_view, rebase_project_sources, seeded_for_project, sidecar_path,
)


PROJECT = {
    "title": "Les voix de Jeanne", "subtitle": "Une aventure",
    "options": {"language": "fr"},
    "campaigns": [{"id": "acte_1", "name": "La lisière",
                   "description": "Départ du village", "start_mission": "test"}],
    "story": {"scenes": [
        {"id": "intro", "title": "Une rencontre", "speaker": "Jeanne",
         "text": "Bienvenue !", "choices": [{"id": "go", "label": "Entrer"}]},
    ]},
}


class R57CatalogTests(unittest.TestCase):
    def test_seeded_keys_and_stale_source_fail_closed(self):
        catalog, drift = seeded_for_project(PROJECT)
        self.assertFalse(drift)
        self.assertIn("project.title", catalog.data["entries"])
        self.assertIn("campaign.acte_1.name", catalog.data["entries"])
        self.assertIn("story.intro.text", catalog.data["entries"])
        self.assertIn("story.intro.choice.go.label", catalog.data["entries"])
        self.assertEqual(catalog.render("project.title", "en"), PROJECT["title"])
        translated = catalog.with_translation("project.title", "en", "Joan's voices")
        self.assertEqual(translated.render("project.title", "en"), "Joan's voices")
        self.assertEqual(translated.render("project.title", "en",
                                           source="Changed title"), "Changed title")
        changed = dict(PROJECT, title="Nouveau titre")
        reread, drift = seeded_for_project(changed, translated)
        self.assertIsNotNone(reread)
        self.assertEqual(drift, ("project.title",))

    def test_legacy_optional_subtitle_may_be_empty(self):
        project = dict(PROJECT, subtitle="")
        cat, drift = seeded_for_project(project)
        self.assertEqual(drift, ())
        self.assertNotIn("project.subtitle", cat.data["entries"])
        self.assertIn("project.title", cat.data["entries"])

    def test_explicit_source_rebase_resets_only_changed_translations(self):
        old, _ = seeded_for_project(PROJECT)
        old = old.with_translation("project.title", "en", "Original title")
        old = old.with_translation("story.intro.text", "en", "Welcome!")
        changed = dict(PROJECT, title="Titre révisé")
        unchanged, drift = seeded_for_project(changed, old)
        self.assertEqual(drift, ("project.title",))
        self.assertEqual(unchanged.render("project.title", "en",
                                          source="Titre révisé"), "Titre révisé")
        fixed, fixed_keys = rebase_project_sources(changed, old)
        self.assertEqual(fixed_keys, ("project.title",))
        self.assertEqual(fixed.render("project.title", "en"), "Titre révisé")
        self.assertEqual(fixed.render("story.intro.text", "en"), "Welcome!")

    def test_player_projection_preserves_runtime_and_translates_dialogue(self):
        cat, _ = seeded_for_project(PROJECT)
        cat = cat.with_translation("project.title", "en", "Joan's voices")
        cat = cat.with_translation("story.intro.text", "en", "Welcome!")
        cat = cat.with_translation("story.intro.choice.go.label", "en", "Enter")
        view = {"campaign": "acte_1", "title": PROJECT["title"],
                "subtitle": PROJECT["subtitle"], "scene": {
                    "id": "intro", "text": "Bienvenue !", "speaker": "Jeanne",
                    "title": "Une rencontre"},
                "choices": [{"id": "go", "label": "Entrer"}],
                "revision": 11}
        projected = localize_view(view, cat, "en")
        self.assertEqual(projected["title"], "Joan's voices")
        self.assertEqual(projected["scene"]["text"], "Welcome!")
        self.assertEqual(projected["choices"][0]["label"], "Enter")
        self.assertEqual(view["scene"]["text"], "Bienvenue !")
        self.assertEqual(view["choices"][0]["label"], "Entrer")
        self.assertEqual(projected["revision"], 11)

    def test_v2_line_id_localizes_active_dialogue_without_touching_cursor(self):
        from copy import deepcopy
        project = deepcopy(PROJECT)
        project["story"]["schema_version"] = 2
        project["story"]["scenes"][0]["lines"] = [
            {"id": "opening", "speaker": "Jeanne", "text": "Bonjour."},
            {"id": "reply", "speaker": "Capitaine", "text": "À la porte."},
        ]
        cat, drift = seeded_for_project(project)
        self.assertFalse(drift)
        self.assertIn("story.intro.line.reply.text", cat.data["entries"])
        cat = cat.with_translation("story.intro.line.reply.text", "en", "At the gate.")
        cat = cat.with_translation("story.intro.line.reply.speaker", "en", "Captain")
        state = {
            "campaign": "acte_1", "title": "Les voix de Jeanne",
            "scene": {"id": "intro", "title": "Une rencontre",
                      "speaker": "Capitaine", "text": "À la porte."},
            "dialogue_line": {"scene_id": "intro", "id": "reply",
                              "index": 1, "count": 2, "complete": True,
                              "speaker": "Capitaine", "text": "À la porte."},
            "choices": [{"id": "go", "label": "Entrer"}],
            "revision": 31,
        }
        before = deepcopy(state)
        translated = localize_view(state, cat, "en")
        self.assertEqual(translated["scene"]["text"], "At the gate.")
        self.assertEqual(translated["scene"]["speaker"], "Captain")
        self.assertEqual(translated["dialogue_line"]["text"], "At the gate.")
        self.assertEqual(translated["dialogue_line"]["id"], "reply")
        self.assertEqual(translated["dialogue_line"]["index"], 1)
        self.assertEqual(translated["revision"], 31)
        self.assertEqual(state, before)
        # A reordered line keeps its translation because its id is stable.
        project["story"]["scenes"][0]["lines"].reverse()
        _, drift = seeded_for_project(project, cat)
        self.assertEqual(drift, ())

    def test_v2_stale_line_text_does_not_show_older_translation(self):
        from copy import deepcopy
        project = deepcopy(PROJECT)
        project["story"]["schema_version"] = 2
        project["story"]["scenes"][0]["lines"] = [
            {"id": "reply", "speaker": "Jeanne", "text": "Bonjour."},
        ]
        cat, _ = seeded_for_project(project)
        cat = cat.with_translation("story.intro.line.reply.text", "en", "Hello.")
        state = {
            "campaign": "acte_1", "scene": {
                "id": "intro", "speaker": "Jeanne", "text": "Texte modifié"},
            "dialogue_line": {
                "scene_id": "intro", "id": "reply", "speaker": "Jeanne",
                "text": "Texte modifié", "index": 0, "count": 1, "complete": True},
            "choices": [],
        }
        translated = localize_view(state, cat, "en")
        self.assertEqual(translated["scene"]["text"], "Texte modifié")
        self.assertEqual(translated["dialogue_line"]["text"], "Texte modifié")

    def test_real_r42_checkpoint_line_translation_survives_resume(self):
        from drawtemp.player.controller import PlayerController
        from drawtemp.sdk.reference import reference_project
        from sporebound.narrative_r42 import migrate_story_v1, set_dialogue_lines

        content, legacy = reference_project()
        v2 = migrate_story_v1(legacy, content)
        project = set_dialogue_lines(v2, content, "arrival", [
            {"id": "intro", "speaker": "Jeanne", "text": "Bonjour capitaine."},
            {"id": "reply", "speaker": "Capitaine", "text": "Bonjour Jeanne."},
        ])
        cat, drift = seeded_for_project(project.to_dict())
        self.assertEqual(drift, ())
        cat = cat.with_translation(
            "story.arrival.line.reply.text", "en", "Hello, Joan.")
        cat = cat.with_translation(
            "story.arrival.line.reply.speaker", "en", "Captain")
        with TemporaryDirectory() as folder:
            controller = PlayerController(content, project, "main", folder)
            controller.new_game()
            state = controller.next_dialogue_line()
            self.assertEqual(state["dialogue_line"]["id"], "reply")
            original = controller.session.recording()
            localized = localize_view(state, cat, "en")
            self.assertEqual(localized["scene"]["text"], "Hello, Joan.")
            self.assertEqual(localized["scene"]["speaker"], "Captain")
            self.assertEqual(controller.session.recording(), original)
            controller.save(1)
            resumed = PlayerController(content, project, "main", folder)
            restored = resumed.load(1)
            self.assertEqual(restored["dialogue_line"]["id"], "reply")
            self.assertEqual(
                localize_view(restored, cat, "en")["scene"]["text"],
                "Hello, Joan.")

    def test_pluralization_format_and_missing_fallback(self):
        data = Catalog.empty().data
        data["entries"]["inventory.items"] = {
            "source": {"one": "{count} objet", "other": "{count} objets"},
            "translations": {"en": {
                "one": "{count} item", "other": "{count} items"}},
            "context": "Inventory count", "max_length": 40,
        }
        cat = Catalog(data)
        self.assertEqual(cat.render("inventory.items", "en", count=1), "1 item")
        self.assertEqual(cat.render("inventory.items", "en", count=0), "0 items")
        self.assertEqual(cat.render("inventory.items", "fr", count=0), "0 objet")
        self.assertEqual(cat.render("inventory.items", "fr", count=2), "2 objets")
        self.assertIn("3", cat.render("inventory.items", "qps-ploc", count=3))

    def test_reject_placeholder_injection_and_bad_plural(self):
        data = Catalog.empty().data
        data["entries"]["ui.play"] = {
            "source": "Bonjour {name}", "translations": {},
            "context": "", "max_length": 20,
        }
        cat = Catalog(data)
        with self.assertRaises(LocalizationError):
            cat.with_translation("ui.play", "en", "Hello {name.__class__}")
        with self.assertRaises(LocalizationError):
            cat.with_translation("ui.play", "en", "Hello {other}")
        with self.assertRaises(LocalizationError):
            cat.render("ui.play", "fr")
        self.assertEqual(cat.render("ui.play", "fr", name="Léa"),
                         "Bonjour Léa")
        invalid = cat.data
        invalid["entries"]["ui.play"]["source"] = {"one": "One", "other": "Other"}
        invalid["entries"]["ui.play"]["translations"] = {
            "en": {"one": "One"}}
        with self.assertRaises(LocalizationError):
            Catalog(invalid)

    def test_utf8_pseudo_and_rtl_isolates(self):
        cat, _ = seeded_for_project(PROJECT)
        accented = cat.render("project.title", "qps-ploc")
        mirrored = cat.render("project.title", "qps-plocm")
        self.assertTrue(accented.startswith("[!!"))
        self.assertIn("ï", accented)
        self.assertTrue(mirrored.startswith("\u2067"))
        self.assertTrue(mirrored.endswith("\u2069"))
        self.assertEqual(cat.render("campaign.acte_1.name", "fr"), "La lisière")

    def test_save_reload_concurrency_and_legacy_project_unchanged(self):
        with TemporaryDirectory() as temp:
            project_path = Path(temp) / "game.json"
            project_path.write_text("unmodified", encoding="utf-8")
            sidecar = sidecar_path(project_path)
            self.assertEqual(sidecar.name, "game.l10n.json")
            cat, _ = seeded_for_project(PROJECT)
            revision = cat.save(sidecar, expected_revision=None)
            self.assertEqual(revision, file_revision(sidecar))
            self.assertIsNotNone(Catalog.load(sidecar))
            self.assertEqual(project_path.read_text(encoding="utf-8"), "unmodified")
            with self.assertRaises(LocalizationError):
                cat.save(sidecar, expected_revision=None)
            updated = cat.with_translation("project.title", "en", "Voices")
            second = updated.save(sidecar, expected_revision=revision)
            self.assertNotEqual(second, revision)
            with self.assertRaises(LocalizationError):
                cat.save(sidecar, expected_revision=revision)

    def test_audit_missing_and_length(self):
        cat, _ = seeded_for_project(PROJECT)
        self.assertIn(("project.title", "missing"), cat.audit("en"))
        long = cat.with_translation("project.title", "en", "X" * 121)
        self.assertIn(("project.title", "too_long"), long.audit("en"))

    def test_headless_does_not_import_qt(self):
        import subprocess
        import sys
        subprocess.run([sys.executable, "-c",
                        "import sys; import drawtemp.localization; "
                        "assert 'PySide6' not in sys.modules"], check=True)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 unavailable")
class R57QtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_studio_dialog_keyboard_and_sidecar(self):
        from PySide6.QtCore import QSettings
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        from drawtemp.studio.qt_shell import StudioWindow
        from drawtemp.studio.r57_translation_qt import TranslationStudioDialog
        with TemporaryDirectory() as temp:
            content = Path(temp) / "game.json"
            session = AuthoringSession.new(*reference_project())
            session.save_as(content)
            window = StudioWindow(
                session, content_path=content,
                settings=QSettings(str(Path(temp) / "settings.ini"),
                                   QSettings.IniFormat))
            try:
                self.assertIn("r57_translation", window.commands)
                dialog = TranslationStudioDialog(session, content, window)
                self.assertGreater(dialog.keys.count(), 0)
                self.assertTrue(dialog.search.focusPolicy())
                dialog.keys.setCurrentRow(0)
                self.assertTrue(dialog.text.isReadOnly() is False)
                dialog.text.setPlainText("Localisation test")
                dialog.save()
                self.assertTrue(sidecar_path(content).is_file())
                dialog.close()
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()

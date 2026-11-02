"""Headless English-first UI JSON resource localization regression tests."""
import unittest
from drawtemp.localization.ui import (
    DEFAULT_LANGUAGE, LANGUAGES, UiLocalizationError, audit_catalogs,
    get_catalog, language_choices, normalize_language, ui_text,
)
from sporebound.game_project import GameProject

class UiLocalizationTests(unittest.TestCase):
    def test_default_and_resources(self):
        self.assertEqual(DEFAULT_LANGUAGE, "en")
        self.assertEqual(LANGUAGES, ("en", "fr"))
        self.assertEqual(language_choices(), (("en", "English"), ("fr", "Français")))
        self.assertEqual(normalize_language(None), "en")
        self.assertEqual(normalize_language("de"), "en")
        self.assertEqual(ui_text("menu.file"), "&File")
        self.assertEqual(ui_text("player.resume"), "Resume")
        self.assertEqual(GameProject().options["language"], "en")

    def test_french_separate_from_project_source(self):
        self.assertEqual(ui_text("menu.file", "fr"), "&Fichier")
        self.assertEqual(ui_text("player.resume", "fr"), "Reprendre")
        project = GameProject()
        project.options["language"] = "fr"
        self.assertEqual(project.options["language"], "fr")
        self.assertEqual(ui_text("menu.file"), "&File")

    def test_catalog_integrity(self):
        self.assertEqual(audit_catalogs(), {"fr": []})
        self.assertEqual(set(get_catalog("en")), set(get_catalog("fr")))
        self.assertEqual(ui_text("studio.workspace_prefix", name="Maps"), "Workspace: Maps")
        self.assertEqual(ui_text("studio.workspace_prefix", "fr", name="Cartes"), "Atelier : Cartes")
        self.assertEqual(ui_text("menu.tools", "xx"), "&Tools")
        self.assertEqual(ui_text("custom.unknown", "fr"), "custom.unknown")
        with self.assertRaises(UiLocalizationError):
            ui_text("studio.workspace_prefix", "fr")
        with self.assertRaises(UiLocalizationError):
            ui_text("studio.workspace_prefix", "fr", wrong="key")

    def test_legacy_r57_content_localization(self):
        from drawtemp.localization import Catalog
        self.assertEqual(Catalog.empty("fr").data["source_language"], "fr")

if __name__ == "__main__":
    unittest.main()

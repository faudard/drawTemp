"""Regression coverage for English-first application UI localization."""
import unittest

from drawtemp.localization.ui import (
    DEFAULT_LANGUAGE, LANGUAGES, UI_STRINGS, normalize_language, ui_text,
)
from sporebound.game_project import GameProject


class UiLocalizationTests(unittest.TestCase):
    def test_default_is_english_even_without_os_locale(self):
        self.assertEqual(DEFAULT_LANGUAGE, "en")
        self.assertEqual(normalize_language(None), "en")
        self.assertEqual(normalize_language("de"), "en")
        self.assertEqual(ui_text("menu.file"), "&File")
        self.assertEqual(ui_text("player.resume"), "Resume")
        self.assertEqual(GameProject().options["language"], "en")

    def test_french_is_explicit_and_does_not_change_project_content(self):
        self.assertEqual(ui_text("menu.file", "fr"), "&Fichier")
        self.assertEqual(ui_text("player.resume", "fr"), "Reprendre")
        project = GameProject()
        project.options["language"] = "fr"
        self.assertEqual(project.options["language"], "fr")
        self.assertEqual(ui_text("menu.file"), "&File")

    def test_key_coverage_and_fallback(self):
        self.assertEqual(set(UI_STRINGS["en"]), set(UI_STRINGS["fr"]))
        self.assertEqual(LANGUAGES, ("en", "fr"))
        self.assertEqual(ui_text("studio.workspace_prefix", name="Maps"), "Workspace: Maps")
        self.assertEqual(ui_text("studio.workspace_prefix", "fr", name="Cartes"), "Atelier : Cartes")
        self.assertEqual(ui_text("menu.tools", "xx"), "&Tools")
        self.assertEqual(ui_text("custom.unknown", "fr"), "custom.unknown")

    def test_existing_r57_catalog_still_supports_french_sources(self):
        from drawtemp.localization import Catalog
        catalog = Catalog.empty("fr")
        self.assertEqual(catalog.data["source_language"], "fr")


if __name__ == "__main__":
    unittest.main()

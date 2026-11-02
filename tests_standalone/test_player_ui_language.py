"""Headless player UI language tests; no Tk display or Qt dependency needed."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from drawtemp.localization.ui import language_choices, ui_text
from sporebound.player_ui_language import (
    PlayerLanguageError, language_path, load_ui_language, save_ui_language)
from sporebound.player_preferences import default_preferences, save_preferences


class GameLanguageTests(unittest.TestCase):
    def test_default_and_json_labels(self):
        self.assertEqual(language_choices(), (("en", "English"), ("fr", "Français")))
        self.assertEqual(ui_text("tk.options.language_label"), "Game language")
        self.assertEqual(ui_text("tk.options.language_label", "fr"), "Langue du jeu")
        for lang in ("en", "fr"):
            for key in ("tk.options.apply", "tk.options.action.execute",
                        "tk.title.new", "tk.title.options", "tk.pause.save"):
                self.assertNotEqual(ui_text(key, lang), key)

    def test_persist_language_separately_from_keyboard_and_saves(self):
        with TemporaryDirectory() as folder:
            profile = Path(folder) / "test.profile"
            self.assertEqual(load_ui_language(profile), ("en", None))
            keyboard = save_preferences(profile, default_preferences())
            initial = keyboard.read_bytes()
            path = save_ui_language(profile, "fr")
            self.assertEqual(path, language_path(profile))
            self.assertEqual(load_ui_language(profile), ("fr", None))
            self.assertEqual(keyboard.read_bytes(), initial)
            save_ui_language(profile, "en")
            self.assertEqual(load_ui_language(profile), ("en", None))

    def test_corrupt_and_unknown_preferences_cannot_be_overwritten(self):
        with TemporaryDirectory() as folder:
            profile = Path(folder) / "test.profile"
            for code in ("de", None, ""):
                with self.assertRaises(PlayerLanguageError):
                    save_ui_language(profile, code)
            path = language_path(profile)
            path.write_text('{"version": 99}', encoding="utf-8")
            original = path.read_bytes()
            self.assertEqual(load_ui_language(profile)[0], "en")
            self.assertIsNotNone(load_ui_language(profile)[1])
            with self.assertRaises(PlayerLanguageError):
                save_ui_language(profile, "fr")
            self.assertEqual(path.read_bytes(), original)

    def test_failed_atomic_replace_preserves_old_settings(self):
        with TemporaryDirectory() as folder:
            profile = Path(folder) / "test.profile"
            file = save_ui_language(profile, "fr")
            original = file.read_bytes()
            with patch("sporebound.player_ui_language.os.replace",
                       side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    save_ui_language(profile, "en")
            self.assertEqual(file.read_bytes(), original)
            self.assertEqual(list(Path(folder).glob(".player-language-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()

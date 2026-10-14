"""R7.7 independent, atomic Player preferences and compatibility gates."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from sporebound.player_preferences import (
    default_preferences, load_preferences, preferences_path,
    save_preferences, validate_preferences,
)


class PlayerPreferencesR7Tests(unittest.TestCase):
    def test_default_preferences_are_separate_from_session_slots(self):
        with TemporaryDirectory() as tmp:
            profile = Path(tmp) / "custom.profile"
            settings, warning = load_preferences(profile)
            self.assertIsNone(warning)
            self.assertEqual(settings["version"], 1)
            self.assertEqual(settings["text_scale"], 100)
            self.assertEqual(preferences_path(profile).name,
                             "custom.profile.player-ux.json")
            self.assertFalse(preferences_path(profile).exists())

    def test_roundtrip_with_remapped_key_and_accessibility(self):
        with TemporaryDirectory() as tmp:
            profile = Path(tmp) / "player.profile"
            expected = default_preferences()
            expected["keybindings"]["execute"] = "<F1>"
            expected["text_scale"] = 150
            expected["high_contrast"] = True
            expected["compact_hud"] = True
            save_preferences(profile, expected)
            loaded, warning = load_preferences(profile)
            self.assertIsNone(warning)
            self.assertEqual(loaded, expected)

    def test_letters_persist_without_preferences_migration(self):
        with TemporaryDirectory() as tmp:
            profile = Path(tmp) / "player.profile"
            prefs = default_preferences()
            prefs["keybindings"]["north"] = "<Key-w>"
            prefs["keybindings"]["west"] = "<Key-a>"
            save_preferences(profile, prefs)
            actual, warning = load_preferences(profile)
            self.assertIsNone(warning)
            self.assertEqual(actual["version"], 1)
            self.assertEqual(actual["keybindings"]["north"], "<Key-w>")
            self.assertEqual(actual["keybindings"]["west"], "<Key-a>")

    def test_invalid_values_rejected_without_touching_existing_file(self):
        with TemporaryDirectory() as tmp:
            profile = Path(tmp) / "player.profile"
            path = save_preferences(profile, default_preferences())
            prior = path.read_bytes()
            for bad in (
                {"text_scale": "huge"},
                {"version": 2},
                {"high_contrast": 1},
                {"keybindings": {"execute": "<Return>"}},
                {"keybindings": dict(default_preferences()["keybindings"],
                                     cancel="<Return>")},
            ):
                document = default_preferences()
                document.update(bad)
                with self.assertRaises(ValueError):
                    save_preferences(profile, document)
                self.assertEqual(prior, path.read_bytes())

    def test_corrupt_file_kept_with_diagnostic_and_safe_defaults(self):
        with TemporaryDirectory() as tmp:
            profile = Path(tmp) / "player.profile"
            path = preferences_path(profile)
            path.write_text('{"version": 99, "unknown": true}', encoding="utf-8")
            saved = path.read_bytes()
            settings, warning = load_preferences(profile)
            self.assertEqual(settings, default_preferences())
            self.assertIn("ignoré", warning)
            self.assertEqual(path.read_bytes(), saved)

    def test_failed_atomic_rename_keeps_previous_settings(self):
        with TemporaryDirectory() as tmp:
            profile = Path(tmp) / "player.profile"
            path = save_preferences(profile, default_preferences())
            prior = path.read_bytes()
            document = default_preferences()
            document["text_scale"] = 125
            with patch("sporebound.player_preferences.os.replace",
                       side_effect=OSError("rename denied")):
                with self.assertRaises(OSError):
                    save_preferences(profile, document)
            self.assertEqual(path.read_bytes(), prior)
            self.assertEqual(sorted(Path(tmp).glob(".player-ux-*.tmp")), [])

    def test_profiles_have_isolated_settings(self):
        with TemporaryDirectory() as tmp:
            one, two = Path(tmp)/"one", Path(tmp)/"two"
            a = default_preferences()
            a["high_contrast"] = True
            save_preferences(one, a)
            left, _ = load_preferences(one)
            right, _ = load_preferences(two)
            self.assertTrue(left["high_contrast"])
            self.assertFalse(right["high_contrast"])


if __name__ == "__main__":
    unittest.main()

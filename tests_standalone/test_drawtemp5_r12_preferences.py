"""R12.8/R12.9: durable, context-safe keybindings and UI preferences."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.player.preferences import (
    PreferenceError, PlayerPreferences, initial_settings, validate)
from drawtemp.player.controller import PlayerController
from drawtemp.sdk.reference import reference_project


class R12InputPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "player-preferences.json"

    def test_azerty_qwerty_profiles_and_contextual_arrows(self):
        prefs = PlayerPreferences(self.path)
        self.assertEqual(prefs.resolve("Z", "exploration"), "explore_up")
        self.assertEqual(prefs.resolve("Q", "exploration"), "explore_left")
        self.assertEqual(prefs.resolve("Up", "exploration"), "explore_up")
        self.assertEqual(prefs.resolve("Up", "battle"), "battle_up")
        self.assertEqual(prefs.resolve("Space", "battle"), "battle_end")
        self.assertEqual(prefs.resolve("F5", "dialogue"), "save")
        self.assertEqual(prefs.resolve("Escape", "title"), "pause")
        self.assertEqual(prefs.resolve("M", "dialogue"), "")
        self.assertEqual(prefs.resolve("Z", "battle"), "")

        prefs.profile("qwerty")
        self.assertEqual(prefs.resolve("W", "exploration"), "explore_up")
        self.assertEqual(prefs.resolve("A", "exploration"), "explore_left")
        self.assertEqual(prefs.resolve("Z", "exploration"), "")
        prefs.rebind("explore_up", "I")
        self.assertEqual(prefs.resolve("I", "exploration"), "explore_up")
        prefs.profile("azerty")
        self.assertEqual(prefs.resolve("Z", "exploration"), "explore_up")
        persisted = PlayerPreferences(self.path)
        self.assertEqual(persisted.view()["profile"], "azerty")
        persisted.profile("qwerty")
        self.assertEqual(persisted.binding("explore_up"), "I")

    def test_duplicate_and_direction_conflicts_are_atomic(self):
        prefs = PlayerPreferences(self.path)
        prefs.rebind("battle_move", "X")
        prior = self.path.read_bytes()
        snapshot = prefs.view()
        for action, key in [
            ("explore_up", "Q"),      # exploration duplicate
            ("battle_attack", "X"),   # combat duplicate
            ("save", "Z"),            # global vs exploration
            ("pause", "X"),           # global vs combat
            ("battle_end", "Up"),     # reserved directional arrow
            ("explore_up", "Left"),   # wrong direction
            ("explore_up", "F11"),    # unsupported key
            ("not_an_action", "J"),
        ]:
            with self.subTest(action=action, key=key):
                with self.assertRaises(PreferenceError):
                    prefs.rebind(action, key)
                self.assertEqual(prefs.view(), snapshot)
                self.assertEqual(self.path.read_bytes(), prior)
        prefs.rebind("battle_up", "I")
        self.assertEqual(prefs.resolve("Up", "battle"), "battle_up")
        prefs.reset()
        self.assertEqual(prefs.binding("battle_up"), "Up")

    def test_appearance_is_validated_saved_and_reloaded(self):
        prefs = PlayerPreferences(self.path)
        for name, value in [
            ("text_scale", 1.25), ("high_contrast", True),
            ("show_grid", False), ("show_heights", True),
            ("fullscreen", True),
        ]:
            prefs.set_display(name, value)
        reloaded = PlayerPreferences(self.path)
        self.assertEqual(reloaded.view()["display"], {
            "text_scale": 1.25, "high_contrast": True, "show_grid": False,
            "show_heights": True, "fullscreen": True,
        })
        prior = self.path.read_bytes()
        for name, value in [
            ("text_scale", "1.0"), ("text_scale", 1.5),
            ("fullscreen", 1), ("show_grid", 0), ("audio_volume", 50),
        ]:
            with self.subTest(name=name, value=value):
                with self.assertRaises(PreferenceError):
                    prefs.set_display(name, value)
                self.assertEqual(self.path.read_bytes(), prior)

    def test_incompatible_and_corrupt_files_preserved_until_user_edits(self):
        cases = [
            "not json",
            json.dumps({"version": 7}),
            " " * 65537,
        ]
        for raw in cases:
            with self.subTest(raw=raw[:12]):
                self.path.write_text(raw, encoding="utf-8")
                prefs = PlayerPreferences(self.path)
                self.assertTrue(prefs.warning)
                self.assertEqual(prefs.view()["profile"], "azerty")
                self.assertEqual(self.path.read_text(encoding="utf-8"), raw)
                invalid = self.path.with_name(self.path.name + ".invalid")
                invalid.unlink(missing_ok=True)
                prefs.set_display("high_contrast", True)
                self.assertEqual(invalid.read_text(encoding="utf-8"), raw)
                self.assertTrue(PlayerPreferences(self.path).view()["display"]["high_contrast"])

    def test_io_failure_cannot_mutate_live_preferences(self):
        prefs = PlayerPreferences(self.path)
        before = prefs.view()
        with patch.object(prefs, "_persist", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                prefs.rebind("explore_up", "I")
        self.assertEqual(before, prefs.view())
        self.assertFalse(self.path.exists())

    def test_robust_versioned_schema_and_detached_views(self):
        doc = initial_settings()
        validate(doc)
        doc["active_profile"] = "unknown"
        with self.assertRaises(PreferenceError):
            validate(doc)
        prefs = PlayerPreferences(self.path)
        view = prefs.view()
        view["bindings"]["explore_up"] = "X"
        view["rows"][0]["key"] = "Z"
        self.assertEqual(prefs.binding("explore_up"), "Z")
        self.assertEqual(prefs.binding("save"), "F5")

    def test_game_session_and_preferences_have_separate_lifecycles(self):
        content, project = reference_project()
        player = PlayerController(content, project, "main", self.tmp.name)
        self.assertIn("settings", player.state())
        player.new_game()
        initial = player.session.recording()
        revision = player.state()["revision"]
        player.set_binding("explore_up", "I")
        player.set_profile("qwerty")
        player.set_display("show_grid", False)
        self.assertEqual(revision, player.state()["revision"])
        self.assertEqual(initial, player.session.recording())
        player.save(1)
        self.assertEqual(PlayerController(content, project, "main", self.tmp.name)
                         .state()["settings"]["display"]["show_grid"], False)
        self.assertEqual(player.state()["screen"], "dialogue")
        self.assertTrue((Path(self.tmp.name) / "slot_1.json").exists())


if __name__ == "__main__":
    unittest.main()

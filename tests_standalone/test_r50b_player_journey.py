"""R50.B PlayerController acceptance: CT/narrative intents and real disk recovery."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.studio.r28e_minigames import create_minigame
from drawtemp.studio.r50b_player_journey import (
    PlayerJourneyError, check_player_journey,
)


class R50BPlayerJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_two_real_player_intents_save_and_reopen(self):
        paths = {}
        for kind in ("duel_tactique", "choix_village"):
            with self.subTest(kind=kind):
                path = create_minigame(kind, self.root / kind) / "game.json"
                authored_bytes = path.read_bytes()
                manifest = path.with_name("game.game.json")
                manifest_bytes = manifest.read_bytes()
                report = check_player_journey(path, kind=kind)
                self.assertEqual(report["minigame"], kind)
                self.assertTrue(report["preflight_passed"])
                self.assertTrue(report["player_controller_new_game"])
                self.assertTrue(report["player_intent_persisted"])
                self.assertTrue(report["player_save_reload_equal"])
                self.assertTrue(report["authored_documents_unchanged"])
                self.assertFalse(report["qt_onscreen_verified"])
                self.assertFalse(report["native_player_verified"])
                self.assertFalse(report["clean_machine_export_verified"])
                self.assertFalse(report["release_9_0_certified"])
                self.assertEqual(path.read_bytes(), authored_bytes)
                self.assertEqual(manifest.read_bytes(), manifest_bytes)
                self.assertEqual(
                    sorted(p.name for p in path.parent.iterdir()),
                    ["game.game.json", "game.json"],
                )
                paths[kind] = report["checkpoint_digest"]
        self.assertNotEqual(paths["duel_tactique"], paths["choix_village"])

    def test_rejects_unimplemented_player_modes(self):
        project = create_minigame("duel_tactique", self.root / "good")
        path = project / "game.json"
        for label in ("action_adventure", "classic_rpg", "narrative_hybrid", "", None):
            with self.subTest(kind=label), self.assertRaises(PlayerJourneyError):
                check_player_journey(path, kind=label)

    def test_corrupted_author_documents_are_not_played_or_replaced(self):
        project = create_minigame("duel_tactique", self.root / "broken")
        manifest = project / "game.game.json"
        bad = b'{"version": 9999, "title": "Untrusted"}'
        manifest.write_bytes(bad)
        with self.assertRaises(PlayerJourneyError):
            check_player_journey(project / "game.json", kind="duel_tactique")
        self.assertEqual(manifest.read_bytes(), bad)
        self.assertFalse((project / "player-profile_session_saves").exists())


if __name__ == "__main__":
    unittest.main()

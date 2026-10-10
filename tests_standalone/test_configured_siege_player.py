"""2.5.4.2: player starts Studio-authored sieges without bypassing campaign gates."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController
from sporebound.siege_authoring import add_front, new_blueprint, replace_siege, set_finale


class ConfiguredSiegePlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)
        cls.original = GameProject.load(
            Path(DEFAULT_CONTENT).with_suffix(".game.json"), cls.content)

    def project(self):
        bp = new_blueprint("castle_custom", "main", "garden", front="gate")
        bp = add_front(bp, "walls", "hold", strength=7,
                       opposition=11, doctrine="assault")
        bp = set_finale(bp, "walls", {"gate": ["victory"]})
        return replace_siege(self.original, self.content, bp)

    def test_campaign_gate_and_unrelated_campaign_are_enforced(self):
        project = self.project()
        session = GameSession.new(self.content, project, "main")
        self.assertEqual(session.available_sieges()[0]["locked"], ["hold"])
        self.assertFalse(session.available_sieges()[0]["ready"])
        previous = session.recording()
        with self.assertRaisesRegex(RuleError, "locked"):
            session.start_configured_siege("castle_custom")
        self.assertEqual(previous, session.recording())
        with self.assertRaises(RuleError):
            session.start_configured_siege("unknown")
        unrelated = GameSession.new(self.content, project, "relique")
        self.assertEqual(unrelated.available_sieges(), [])
        with self.assertRaises(RuleError):
            unrelated.start_configured_siege("castle_custom")

    def test_authored_front_specs_finale_and_exact_replay(self):
        project = self.project()
        session = GameSession.new(self.content, project, "main", seed=7)
        session.progress.unlocked.append("hold")
        self.assertTrue(session.available_sieges()[0]["ready"])
        session.start_configured_siege("castle_custom")
        self.assertEqual(session.siege_id, "castle_custom")
        self.assertEqual(session.mode, "fronts")
        self.assertEqual(session.fronts.initial_specs["walls"]["strength"], 7)
        self.assertEqual(session.fronts.campaign.final, "walls")
        self.assertEqual(session.fronts.missions, {"gate": "garden", "walls": "hold"})
        session.set_doctrine("walls", "delay")
        session.advance_fronts()
        restored = GameSession.from_recording(
            session.recording(), self.content, project)
        self.assertEqual(restored.siege_id, "castle_custom")
        self.assertEqual(restored.fronts.digest(), session.fronts.digest())
        self.assertEqual(restored.recording(), session.recording())
        with self.assertRaises(RuleError):
            session.start_configured_siege("castle_custom")

    def test_persistent_player_slots_and_recovery(self):
        project = self.project()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "custom.game.json"
            ui = PlayerController(self.content, project, path)
            ui.new_game("main", 1, seed=21)
            before = ui.store().path.read_bytes()
            with self.assertRaises(RuleError):
                ui.start_configured_siege("castle_custom")
            self.assertEqual(ui.store().path.read_bytes(), before)
            self.assertEqual(ui.session.mode, "campaign")
            # This setup mimics an authored narrative decision unlocking a
            # sector; the runtime still verifies both missions are available.
            ui.session.progress.unlocked.append("hold")
            ui.save()
            ui.start_configured_siege("castle_custom")
            ui.advance_fronts()
            other = PlayerController(self.content, project, path)
            restored = other.load_game("main", 1)
            self.assertEqual(restored.siege_id, "castle_custom")
            self.assertEqual(restored.recording(), ui.session.recording())
            # The final front must remain locked until the gate is won:
            # assert this gate rather than bypassing the actual siege policy.
            previous = other.session.recording()
            with self.assertRaises(RuleError):
                other.switch_front("walls")
            self.assertEqual(other.session.recording(), previous)
            other.set_doctrine("walls", "hold")
            latest = PlayerController(self.content, project, path)
            latest.load_game("main", 1)
            self.assertEqual(latest.session.fronts.timeline.focused, "gate")
            self.assertEqual(latest.session.fronts.timeline.fronts["walls"]["doctrine"],
                             "hold")
            self.assertEqual(latest.session.siege_id, "castle_custom")
            self.assertEqual(latest.session.fronts.history, other.session.fronts.history)

    def test_siege_identity_cannot_be_renamed_in_checkpoint(self):
        project = self.project()
        session = GameSession.new(self.content, project, "main")
        session.progress.unlocked.append("hold")
        session.start_configured_siege("castle_custom")
        record = session.recording()
        changed = deepcopy(record)
        changed["siege_id"] = "not_castle"
        changed["digest"] = digest({k: v for k, v in changed.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(changed, self.content, project)
        changed["siege_id"] = "castle_custom"
        changed["mode"] = "battle"
        changed["digest"] = digest({k: v for k, v in changed.items() if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(changed, self.content, project)

    def test_duplicate_missions_are_never_launched(self):
        duplicate = new_blueprint("double", "main", "garden", front="east")
        duplicate = add_front(duplicate, "west", "garden")
        project = replace_siege(self.original, self.content, duplicate)
        session = GameSession.new(self.content, project, "main")
        row = session.available_sieges()[0]
        self.assertFalse(row["ready"])
        with self.assertRaisesRegex(RuleError, "distinct"):
            session.start_configured_siege("double")
        self.assertEqual(session.mode, "campaign")

    def test_legacy_ad_hoc_fronts_do_not_gain_siege_identity(self):
        session = GameSession.new(self.content, self.original, "main")
        session.progress.unlocked.append("hold")
        session.start_fronts({"gate": "garden", "walls": "hold"}, "gate")
        record = session.recording()
        self.assertNotIn("siege_id", record)
        restored = GameSession.from_recording(record, self.content, self.original)
        self.assertIsNone(restored.siege_id)
        restored.abandon_encounter()
        self.assertIsNone(restored.siege_id)


if __name__ == "__main__":
    unittest.main()

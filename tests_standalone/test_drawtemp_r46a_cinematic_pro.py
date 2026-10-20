"""R46.A regression gates: canonical R11 + opt-in GameSession cue ledger."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.cinematic_pro import EXTENSION
from sporebound.cinematics import cinematic_template, event_template
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import Content, RuleError


class R46CinematicProTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.legacy = GameProject.default(self.content)
        campaign_id = self.legacy.campaigns[0]["id"]
        clip = cinematic_template("war_council", "Le conseil de guerre",
                                  "campaign_start", campaign_id)
        clip["duration_ms"] = 5000
        clip["events"] = [
            event_template("camera", "opening_shot", 0, 2000),
            event_template("dialogue", "decision", 1000, 900),
            event_template("sound", "farewell", 4000, 500),
        ]
        self.project = deepcopy(self.legacy)
        self.project.cinematics = [clip]
        self.project.extensions[EXTENSION] = {
            "schema_version": 1,
            "data": {
                "version": 1,
                "cues": [
                    {"clip": "war_council", "event": "opening_shot",
                     "effect": {"kind": "set_flag", "flag": "war_council_seen",
                                "value": True}},
                    {"clip": "war_council", "event": "decision",
                     "effect": {"kind": "set_flag", "flag": "war_council_choice",
                                "value": True}},
                    {"clip": "war_council", "event": "farewell",
                     "effect": {"kind": "set_flag", "flag": "war_council_closed",
                                "value": True}},
                ],
            },
        }
        self.project.validate(self.content)
        self.campaign_id = campaign_id

    def _session(self):
        return GameSession.new(self.content, self.project, self.campaign_id,
                               seed=19)

    def test_legacy_manifest_and_session_remain_byte_contract_compatible(self):
        self.assertNotIn(EXTENSION, self.legacy.to_dict().get("extensions", {}))
        session = GameSession.new(self.content, self.legacy, self.campaign_id)
        record = session.recording()
        self.assertNotIn("cinematic_pro", record)
        restored = GameSession.from_recording(record, self.content, self.legacy)
        self.assertEqual(restored.recording(), record)
        with self.assertRaises(RuleError):
            session.cinematic_pro_start("war_council")

    def test_versioned_project_roundtrip_and_fail_closed_references(self):
        data = self.project.to_dict()
        self.assertEqual(GameProject.from_dict(data, self.content).to_dict(), data)
        invalid = [
            lambda c: c.update(event="absent"),
            lambda c: c.update(clip="absent"),
            lambda c: c.update(at_ms=3000),  # no second authored timeline
            lambda c: c["effect"].update(kind="run_script"),
            lambda c: c["effect"].update(value=1),
            lambda c: c["effect"].update(flag="../escape"),
        ]
        for change in invalid:
            with self.subTest(change=repr(change)), self.assertRaises(RuleError):
                broken = deepcopy(data)
                cue = broken["extensions"][EXTENSION]["data"]["cues"][1]
                change(cue)
                GameProject.from_dict(broken, self.content)
        broken = deepcopy(data)
        broken["extensions"][EXTENSION]["data"]["cues"].append(
            deepcopy(broken["extensions"][EXTENSION]["data"]["cues"][0]))
        with self.assertRaises(RuleError):
            GameProject.from_dict(broken, self.content)
        broken = deepcopy(data)
        broken["extensions"][EXTENSION]["data"]["version"] = 99
        with self.assertRaises(RuleError):
            GameProject.from_dict(broken, self.content)

    def test_seek_is_presentation_only_advance_pause_and_skip_once(self):
        session = self._session()
        self.assertEqual(session.cinematic_pro_start("war_council"),
                         ("war_council/opening_shot",))
        self.assertTrue(session.progress.story_flags["war_council_seen"])
        self.assertNotIn("war_council_choice", session.progress.story_flags)
        session.cinematic_pro_seek(4500)
        self.assertNotIn("war_council_choice", session.progress.story_flags)
        self.assertNotIn("war_council_closed", session.progress.story_flags)
        committed = session.cinematic_pro_skip()
        self.assertEqual(committed, ("war_council/decision", "war_council/farewell"))
        self.assertTrue(session.progress.story_flags["war_council_choice"])
        self.assertTrue(session.progress.story_flags["war_council_closed"])
        self.assertEqual(session.cinematic_pro_skip(), ())
        # Replay of the same clip cannot duplicate gameplay effects.
        self.assertEqual(session.cinematic_pro_start("war_council"), ())
        self.assertEqual(session.cinematic_pro_advance(5000), ())
        state = session.cinematic_pro_state()
        self.assertFalse(state["playing"])
        self.assertEqual(state["position_ms"], 5000)
        self.assertEqual(len(state["applied"]), 3)

    def test_checkpoint_resume_and_history_safe_seek(self):
        session = self._session()
        session.cinematic_pro_start("war_council")
        session.cinematic_pro_advance(1500)
        self.assertTrue(session.progress.story_flags["war_council_choice"])
        self.assertNotIn("war_council_closed", session.progress.story_flags)
        session.cinematic_pro_pause()
        with self.assertRaises(RuleError):
            session.cinematic_pro_advance(1)
        record = session.recording()
        restored = GameSession.from_recording(record, self.content, self.project)
        self.assertEqual(restored.recording(), record)
        restored.cinematic_pro_seek(0)  # rewind never reverses committed flags
        restored.cinematic_pro_resume()
        self.assertEqual(restored.cinematic_pro_advance(2500), ())
        self.assertEqual(restored.cinematic_pro_advance(2500),
                         ("war_council/farewell",))
        self.assertEqual(restored.cinematic_pro_skip(), ())
        self.assertEqual(restored.progress.story_flags["war_council_closed"], True)

    def test_malformed_checkpoint_rejected_even_with_recomputed_digest(self):
        session = self._session()
        session.cinematic_pro_start("war_council")
        snapshot = session.recording()
        for invalid in (
            lambda x: x["cinematic_pro"].update(position_ms=6000),
            lambda x: x["cinematic_pro"].update(applied=["unknown/marker"]),
            lambda x: x["cinematic_pro"].update(applied=["war_council/decision",
                                                         "war_council/decision"]),
            lambda x: x.pop("cinematic_pro"),
        ):
            bad = deepcopy(snapshot)
            invalid(bad)
            bad["digest"] = digest({key: value for key, value in bad.items()
                                    if key != "digest"})
            with self.subTest(invalid=repr(invalid)), self.assertRaises(RuleError):
                GameSession.from_recording(bad, self.content, self.project)

    def test_tick_quantization_is_render_frequency_independent(self):
        left = self._session()
        right = self._session()
        left.cinematic_pro_start("war_council")
        right.cinematic_pro_start("war_council")
        left.cinematic_pro_advance(5000)
        for step in (110, 890, 1500, 2500):
            right.cinematic_pro_advance(step)
        self.assertEqual(left.recording(), right.recording())


if __name__ == "__main__":
    unittest.main()

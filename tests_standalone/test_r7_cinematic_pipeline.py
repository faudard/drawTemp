"""R7.13–R7.16 regression gates for Studio, Player and certified scene paths."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.audio_timeline import CinematicAudioDirector, mix_at
from sporebound.cinematic_player import draw_frame
from sporebound.cinematics import (cinematic_template, event_template, frame_at)
from sporebound.event_cinematic_qa import audit_event_cinematic_path
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from tests_standalone.test_scene_cinematics import cinematic_project, start_at_breach
from sporebound.authored_siege_player import AuthoredSiegeController


class R7TimelineTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.clip = cinematic_template("r7", "Timeline 3.0", "campaign_start", "main")
        self.clip["duration_ms"] = 8000
        actor = event_template("actor", "hero", 0, 8000)
        actor["easing"] = "ease_in"
        cam = event_template("camera", "shot_a", 0, 8000)
        cam.update(shot="arrival", transition="wipe", easing="ease_out",
                   **{"to": [.5, -.25]})
        dialogue = event_template("dialogue", "line", 1000, 3000)
        dialogue.update(text="Bonjour Jeanne", portrait="jeanne",
                        expression="determined", chars_per_second=10)
        fade = event_template("fade", "fade", 5000, 3000)
        fade["easing"] = "ease_in_out"
        music = event_template("sound", "score", 0, 8000)
        music.update(cue="theme", bus="music", volume=100, volume_to=0,
                     loop=True, fade_in_ms=0, fade_out_ms=0)
        self.clip["events"] = [actor, cam, dialogue, fade, music]
        self.project.cinematics = [self.clip]

    def test_eased_shot_and_expressive_text_seek(self):
        self.project.validate(self.content)
        frame = frame_at(self.clip, 2000)
        self.assertAlmostEqual(dict(frame.actors)["jeanne"][0], .18125)
        self.assertAlmostEqual(frame.camera[0], .21875)
        self.assertEqual(frame.shot, "arrival")
        self.assertIsNone(frame.shot_transition)  # wipe completes in first quarter
        self.assertEqual(frame.dialogue, ("Jeanne", "Bonjour Jeanne"))
        self.assertEqual(frame.dialogue_presentation.visible_text, "Bonjour Je")
        self.assertEqual(frame.dialogue_presentation.expression, "determined")
        early = frame_at(self.clip, 1500)
        self.assertEqual(early.dialogue_presentation.visible_text, "Bonjo")
        self.assertEqual(frame_at(self.clip, 0).shot_transition[0], "wipe")
        self.assertIsNone(frame_at(self.clip, 5000).dialogue)
        self.assertAlmostEqual(frame_at(self.clip, 6500).fade[1], .5)
        self.assertEqual(frame_at(self.clip, 6500), frame_at(self.clip, 6500))

    def test_volume_automation_and_seek_without_historical_cues(self):
        self.assertEqual(mix_at(self.clip, 0)[0].level, 1)
        self.assertEqual(mix_at(self.clip, 4000)[0].level, .5)
        self.assertAlmostEqual(mix_at(self.clip, 6000)[0].level, .25)
        stage = Mock()
        director = CinematicAudioDirector(self.clip, stage)
        director.seek(6000)
        stage.play_track.assert_called_once()
        stage.set_track_level.assert_called_with("score", .25)
        stage.cue.assert_not_called()
        director.advance(6500)
        stage.cue.assert_not_called()

    def test_strict_schema_and_roundtrip_preserve_legacy_contract(self):
        serialized = self.project.to_dict()
        restored = GameProject.from_dict(serialized, self.content)
        self.assertEqual(restored.cinematics, [self.clip])
        for eid, field, invalid in (
                ("hero", "easing", "bounce"),
                ("shot_a", "transition", "teleport"),
                ("shot_a", "shot", "../bad"),
                ("line", "expression", "unknown"),
                ("line", "chars_per_second", True),
                ("line", "chars_per_second", 121),
                ("score", "volume_to", -1),
                ("score", "volume_to", True)):
            with self.subTest(field=field, invalid=invalid):
                bad = deepcopy(serialized)
                event = next(e for e in bad["cinematics"][0]["events"]
                             if e["id"] == eid)
                event[field] = invalid
                with self.assertRaises(RuleError):
                    GameProject.from_dict(bad, self.content)
        legacy = event_template("dialogue", "old", 0, 800)
        old = cinematic_template("old", "Old", "campaign_start", "main")
        old["events"] = [legacy]
        self.assertEqual(frame_at(old, 100).dialogue,
                         ("Jeanne", "Notre histoire commence..."))
        self.assertEqual(frame_at(old, 100).dialogue_presentation.visible_text,
                         legacy["text"])

    def test_player_renders_visible_text_and_portrait_without_tk(self):
        canvas = Mock()
        canvas.winfo_width.return_value = 800
        canvas.winfo_height.return_value = 500
        image = object()
        renderer = Mock()
        renderer.image.return_value = image
        frame = draw_frame(canvas, self.clip, 1500, renderer)
        self.assertEqual(frame.dialogue_presentation.visible_text, "Bonjo")
        texts = [c.kwargs["text"] for c in canvas.create_text.call_args_list]
        self.assertIn("Bonjo", texts)
        self.assertNotIn("Bonjour Jeanne", texts)
        renderer.image.assert_any_call("portrait", "jeanne_determined")


class R7PipelineQATests(unittest.TestCase):
    def test_certified_path_matches_real_siege_replay_and_gameplay_effect(self):
        content, bp, project = cinematic_project()
        report = audit_event_cinematic_path(
            project, content, source_kind="strategic_event",
            source_id="castle_causal/open_portcullis", choice_id="continue")
        self.assertEqual(report.scene_id, "breach")
        self.assertEqual(report.cinematic_ids,
                         ("lever_reveal", "army_charge"))
        self.assertEqual(report.gameplay_effects, ("set_flag",))
        self.assertEqual(len(report.timeline_sha256), 64)
        self.assertEqual(report, audit_event_cinematic_path(
            project, content, source_kind="strategic_event",
            source_id="castle_causal/open_portcullis", choice_id="continue"))
        with TemporaryDirectory() as folder:
            path = Path(folder) / "r7.game.json"
            ctl = start_at_breach(content, bp, project, path)
            self.assertEqual(ctl.active_scene()["id"], report.scene_id)
            for cid in report.cinematic_ids:
                self.assertEqual(ctl.pending_cinematic()["id"], cid)
                ctl.acknowledge_cinematic(cid)
            ctl.choose_story_option(report.choice_id)
            self.assertTrue(ctl.story.progress.story_flags["gate_opened"])
            restored = AuthoredSiegeController(content, bp, path, project=project)
            restored.continue_game()
            self.assertEqual(restored.story.recording(), ctl.story.recording())
            self.assertTrue(restored.story.progress.story_flags["gate_opened"])

    def test_gate_rejects_missing_link_choice_cinematic_and_consequence(self):
        content, bp, project = cinematic_project()
        source = "castle_causal/open_portcullis"
        with self.assertRaises(RuleError):
            audit_event_cinematic_path(project, content, source_kind="strategic_event",
                                       source_id="castle_causal/missing",
                                       choice_id="continue")
        with self.assertRaises(RuleError):
            audit_event_cinematic_path(project, content, source_kind="strategic_event",
                                       source_id=source, choice_id="missing")
        empty = deepcopy(project)
        empty.cinematics = []
        with self.assertRaises(RuleError):
            audit_event_cinematic_path(empty, content, source_kind="strategic_event",
                                       source_id=source, choice_id="continue")
        empty = deepcopy(project)
        empty.story["scenes"][0]["choices"][0]["effects"] = []
        with self.assertRaises(RuleError):
            audit_event_cinematic_path(empty, content, source_kind="strategic_event",
                                       source_id=source, choice_id="continue")


if __name__ == "__main__":
    unittest.main()

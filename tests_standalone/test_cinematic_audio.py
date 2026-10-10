"""Audio Studio 2.0: pure mix, safe validation, transport and pygame-free channels."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.assets import AssetRegistry
from sporebound.audio_stage import AudioStage
from sporebound.audio_timeline import CinematicAudioDirector, mix_at
from sporebound.cinematics import cinematic_template, event_template
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError


class AudioTimelineTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.clip = cinematic_template("demo", "Cinematic mixer", "campaign_start",
                                       self.project.campaigns[0]["id"])
        self.clip["duration_ms"] = 10000
        self.clip["events"] = [
            self.track("score", "score", "music", 0, 10000,
                       fade_in_ms=1000, fade_out_ms=1000, loop=True),
            self.track("wind", "wind", "ambience", 0, 9500, loop=True, volume=50),
            self.track("voice", "narration", "voice", 2000, 3000,
                       fade_in_ms=500, fade_out_ms=500, duck_percent=25),
            event_template("sound", "old_bell", 2500, 100),
            self.track("sword", "clang", "sfx", 6000, 200),
        ]

    @staticmethod
    def track(eid, cue, bus, start, duration, **options):
        event = event_template("sound", eid, start, duration)
        event.update(cue=cue, bus=bus, **options)
        return event

    def test_mix_fades_music_ambience_and_ducks_for_voice(self):
        def levels(ms):
            return {t.event_id: t.level for t in mix_at(self.clip, ms)}
        self.assertEqual(levels(0)["score"], 0)
        self.assertEqual(levels(0)["wind"], 0.5)
        self.assertEqual(levels(1000)["score"], 1)
        self.assertAlmostEqual(levels(2250)["score"], 0.625)
        self.assertAlmostEqual(levels(2500)["score"], 0.25)
        self.assertAlmostEqual(levels(5000)["score"], 1)
        self.assertAlmostEqual(levels(9500)["score"], 0.5)
        self.assertNotIn("score", levels(10000))
        self.assertNotIn("old_bell", levels(2500))  # legacy is one-shot
        self.assertEqual(mix_at(self.clip, 5000), mix_at(self.clip, 5000))

    def test_project_schema_rejects_invalid_mix_fields_and_preserves_legacy(self):
        data = {**self.project.to_dict(), "cinematics": [self.clip]}
        self.assertEqual(GameProject.from_dict(data, self.content).cinematics, [self.clip])
        mutations = (
            lambda e: e.update(bus="invalid"),
            lambda e: e.update(volume=True),
            lambda e: e.update(volume=101),
            lambda e: e.update(loop="yes"),
            lambda e: e.update(fade_in_ms=-1),
            lambda e: e.update(fade_out_ms=e["duration_ms"] + 1),
            lambda e: e.update(duck_percent=30),  # not a voice
            lambda e: e.update(unexpected="field"),
        )
        for mutation in mutations:
            with self.subTest(mutation=repr(mutation)), self.assertRaises(RuleError):
                clip = deepcopy(self.clip)
                mutation(clip["events"][0])
                GameProject.from_dict(
                    {**self.project.to_dict(), "cinematics": [clip]},
                    self.content)
        with TemporaryDirectory() as folder:
            p = Path(folder) / "demo.game.json"
            GameProject.from_dict(data, self.content).save(p, self.content)
            self.assertEqual(GameProject.load(p, self.content).cinematics, [self.clip])
        self.assertNotIn("cinematics", self.project.to_dict())

    def test_director_dispatches_once_pause_seek_and_stops(self):
        stage = Mock()
        director = CinematicAudioDirector(self.clip, stage)
        stage.music.assert_called_once_with(None)
        director.advance(0)
        self.assertEqual(stage.play_track.call_count, 2)  # score + wind
        self.assertEqual(stage.set_track_level.call_count, 2)
        director.advance(2500)
        self.assertEqual(stage.cue.call_count, 1)
        stage.cue.assert_called_with("cinematic")
        director.advance(2500)
        self.assertEqual(stage.cue.call_count, 1)
        director.advance(6000)
        self.assertEqual(stage.play_track.call_count, 4)  # 2 + voice + sword; voice ended
        director.pause()
        stage.pause_tracks.assert_called_once()
        director.resume()
        stage.resume_tracks.assert_called_once()
        director.seek(7000)
        self.assertEqual(stage.cue.call_count, 1)
        director.restart()
        self.assertEqual(stage.cue.call_count, 1)
        director.advance(2500)
        self.assertEqual(stage.cue.call_count, 2)
        director.stop()
        self.assertEqual(director._active, set())

    def test_no_audio_device_still_has_deterministic_projection(self):
        director = CinematicAudioDirector(self.clip)
        director.advance(5000)
        director.seek(1500)
        director.pause()
        director.resume()
        director.restart()
        director.stop()
        self.assertEqual(mix_at(self.clip, 2500)[0].bus, "music")


class ChannelAudioTests(unittest.TestCase):
    def test_multi_channel_playback_level_pause_and_close(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "score.wav").write_bytes(b"RIFF" + b"\x00" * 4 + b"WAVE")
            registry = AssetRegistry({"version": 1, "entries": [
                {"id": "score", "kind": "sound", "path": "score.wav"}
            ], "bindings": {"sound": {"cinematic_score": "score"}}})
            stage = AudioStage(registry, root, effects_volume=80, music_volume=60)
            mixer = Mock()
            channels = [Mock(), Mock()]
            mixer.Sound.return_value.play.side_effect = channels
            stage._mixer = mixer
            self.assertTrue(stage.play_track("score", "cinematic_score",
                                             bus="music", loop=True))
            self.assertTrue(stage.play_track("wind", "cinematic_score",
                                             bus="ambience", loop=True))
            self.assertEqual(mixer.Sound.call_count, 1)  # reused cached Sound
            self.assertEqual(mixer.Sound.return_value.play.call_count, 2)
            stage.set_track_level("score", 0.25)
            channels[0].set_volume.assert_called_with(0.15)
            stage.set_track_level("wind", 0.5)
            channels[1].set_volume.assert_called_with(0.30)
            stage.pause_tracks()
            channels[0].pause.assert_called_once()
            stage.resume_tracks()
            channels[1].unpause.assert_called_once()
            stage.stop_track("score")
            channels[0].stop.assert_called_once()
            stage.close()
            channels[1].stop.assert_called_once()
            self.assertEqual(stage._tracks, {})
            self.assertFalse(stage.play_track("x", "no_such_binding"))


if __name__ == "__main__":
    unittest.main()

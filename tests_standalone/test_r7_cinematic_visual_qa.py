"""R7.17: wall-clock, pause/seek and replay correctness without any Tk/audio."""
from unittest.mock import Mock
import unittest

from sporebound.audio_timeline import CinematicAudioDirector
from sporebound.cinematic_transport import CinematicTransport
from sporebound.cinematics import cinematic_template, event_template, frame_at
from sporebound.model import RuleError


class FakeTime:
    def __init__(self):
        self.seconds = 0.

    def __call__(self):
        return self.seconds

    def advance(self, millis):
        self.seconds += millis / 1000.


def demo_clip():
    clip = cinematic_template("r7_scene", "R7 visual QA", "campaign_start", "main")
    clip["duration_ms"] = 3000
    shot = event_template("camera", "camera", 0, 3000)
    shot.update(shot="arrival", transition="dissolve", easing="ease_in_out")
    line = event_template("dialogue", "dialogue", 100, 1800)
    line.update(speaker="Jeanne", text="Nous entrons dans la forteresse",
                portrait="jeanne", expression="determined", chars_per_second=12)
    cue = event_template("sound", "bell", 500, 100)
    cue["cue"] = "bell"
    music = event_template("sound", "score", 0, 3000)
    music.update(cue="theme", bus="music", loop=True, volume=90,
                 volume_to=40, fade_in_ms=300, fade_out_ms=500)
    clip["events"] = [shot, line, cue, music]
    return clip


class MonotonicTransportTests(unittest.TestCase):
    def test_no_40ms_tick_drift_or_rounding_loss(self):
        clock = FakeTime()
        transport = CinematicTransport(3000, monotonic=clock)
        clock.advance(1.2)
        self.assertEqual(transport.read(), 1)
        clock.advance(1.7)
        self.assertEqual(transport.read(), 2)
        clock.advance(397.1)
        self.assertEqual(transport.read(), 400)
        clock.advance(2100)
        self.assertEqual(transport.read(), 2500)
        clock.advance(2000)
        self.assertEqual(transport.read(), 3000)

    def test_pause_resume_seek_restart_and_no_stale_time(self):
        clock = FakeTime()
        transport = CinematicTransport(1500, monotonic=clock)
        clock.advance(600)
        self.assertEqual(transport.pause(), 600)
        clock.advance(7000)
        self.assertEqual(transport.read(), 600)
        self.assertEqual(transport.checkpoint(),
                         {"time_ms": 600, "playing": False})
        transport.resume()
        clock.advance(80)
        self.assertEqual(transport.read(), 680)
        transport.seek(1200)
        clock.advance(100)
        self.assertEqual(transport.read(), 1300)
        transport.restart()
        self.assertEqual(transport.read(), 0)
        clock.advance(100)
        self.assertEqual(transport.read(), 100)
        clock.seconds -= .05
        self.assertEqual(transport.read(), 100)
        clock.advance(200)
        self.assertEqual(transport.read(), 250)

    def test_checkpoints_validation_is_atomic(self):
        clock = FakeTime()
        transport = CinematicTransport(2000, monotonic=clock)
        clock.advance(500)
        saved = transport.checkpoint()
        transport.seek(1500)
        transport.restore(saved)
        self.assertEqual(transport.position_ms, 500)
        for bad in ({"time_ms": True, "playing": False},
                    {"time_ms": 2500, "playing": False},
                    {"time_ms": 100, "playing": 1},
                    {"time_ms": 0}, None):
            with self.subTest(bad=bad), self.assertRaises(RuleError):
                transport.restore(bad)
            self.assertEqual(transport.position_ms, 500)

    def test_clock_audio_video_determinism_across_delayed_frames(self):
        clip = demo_clip()
        clock = FakeTime()
        transport = CinematicTransport(3000, monotonic=clock)
        stage = Mock()
        director = CinematicAudioDirector(clip, stage)
        director.advance(0)
        self.assertEqual(frame_at(clip, 0).dialogue, None)
        clock.advance(730)
        first = transport.read()
        director.advance(first)
        self.assertEqual(first, 730)
        self.assertEqual(frame_at(clip, first), frame_at(clip, 730))
        stage.cue.assert_called_once_with("bell")
        clock.advance(1200)
        director.advance(transport.read())
        self.assertEqual(transport.read(), 1930)
        transport.pause()
        director.pause()
        clock.advance(5000)
        self.assertEqual(transport.read(), 1930)
        transport.seek(300)
        director.seek(300)
        stage.cue.assert_called_once()  # seek cannot play the old bell
        transport.resume()
        director.resume()
        clock.advance(400)
        director.advance(transport.read())
        self.assertEqual(transport.read(), 700)
        self.assertEqual(stage.cue.call_count, 2)  # intentional replay crosses bell
        director.stop()


if __name__ == "__main__":
    unittest.main()

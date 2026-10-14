"""R7.17 real Tk visual gate for portraits, transitions, timing and lifecycle.

Runs under xvfb-run with SPOREBOUND_GUI_SMOKE=1, as other Studio GUI tests.
No project writes and no audio device are required.
"""
import os
import unittest
from unittest.mock import Mock

from sporebound.cinematic_player import CinematicPlayback, draw_frame
from sporebound.cinematics import frame_at
from sporebound.model import RuleError
from tests_standalone.test_r7_cinematic_visual_qa import FakeTime, demo_clip


@unittest.skipUnless(os.environ.get("SPOREBOUND_GUI_SMOKE") == "1",
                     "Needs Tk and a display")
class CinematicVisualGUITests(unittest.TestCase):
    def test_real_tk_portrait_fallback_transitions_scrub_and_interrupt(self):
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
        root.geometry("880x540")
        root.withdraw()
        clock = FakeTime()
        audio = Mock()
        done = Mock()
        clip = demo_clip()
        playback = None
        try:
            playback = CinematicPlayback(root, tk, ttk, clip, done,
                                         audio=audio, clock=clock)
            root.update_idletasks()
            photo = tk.PhotoImage(width=48, height=48, master=root)
            photo.put("#e9a545", to=(0, 0, 48, 48))
            lookup = Mock(side_effect=lambda kind, slot:
                          photo if kind == "portrait" and
                          slot == "jeanne_determined" else None)
            playback.renderer.image = lookup
            playback.seek(500)
            self.assertEqual(playback.time_ms, 500)
            self.assertEqual(frame_at(clip, 500).dialogue_presentation.visible_text,
                             "Nous")
            texts = [playback.canvas.itemcget(item, "text")
                     for item in playback.canvas.find_all()
                     if playback.canvas.type(item) == "text"]
            self.assertIn("Nous", texts)
            self.assertTrue(any(playback.canvas.type(item) == "image"
                                for item in playback.canvas.find_all()))
            lookup.assert_any_call("portrait", "jeanne_determined")
            # The dissolve overlay is present above actors, before dialogue.
            self.assertEqual(frame_at(clip, 500).shot_transition[0], "dissolve")
            playback.seek(800)
            self.assertIsNone(frame_at(clip, 800).shot_transition)
            # Missing expressive portrait falls back to the base asset.
            playback.renderer.image = Mock(side_effect=lambda kind, slot:
                                            photo if (kind, slot) ==
                                            ("portrait", "jeanne") else None)
            playback.seek(900)
            playback.renderer.image.assert_any_call("portrait", "jeanne")
            audio.cue.assert_not_called()  # user scrubbing never plays old SFX
            playback.restart()
            if playback.job is not None:
                root.after_cancel(playback.job)
                playback.job = None
            clock.advance(750)
            playback._tick()
            self.assertEqual(playback.time_ms, 750)
            audio.cue.assert_called_once_with("bell")
            playback.toggle()
            checkpoint = playback.checkpoint()
            self.assertEqual(checkpoint["clip_id"], clip["id"])
            self.assertEqual(checkpoint["playing"], False)
            clock.advance(2100)
            self.assertEqual(playback.transport.read(), 750)
            playback.seek(1200)
            playback.restore(checkpoint)
            self.assertEqual(playback.time_ms, 750)
            self.assertFalse(playback.playing)
            audio.cue.assert_called_once_with("bell")
            with self.assertRaises(RuleError):
                playback.restore({**checkpoint, "clip_id": "other"})
            self.assertEqual(playback.time_ms, 750)
            playback.toggle()
            if playback.job is not None:
                root.after_cancel(playback.job)
                playback.job = None
            clock.advance(2300)
            playback._tick()
            self.assertTrue(playback.closed)
            done.assert_called_once_with()
            playback.skip()
            playback.close()
            done.assert_called_once_with()
            self.assertEqual(audio.cue.call_count, 1)
        finally:
            if playback is not None:
                playback.close()
            root.destroy()

    def test_canvas_render_order_is_stable_at_identical_playhead(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            canvas = tk.Canvas(root, width=800, height=480)
            canvas.pack()
            clip = demo_clip()
            draw_frame(canvas, clip, 420)
            first = [(canvas.type(item), canvas.coords(item),
                      canvas.itemcget(item, "text")
                      if canvas.type(item) == "text" else "")
                     for item in canvas.find_all()]
            draw_frame(canvas, clip, 420)
            second = [(canvas.type(item), canvas.coords(item),
                       canvas.itemcget(item, "text")
                       if canvas.type(item) == "text" else "")
                      for item in canvas.find_all()]
            self.assertEqual(first, second)
            self.assertTrue(first)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()

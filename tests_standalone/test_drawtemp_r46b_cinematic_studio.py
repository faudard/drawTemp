"""R46.B cinematic authoring gates: zoom, trim, revision and Qt projection."""
from copy import deepcopy
import os
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.cinematics import event_template
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from drawtemp.cinematics.document import CinematicDocument
from drawtemp.cinematics.timeline import TimelineScale


class R46BTimelineCoreTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.document = CinematicDocument(GameProject.default(self.content),
                                          self.content)
        self.clip_id = self.document.add_jeanne_intro()

    def test_zoom_does_not_change_source_timestamps_or_scrub_position(self):
        before = self.document.clip(self.clip_id)
        for factor in (.5, 1, 2, 4, 8):
            scale = TimelineScale(before["duration_ms"], width_px=920 * factor)
            for time_ms in (0, 1500, 12000):
                self.assertEqual(scale.seek(scale.time_to_x(time_ms)), time_ms)
            self.assertGreater(scale.major_tick_ms(), 0)
            self.assertLessEqual(scale.major_tick_ms(), 180000)
        self.assertEqual(before, self.document.clip(self.clip_id))

    def test_trim_r11_keyframes_keeps_history_and_source(self):
        self.document.add_keyframe(self.clip_id, "jeanne", 1100)
        original = self.document.clip(self.clip_id)
        actor = next(e for e in original["events"] if e["id"] == "jeanne")
        self.document.trim_event(self.clip_id, "jeanne", 4000,
                                 expected_revision=self.document.revision)
        updated = self.document.clip(self.clip_id)
        new_actor = next(e for e in updated["events"] if e["id"] == "jeanne")
        self.assertEqual(new_actor["duration_ms"], 4000)
        self.assertEqual(new_actor["keyframes"][0]["at_ms"],
                         round(1100 * 4000 / actor["duration_ms"]))
        self.assertTrue(self.document.undo())
        self.assertEqual(self.document.clip(self.clip_id), original)
        self.assertTrue(self.document.redo())
        self.assertEqual(self.document.clip(self.clip_id), updated)

    def test_trim_rejects_audio_fade_boundary_atomically(self):
        before = self.document.clip(self.clip_id)
        revision = self.document.revision
        # The original score has fade_out_ms=2000, cannot fit in 1000 ms.
        with self.assertRaises(RuleError):
            self.document.trim_event(self.clip_id, "musique", 1000)
        self.assertEqual(self.document.clip(self.clip_id), before)
        self.assertEqual(self.document.revision, revision)

    def test_trim_rejects_older_revision_and_clip_overflow(self):
        revision = self.document.revision
        self.document.edit_event(self.clip_id, "jeanne",
                                 {"easing": "ease_out"})
        before = self.document.clip(self.clip_id)
        with self.assertRaises(RuleError):
            self.document.trim_event(self.clip_id, "jeanne", 2000,
                                     expected_revision=revision)
        # Event begins at 700ms, 12000ms duration would overrun the clip.
        with self.assertRaises(RuleError):
            self.document.trim_event(self.clip_id, "jeanne", 12000)
        self.assertEqual(self.document.clip(self.clip_id), before)

    def test_trim_width_bounds_and_near_end_do_not_drop_last_partial_cell(self):
        scale = TimelineScale(12501, width_px=920)
        self.assertEqual(scale.duration_at_width(scale.width_for(3500), 4000),
                         3500)
        self.assertEqual(scale.duration_at_width(-100, 4500), 1)
        self.assertEqual(scale.duration_at_width(100000, 4501), 4501)
        with self.assertRaises(RuleError):
            scale.duration_at_width(100, 0)


@unittest.skipUnless(os.environ.get("DRAWTEMP_QT_GUI_SMOKE") == "1",
                     "Set DRAWTEMP_QT_GUI_SMOKE=1 in a Qt virtual display job")
class R46BQtSmokeTests(unittest.TestCase):
    def test_edit_zoom_trim_voice_and_subtitle_share_same_stage(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QApplication, QMessageBox
        from drawtemp.studio.qt_cinematic import CinematicEditor
        from drawtemp.cinematics.projection import audio_payload, frame_payload

        app = QApplication.instance() or QApplication([])
        content = Content.load(DEFAULT_CONTENT)
        doc = CinematicDocument(GameProject.default(content), content)
        editor = CinematicEditor(doc)
        try:
            editor._jeanne()
            cid = editor.clip_id
            self.assertEqual(cid, "jeanne_intro")
            initial_revision = doc.revision
            editor.zoom_combo.setCurrentIndex(3)  # 400 %
            self.assertEqual(editor.timeline.scale.width_px, 3680)
            self.assertEqual(initial_revision, doc.revision)  # zoom is not an edit
            editor.stage.seek(2700)
            self.assertEqual(editor.stage.bridge.frame,
                             frame_payload(doc.clip(cid), 2700))
            self.assertIn("Une voix", editor.subtitle_preview.text())
            self.assertEqual(editor.timeline.scale.seek(
                editor.timeline.scale.time_to_x(2700)), 2700)

            voice = event_template("sound", "narrator", 2000, 1000)
            voice.update(cue="narrator_voice", bus="voice")
            doc.add_event(cid, voice)
            editor._refresh()
            editor.stage.seek(2700)
            cues = [t["cue"] for t in audio_payload(doc.clip(cid), 2700)
                    if t["bus"] == "voice"]
            self.assertEqual(cues, ["narrator_voice"])
            self.assertIn("narrator_voice", editor.voice_preview.text())
            revision = doc.revision
            editor._commit_event_trim(cid, "jeanne", 6000, revision)
            actor = next(e for e in doc.clip(cid)["events"]
                         if e["id"] == "jeanne")
            self.assertEqual(actor["duration_ms"], 6000)
            self.assertTrue(doc.undo())
            self.assertEqual(next(e for e in doc.clip(cid)["events"]
                                  if e["id"] == "jeanne")["duration_ms"], 8700)
        finally:
            with patch.object(QMessageBox, "question",
                              return_value=QMessageBox.Yes):
                editor.close()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()

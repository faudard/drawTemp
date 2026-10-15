"""R11.10: direct timeline editing, deterministic snap and transaction gates."""
from copy import deepcopy
import os
from unittest import TestCase, skipUnless
from unittest.mock import patch

from drawtemp.cinematics.document import CinematicDocument
from drawtemp.cinematics.timeline import TimelineScale
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError


class TimelineScaleTests(TestCase):
    def test_time_pixel_roundtrip_and_seek(self):
        scale = TimelineScale(12000)
        for ms in (0, 1000, 3500, 8500, 12000):
            self.assertEqual(scale.x_to_time(scale.time_to_x(ms)), ms)
        self.assertEqual(scale.seek(-100), 0)
        self.assertEqual(scale.seek(15000), 12000)
        self.assertAlmostEqual(scale.width_for(3000), 230)

    def test_snap_and_clip_bounds(self):
        scale = TimelineScale(12000)
        self.assertEqual(scale.absolute(scale.time_to_x(3549), 2000), 3500)
        self.assertEqual(scale.absolute(scale.time_to_x(3551), 2000), 3600)
        self.assertEqual(scale.absolute(scale.time_to_x(-800), 2000), 0)
        self.assertEqual(scale.absolute(scale.time_to_x(12000), 3500), 8500)
        self.assertEqual(scale.local_key(scale.time_to_x(1900), 700, 8700), 1200)
        self.assertEqual(scale.local_key(scale.time_to_x(800), 700, 8700), 100)
        self.assertEqual(scale.local_key(scale.time_to_x(0), 700, 8700), 1)
        self.assertEqual(scale.local_key(scale.time_to_x(99999), 700, 8700), 8699)

    def test_short_legacy_clip_and_strict_constraints(self):
        scale = TimelineScale(500)
        self.assertEqual(scale.absolute(scale.time_to_x(500), 500), 0)
        self.assertEqual(scale.local_key(scale.time_to_x(250), 0, 200), 199)
        with self.assertRaises(RuleError):
            scale.absolute(130, 501)
        with self.assertRaises(RuleError):
            scale.local_key(130, 0, 1)


class TimelineDocumentTests(TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.doc = CinematicDocument(GameProject.default(self.content), self.content)
        self.cid = self.doc.add_jeanne_intro()

    def test_event_move_one_revision_one_undo_and_full_roundtrip(self):
        old = self.doc.clip(self.cid)
        rev = self.doc.revision
        self.doc.edit_event(self.cid, "appel", {"start_ms": 2500},
                            expected_revision=rev)
        new = self.doc.clip(self.cid)
        self.assertEqual(next(e for e in new["events"] if e["id"] == "appel")["start_ms"], 2500)
        self.assertEqual(self.doc.revision, rev + 1)
        with self.assertRaises(RuleError):
            self.doc.edit_event(self.cid, "appel", {"start_ms": 2600},
                                expected_revision=rev)
        self.assertEqual(self.doc.clip(self.cid), new)
        self.assertTrue(self.doc.undo())
        self.assertEqual(self.doc.clip(self.cid), old)
        self.assertTrue(self.doc.redo())
        self.assertEqual(self.doc.clip(self.cid), new)
        restored = GameProject.from_dict(self.doc.project.to_dict(), self.content)
        self.assertEqual(restored.cinematics[0], new)

    def test_keyframe_retime_collision_rolls_back_without_history(self):
        self.doc.add_keyframe(self.cid, "jeanne", 1000)
        self.doc.add_keyframe(self.cid, "jeanne", 2000)
        before = self.doc.clip(self.cid)
        revision = self.doc.revision
        with self.assertRaises(RuleError):
            self.doc.update_keyframe(self.cid, "jeanne", 1000,
                                     at_ms=2000, expected_revision=revision)
        self.assertEqual(self.doc.clip(self.cid), before)
        self.assertEqual(self.doc.revision, revision)
        with self.assertRaises(RuleError):
            self.doc.update_keyframe(self.cid, "jeanne", 1000,
                                     at_ms=1500, expected_revision=revision-1)
        self.assertEqual(self.doc.revision, revision)
        self.doc.update_keyframe(self.cid, "jeanne", 1000,
                                 at_ms=1500, expected_revision=revision)
        self.assertEqual(self.doc.revision, revision+1)
        self.assertTrue(self.doc.undo())
        self.assertEqual(self.doc.clip(self.cid), before)


@skipUnless(os.environ.get("DRAWTEMP_QT_GUI_SMOKE") == "1",
            "Qt UI smoke requires a display and PySide6")
class TimelineQtSmokeTests(TestCase):
    def test_handles_select_move_and_seek_with_one_transaction(self):
        from PySide6.QtWidgets import QApplication, QMessageBox, QGraphicsItem
        from drawtemp.studio.cinematic_timeline import TimelineBlock, TimelineKeyframe
        from drawtemp.studio.qt_cinematic import CinematicEditor
        app = QApplication.instance() or QApplication([])
        content = Content.load(DEFAULT_CONTENT)
        doc = CinematicDocument(GameProject.default(content), content)
        cid = doc.add_jeanne_intro()
        doc.add_keyframe(cid, "jeanne", 1000)
        editor = CinematicEditor(doc)
        try:
            editor.show()
            app.processEvents()
            blocks = [i for i in editor.timeline_scene.items()
                      if isinstance(i, TimelineBlock)]
            keys = [i for i in editor.timeline_scene.items()
                    if isinstance(i, TimelineKeyframe)]
            self.assertTrue(blocks)
            self.assertEqual(len(keys), 1)
            block = next(i for i in blocks if i.event_id == "appel")
            self.assertTrue(block.flags() & QGraphicsItem.ItemIsMovable)
            self.assertTrue(keys[0].flags() & QGraphicsItem.ItemIsMovable)
            revision = doc.revision
            editor._commit_event_drag(cid, "appel", 2600, revision)
            self.assertEqual(doc.revision, revision + 1)
            self.assertEqual(editor.stage.time_ms, 2600)
            self.assertEqual(next(e for e in doc.clip(cid)["events"]
                                  if e["id"] == "appel")["start_ms"], 2600)
            revision = doc.revision
            editor._commit_key_drag(cid, "jeanne", 1000, 1300, revision)
            self.assertEqual(doc.revision, revision + 1)
            self.assertEqual(next(e for e in doc.clip(cid)["events"]
                                  if e["id"] == "jeanne")["keyframes"][0]["at_ms"], 1300)
            editor._scrub_timeline(1750)
            self.assertEqual(editor.stage.time_ms, 1750)
            self.assertFalse(editor.stage.playing)
            editor._undo()
            self.assertEqual(next(e for e in doc.clip(cid)["events"]
                                  if e["id"] == "jeanne")["keyframes"][0]["at_ms"], 1000)
        finally:
            with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
                editor.close()
            app.processEvents()

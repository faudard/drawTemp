"""R11: schema, authoring atomicity, player parity, FX and project round-trip."""
from copy import deepcopy
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.cinematics import event_template, frame_at
from drawtemp.cinematics import CinematicDocument, frame_payload, audio_payload


class R11DocumentTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.doc = CinematicDocument(self.project, self.content)
        self.cid = self.doc.add_jeanne_intro()

    def test_jeanne_intro_has_real_multitrack_player_state(self):
        clip = self.doc.clip(self.cid)
        kinds = {e["kind"] for e in clip["events"]}
        self.assertTrue({"background", "actor", "camera", "dialogue",
                         "sound", "fade"} <= kinds)
        self.assertEqual({e.get("bus") for e in clip["events"]
                          if e["kind"] == "sound"}, {"music", "ambience"})
        self.doc.project.validate(self.content)
        for time_ms in (0, 1400, 2700, 7800, 10500, 11999):
            frame, audio = self.doc.sample(self.cid, time_ms)
            self.assertEqual(frame, frame_at(clip, time_ms))
            self.assertEqual(frame_payload(clip, time_ms),
                             frame_payload(deepcopy(clip), time_ms))
            self.assertEqual(audio_payload(clip, time_ms),
                             audio_payload(deepcopy(clip), time_ms))
        self.assertEqual(frame_payload(clip, 2700)["speaker"], "Une voix")

    def test_mutations_validate_atomically_and_reject_stale_preview(self):
        before = self.doc.clip(self.cid)
        revision = self.doc.revision
        with self.assertRaises(RuleError):
            self.doc.edit_event(self.cid, "approche",
                                {"duration_ms": 13000})
        self.assertEqual(self.doc.clip(self.cid), before)
        self.assertEqual(self.doc.revision, revision)
        self.doc.add_event(self.cid, event_template("fx", "fire", 1000, 4000))
        revision = self.doc.revision
        with self.assertRaises(RuleError):
            self.doc.add_clip(before, expected_revision=revision - 1)
        self.assertEqual(self.doc.revision, revision)
        self.assertEqual(self.doc.clip(self.cid)["events"][-1]["kind"], "fx")

    def test_keyframe_and_undo_redo_preserve_canonical_project(self):
        original = self.doc.project.to_dict()
        self.doc.add_keyframe(self.cid, "jeanne", 1100)
        self.doc.update_keyframe(self.cid, "jeanne", 1100,
                                 at_ms=1200, pos=[.30, .62])
        self.assertEqual(self.doc.clip(self.cid)["events"][2]["keyframes"][0]["at_ms"], 1200)
        self.assertTrue(self.doc.undo())
        self.assertEqual(self.doc.clip(self.cid)["events"][2]["keyframes"][0]["at_ms"], 1100)
        self.assertTrue(self.doc.redo())
        self.assertEqual(self.doc.clip(self.cid)["events"][2]["keyframes"][0]["at_ms"], 1200)
        self.assertEqual(self.project.to_dict(), original if not self.project.cinematics else
                         self.project.to_dict())  # never mutates the input project

    def test_fx_schema_seed_strict_and_seek_determinism(self):
        fx = event_template("fx", "smoke", 1000, 4000)
        fx["effect"] = "smoke"
        fx["seed"] = 42
        self.doc.add_event(self.cid, fx)
        clip = self.doc.clip(self.cid)
        result = frame_payload(clip, 1200)
        self.assertEqual(result["effects"][0]["seed"], 42)
        self.assertEqual(result, frame_payload(clip, 1200))
        self.assertEqual(frame_payload(clip, 6000)["effects"], [])
        bad = deepcopy(clip)
        bad["events"][-1]["seed"] = -1
        with self.assertRaises(RuleError):
            self.doc.edit_event(self.cid, "smoke", {"seed": -1})
        with self.assertRaises(RuleError):
            self.doc.edit_event(self.cid, "smoke", {"intensity": True})

    def test_manifest_roundtrip_and_stale_disk_guard(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "jeanne.game.json"
            self.doc.save(path)
            restored = GameProject.load(path, self.content)
            self.assertEqual(restored.cinematics, self.doc.clips)
            self.assertFalse(self.doc.dirty)
            self.doc.edit_event(self.cid, "appel", {"text": "Un autre avenir."})
            self.assertTrue(self.doc.dirty)
            path.write_text(path.read_text(encoding="utf8") + "\n", encoding="utf8")
            with self.assertRaises(RuleError):
                self.doc.save()
            self.assertTrue(self.doc.dirty)

    def test_cannot_author_duplicate_ids_or_overflow(self):
        with self.assertRaises(RuleError):
            self.doc.add_event(self.cid, event_template("actor", "jeanne", 0, 1000))
        before = self.doc.clip(self.cid)
        with self.assertRaises(RuleError):
            self.doc.add_event(self.cid, event_template("fx", "beyond", 11900, 2000))
        self.assertEqual(self.doc.clip(self.cid), before)


@unittest.skipUnless(os.environ.get("DRAWTEMP_QT_GUI_SMOKE") == "1",
                     "Set DRAWTEMP_QT_GUI_SMOKE=1 in a Qt/virtual-display job")
class R11QtSmokeTests(unittest.TestCase):
    def test_shared_scene_player_and_studio(self):
        from PySide6.QtWidgets import QApplication
        from drawtemp.player.qt_cinematic import CinematicStage
        from drawtemp.studio.qt_cinematic import CinematicEditor
        from drawtemp.render import __file__ as render_package
        from PySide6.QtQuickWidgets import QQuickWidget
        app = QApplication.instance() or QApplication([])
        content = Content.load(DEFAULT_CONTENT)
        doc = CinematicDocument(GameProject.default(content), content)
        cid = doc.add_jeanne_intro()
        stage = CinematicStage(doc.clip(cid))
        self.assertIsInstance(stage.view, QQuickWidget)
        self.assertIsNotNone(stage.view.rootObject())
        frame0 = stage.bridge.frame
        stage.seek(2700)
        self.assertEqual(stage.bridge.frame, frame_payload(doc.clip(cid), 2700))
        stage.pause()
        editor = CinematicEditor(doc)
        self.assertEqual(editor.stage.bridge.frame, frame0)
        self.assertIsNotNone(editor.stage.view.rootObject())
        editor.close()
        stage.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()

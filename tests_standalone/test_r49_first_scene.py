"""R49.C2: first narrative scene + tactical message action across R1 and Qt."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r49_first_scene import (
    FirstSceneError, FirstSceneRequest, apply_first_scene,
    preview_first_scene, validate_first_scene,
)
from drawtemp.studio.genre_workflow import create_genre_project
from drawtemp.export.r15 import preflight
from drawtemp.studio.workspace_model import resources


def new_session():
    return AuthoringSession.new(*reference_project())


def first_request(session, *, event_id="r49_welcome", scene_id="r49_intro",
                  tick=3):
    mid = session.snapshot().to_dict()["content"]["missions"][0]["id"]
    return FirstSceneRequest(
        mission_id=mid, event_id=event_id, scene_id=scene_id,
        title="Première scène", speaker="Narrateur",
        dialogue="La quête commence.", action_message="Le signal retentit.",
        tick=tick,
    )


class FirstSceneContractTests(unittest.TestCase):
    def test_preview_is_nonmutating_and_apply_one_undo_step(self):
        editor = new_session()
        before = editor.snapshot().to_dict()
        request = first_request(editor)
        plan = preview_first_scene(editor, request, expected_revision=0)
        self.assertEqual(editor.snapshot().to_dict(), before)
        self.assertEqual(editor.revision, 0)
        transition = editor.apply(plan)
        self.assertEqual(transition.snapshot.revision, 1)
        state = editor.snapshot().to_dict()
        mission = next(m for m in state["content"]["missions"]
                       if m["id"] == request.mission_id)
        event = next(e for e in mission["triggers"]
                     if e["id"] == request.event_id)
        self.assertEqual(event["condition"], "tick")
        self.assertEqual(event["value"], 3)
        self.assertEqual(event["actions"],
                         [{"kind": "message", "text": request.action_message}])
        scene = next(s for s in state["project"]["story"]["scenes"]
                     if s["id"] == request.scene_id)
        self.assertEqual(scene["text"], request.dialogue)
        self.assertEqual(scene["speaker"], request.speaker)
        self.assertEqual(
            state["project"]["story"]["during_tactical_event"][
                request.mission_id + "/" + request.event_id],
            request.scene_id)
        editor.undo()
        self.assertEqual(editor.snapshot().to_dict(), before)
        editor.redo()
        self.assertEqual(editor.snapshot().to_dict(), state)

    def test_duplicates_and_stale_revision_never_commit(self):
        editor = new_session()
        request = first_request(editor)
        apply_first_scene(editor, request)
        after = editor.snapshot().to_dict()
        for update in (
            request,
            FirstSceneRequest(**{**request.__dict__,
                                 "event_id": "brand_new_event"}),
            FirstSceneRequest(**{**request.__dict__,
                                 "scene_id": "brand_new_scene"}),
        ):
            with self.subTest(update=update), self.assertRaises(
                    (FirstSceneError, AuthoringError)):
                apply_first_scene(editor, update)
            self.assertEqual(editor.snapshot().to_dict(), after)
        with self.assertRaises(FirstSceneError):
            preview_first_scene(editor, first_request(
                editor, event_id="new_event", scene_id="new_scene"),
                expected_revision=0)
        editor2 = new_session()
        staged = preview_first_scene(editor2, first_request(editor2))
        apply_first_scene(editor2, first_request(
            editor2, event_id="other_event", scene_id="other_scene"))
        with self.assertRaises(AuthoringError):
            editor2.apply(staged)

    def test_rejects_invalid_ids_ticks_text_and_missions(self):
        editor = new_session()
        baseline = editor.snapshot().to_dict()
        request = first_request(editor)
        edits = (
            {"mission_id": "unknown_mission"},
            {"event_id": "../escape"},
            {"scene_id": ""},
            {"scene_id": "1not_valid"},
            {"tick": True},
            {"tick": 0},
            {"tick": 100001},
            {"title": " "},
            {"dialogue": ""},
            {"action_message": " "},
            {"speaker": ""},
            {"dialogue": "x" * 2001},
        )
        for edit in edits:
            with self.subTest(edit=edit), self.assertRaises(FirstSceneError):
                validate_first_scene(editor.snapshot(),
                                     FirstSceneRequest(**{**request.__dict__, **edit}))
        self.assertEqual(editor.snapshot().to_dict(), baseline)

    def test_disk_roundtrip_and_preflight_without_json_edits(self):
        with TemporaryDirectory() as temp:
            path = create_genre_project("srpg", Path(temp) / "project") / "game.json"
            session = AuthoringSession.open(path)
            request = first_request(session)
            apply_first_scene(session, request)
            state = session.snapshot().to_dict()
            session.save()
            reopened = AuthoringSession.open(path)
            self.assertEqual(reopened.snapshot().to_dict(), state)
            checked = preflight(path)
            self.assertTrue(checked["passed"], checked["errors"])

    def test_r49c1_evidence_now_includes_a_real_scene_and_action(self):
        from drawtemp.quality.r49_creator_gate import run_creator_slice
        with TemporaryDirectory() as temp:
            report = run_creator_slice(Path(temp) / "evidence",
                                       revision="a" * 40)
            self.assertTrue(report["creator"]["checks"]["r9_scene_trigger_action"])
            self.assertFalse(report["creator"]["checks"]["qt_gui_author_journey"])
            self.assertFalse(report["creator"]["checks"]["real_gameplay_action"])
            self.assertEqual(report["gate"]["status"], "NO_GO")
            self.assertGreater(report["creator"]["resource_counts"]["scenes"], 0)


@unittest.skipUnless(importlib.util.find_spec("PySide6"),
                     "PySide6 not installed")
class FirstSceneQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def create_window(self, folder):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        session = new_session()
        settings = QSettings(str(Path(folder) / "r49c2.ini"),
                             QSettings.IniFormat)
        window = StudioWindow(session, settings=settings)
        window.show()
        self.app.processEvents()
        return window

    def close_window(self, window):
        with patch.object(window, "_confirm_leave", return_value=True):
            window.close()
        window.deleteLater()
        self.app.processEvents()

    def test_click_through_preview_apply_undo_and_report(self):
        with TemporaryDirectory() as temp:
            window = self.create_window(temp)
            try:
                with patch.object(window, "playtest", return_value=False) as play, \
                        patch.object(window, "export_player", return_value=False) as export:
                    window.navigate("events")
                    panel = window._models["events"].first_scene
                    self.assertEqual(panel.objectName(), "r49c2-first-scene")
                    # Both UI buttons use Studio's existing commands.
                    # Signals are connected during workspace construction.
                    # The fake callbacks must never spawn a Player or export.
                    panel.playtestRequested.emit()
                    panel.exportRequested.emit()
                    play.assert_called_once_with()
                    export.assert_called_once_with()
                
                self.assertFalse(panel.apply_button.isEnabled())
                previous = window.session.snapshot().to_dict()
                panel.event_id.setText("r49_ui_event")
                panel.scene_id.setText("r49_ui_scene")
                self.assertTrue(panel.preview_changes(), panel.report.toPlainText())
                self.assertEqual(window.session.snapshot().to_dict(), previous)
                self.assertTrue(panel.apply_button.isEnabled())
                self.assertTrue(panel.apply_changes(), panel.report.toPlainText())
                self.assertEqual(window.session.revision, 1)
                self.assertTrue(panel.play_button.isEnabled())
                self.assertTrue(panel.export_button.isEnabled())
                snapshot = window.session.snapshot().to_dict()
                self.assertIn("r49_ui_scene",
                              [s["id"] for s in snapshot["project"]["story"]["scenes"]])
                window.session.undo()
                window.refresh()
                self.assertEqual(window.session.snapshot().to_dict(), previous)
            finally:
                self.close_window(window)

    def test_invalid_field_keeps_document_clean_and_disables_apply(self):
        with TemporaryDirectory() as temp:
            window = self.create_window(temp)
            try:
                window.navigate("events")
                panel = window._models["events"].first_scene
                original = window.session.snapshot().to_dict()
                panel.event_id.setText("../broken")
                self.assertFalse(panel.preview_changes())
                self.assertFalse(panel.apply_button.isEnabled())
                self.assertIn("identifiant", panel.report.toPlainText())
                self.assertEqual(window.session.snapshot().to_dict(), original)
            finally:
                self.close_window(window)


if __name__ == "__main__":
    unittest.main()

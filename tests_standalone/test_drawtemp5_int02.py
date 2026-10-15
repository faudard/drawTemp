"""INT-02: R11 Cinematic Studio owns no copy of shared authoring documents.

Headless, cross-workspace regression gate. The Qt smoke covers the button path.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.cinematics import CinematicDocument
from drawtemp.core import Content, GameProject
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from drawtemp.studio.map_authoring import MapStudio
from sporebound.cinematics import event_template
from sporebound.event_composer import action, condition
from sporebound.model import RuleError


class SharedCinematicDocumentTests(unittest.TestCase):
    def setUp(self):
        self.session = AuthoringSession.new(*reference_project())
        self.map = MapStudio(self.session, MISSION)
        self.events = EventStudio(self.session)
        self.cinematic = CinematicDocument.from_session(self.session)

    def test_one_history_across_map_cinematic_and_event_workspaces(self):
        self.map.paint([(3, 3)], "surface:stone")
        map_state = self.session.snapshot().to_dict()
        clip_id = self.cinematic.add_jeanne_intro()
        cinematic_state = self.session.snapshot().to_dict()
        self.assertEqual(clip_id, "jeanne_intro")
        self.events.create(
            MISSION, "int02_lever",
            condition("interact", object_id="lever"),
            [action("message", text="Le passage est ouvert")],
        )
        final = self.session.snapshot().to_dict()
        self.assertEqual(self.cinematic.revision, self.session.revision)

        # Undo in R11 traverses the actual R9 and R11 history entries.
        self.assertTrue(self.cinematic.undo())
        self.assertEqual(self.session.snapshot().to_dict()["project"],
                         cinematic_state["project"])
        self.assertTrue(self.cinematic.undo())
        self.assertEqual(self.session.snapshot().to_dict()["project"],
                         map_state["project"])
        self.assertTrue(self.cinematic.redo())
        self.assertTrue(self.cinematic.redo())
        self.assertEqual(self.session.snapshot().to_dict()["content"], final["content"])
        self.assertEqual(self.session.snapshot().to_dict()["project"], final["project"])

    def test_live_project_never_clobbers_other_workspace_and_reads_new_content(self):
        clip_id = self.cinematic.add_jeanne_intro()
        self.map.paint([(3, 3)], "surface:stone")
        self.session.apply(self.session.preview_project(
            lambda project: {**project, "title": "Updated by another workspace"},
            kind="int02.external-title"))
        self.cinematic.edit_event(clip_id, "appel", {"text": "Debout, Jeanne !"})
        snapshot = self.session.snapshot().to_dict()
        self.assertEqual(snapshot["project"]["title"], "Updated by another workspace")
        self.assertEqual(self.cinematic.project.title, "Updated by another workspace")
        self.assertEqual(self.cinematic.clip(clip_id)["events"][3]["text"],
                         "Debout, Jeanne !")
        self.assertEqual(snapshot["content"]["missions"][0]["id"], MISSION)
        self.assertEqual(self.cinematic.clips, snapshot["project"]["cinematics"])

    def test_invalid_edit_and_stale_cross_workspace_plan_are_fail_closed(self):
        clip_id = self.cinematic.add_jeanne_intro()
        before = self.session.snapshot()
        with self.assertRaises(AuthoringError) as rejected:
            self.cinematic.add_event(
                clip_id, event_template("actor", "jeanne", 0, 1000))
        self.assertEqual(rejected.exception.code, "invalid_edit")
        self.assertEqual(self.session.snapshot(), before)

        stale_plan = self.session.preview_project(
            lambda project: {**project, "title": "Obsolete"},
            kind="int02.stale-preview")
        old_revision = self.cinematic.revision
        self.map.paint([(3, 3)], "surface:stone")
        with self.assertRaises(AuthoringError) as rejected:
            self.session.apply(stale_plan)
        self.assertEqual(rejected.exception.code, "stale_revision")
        with self.assertRaises(RuleError):
            self.cinematic.add_clip(
                self.cinematic.clip(clip_id), expected_revision=old_revision)
        self.assertNotEqual(self.session.snapshot().project["title"], "Obsolete")

    def test_two_document_save_reopen_and_external_change_guard(self):
        self.map.paint([(3, 3)], "surface:stone")
        clip_id = self.cinematic.add_jeanne_intro()
        with TemporaryDirectory() as directory:
            content_path = Path(directory) / "int02.json"
            saved = self.cinematic.save(content_path)
            project_path = content_path.with_suffix(".game.json")
            self.assertEqual(tuple(saved), (content_path, project_path))
            self.assertTrue(content_path.is_file())
            self.assertTrue(project_path.is_file())
            self.assertFalse(self.cinematic.dirty)

            self.cinematic.edit_event(clip_id, "appel", {"text": "En route !"})
            self.cinematic.save()
            reopened = AuthoringSession.open(content_path)
            current = reopened.snapshot().to_dict()
            content = Content.from_dict(current["content"])
            project = GameProject.from_dict(current["project"], content)
            self.assertEqual(CinematicDocument.from_session(reopened).clip(
                clip_id)["events"][3]["text"], "En route !")
            self.assertEqual(project.cinematics[0]["id"], clip_id)

            # A mismatched disk pair must never be replaced by the R11 editor.
            previous_file = content_path.read_bytes() + b" "
            content_path.write_bytes(previous_file)
            self.cinematic.edit_clip(clip_id, {"name": "Changed again"})
            with self.assertRaises(AuthoringError) as rejected:
                self.cinematic.save()
            self.assertEqual(rejected.exception.code, "save_failed")
            self.assertEqual(content_path.read_bytes(), previous_file)
            self.assertTrue(self.cinematic.dirty)

    def test_bound_document_rejects_project_only_save_destination(self):
        self.cinematic.add_jeanne_intro()
        with TemporaryDirectory() as directory:
            project_path = Path(directory) / "int02.game.json"
            with self.assertRaises(RuleError):
                self.cinematic.save(project_path)
            self.assertFalse(project_path.exists())


if __name__ == "__main__":
    unittest.main()

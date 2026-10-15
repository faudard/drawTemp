"""R9 canonical Event & Narrative Studio regression and contract checks."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from sporebound.event_composer import action, condition


class EventStudioR9Tests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)
        self.studio = EventStudio(self.session)

    def test_create_edit_undo_redo_and_replayable_preview(self):
        before = self.studio.documents()
        self.studio.create(MISSION, "lever_r9",
                           condition("interact", object_id="lever"),
                           [action("message", text="Jeanne ouvre la porte")])
        self.assertEqual(self.studio.event(MISSION, "lever_r9")["actions"][0]["text"],
                         "Jeanne ouvre la porte")
        self.assertTrue(any(marker["event_id"] == "lever_r9"
                            for marker in self.studio.map_markers(MISSION)))
        preview = self.studio.preview(MISSION, "lever_r9")
        self.assertTrue(preview["report"]["isolated"])
        self.assertEqual(preview["report"]["outcome"], "applied")
        self.assertTrue(any(node["event_id"] == "lever_r9"
                            for node in self.studio.graph(MISSION)["nodes"]))
        self.assertEqual(before["content"]["missions"][0]["triggers"],
                         self.studio.events(MISSION)[:-1])
        self.studio.undo()
        self.assertEqual(self.studio.documents()["content"], before["content"])
        self.studio.redo()
        self.assertEqual(self.studio.event(MISSION, "lever_r9")["condition"],
                         "interact")

    def test_predicates_order_schedule_link_and_graph(self):
        self.studio.create(MISSION, "first_r9", condition("tick", tick=0),
                           [action("message", text="Départ")])
        self.studio.create(MISSION, "second_r9", condition("tick", tick=0),
                           [action("message", text="Arrivée")])
        self.studio.add_predicate(MISSION, "second_r9",
                                  condition("tick", tick=0), join="all")
        self.studio.add_predicate(MISSION, "second_r9",
                                  condition("tick", tick=99), join="any",
                                  negate=True)
        self.studio.link(MISSION, "second_r9", "first_r9")
        self.studio.schedule(MISSION, "second_r9", delay_ticks=1,
                             expire_after_ticks=10)
        self.studio.add_action(MISSION, "second_r9",
                               action("message", text="Suivant"))
        self.studio.move_action(MISSION, "second_r9", 1, -1)
        event = self.studio.event(MISSION, "second_r9")
        self.assertEqual([a["text"] for a in event["actions"]],
                         ["Suivant", "Arrivée"])
        self.assertEqual(event["after"], ["first_r9"])
        self.assertEqual(event["delay_ticks"], 1)
        self.assertEqual(event["expire_after_ticks"], 10)
        self.assertEqual(event["when"]["any"][1]["not"]["value"], 99)
        graph = self.studio.graph(MISSION)
        self.assertTrue(any(edge["label"] == "après événement"
                            for edge in graph["edges"]))
        self.assertFalse(self.studio.diagnostics(MISSION))

    def test_unknown_event_action_and_cyclic_link_are_atomic(self):
        self.studio.create(MISSION, "a_r9", condition("tick", tick=0),
                           [action("message", text="A")])
        self.studio.create(MISSION, "b_r9", condition("tick", tick=0),
                           [action("message", text="B")])
        self.studio.link(MISSION, "b_r9", "a_r9")
        unchanged = self.studio.documents()
        revision = self.session.revision
        with self.assertRaises(AuthoringError):
            self.studio.link(MISSION, "a_r9", "b_r9")
        with self.assertRaises(AuthoringError):
            self.studio.add_action(MISSION, "a_r9", {"kind": "unknown"})
        with self.assertRaises(AuthoringError):
            self.studio.delete(MISSION, "a_r9")
        self.assertEqual(self.studio.documents(), unchanged)
        self.assertEqual(self.session.revision, revision)

    def test_story_binding_two_document_save_recovery(self):
        self.studio.create(MISSION, "story_r9", condition("tick", tick=0),
                           [action("message", text="Histoire")])
        self.studio.create_scene(MISSION, "r9_scene", "Un départ",
                                 "Jeanne avance", speaker="Jeanne")
        self.studio.bind_scene(MISSION, "story_r9", "r9_scene")
        self.assertEqual(self.studio.inspect(MISSION, "story_r9")["tactical_scene_id"],
                         "r9_scene")
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "r9.json")
            self.studio.save_as(path)
            self.assertTrue(os.path.exists(path))
            self.assertTrue(os.path.exists(os.path.join(directory, "r9.game.json")))
            reopened = EventStudio(AuthoringSession.open(path))
            self.assertEqual(reopened.inspect(MISSION, "story_r9")["tactical_scene_id"],
                             "r9_scene")
            self.assertFalse(reopened.session.snapshot().dirty)

    def test_debugger_is_isolated_and_does_not_claim_replay_certificate(self):
        self.studio.create(MISSION, "debug_r9", condition("tick", tick=0),
                           [action("message", text="Départ")])
        before = self.studio.documents()
        result = self.studio.debugger(MISSION, "debug_r9")
        self.assertTrue(result["report"]["isolated"])
        self.assertIsNone(result["report"]["replay_verified"])
        self.assertIn("debug_r9", result["report"]["fired_ids"])
        self.assertEqual(self.studio.documents(), before)

    def test_reference_lever_gate_cinematic_undo_in_one_step(self):
        before = self.studio.documents()
        self.studio.gate_wizard(
            MISSION, door_id="gate", lever_id="lever", lever_cell=[2, 4],
            event_id="gate_cinematic_r9", danger_cell=[1, 3],
            dialogue="La porte est ouverte !", cinematic_id="r9_intro")
        self.assertIn("gate_cinematic_r9",
                      [e["id"] for e in self.studio.events(MISSION)])
        self.assertEqual(self.studio.documents()["project"]["cinematics"][-1]["id"],
                         "r9_intro")
        self.studio.undo()
        self.assertEqual(self.studio.documents()["content"], before["content"])
        self.assertEqual(self.studio.documents()["project"], before["project"])


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Optional Qt 6 dependency not installed")
class EventStudioQtSmoke(unittest.TestCase):
    def test_offscreen_workspace_boot(self):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        result = subprocess.run(
            [sys.executable, "-m", "drawtemp.studio.event_studio", "--smoke"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

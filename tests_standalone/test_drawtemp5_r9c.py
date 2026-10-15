"""R9.C regression: action contracts, cinematic hooks and shared ISO markers."""
from copy import deepcopy
import importlib.util
import json
import os
import subprocess
import sys
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from drawtemp.studio.event_command_catalog import action_catalogue, tactical_action
from drawtemp.render.event_overlay import project_event_markers
from drawtemp.render.iso_scene import IsoProjection
from sporebound.event_composer import condition, action
from sporebound.model import RuleError


class R9CCanonicalCommands(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.studio = EventStudio(AuthoringSession.new(content, project))

    def test_all_registered_tactical_action_kinds_are_exposed(self):
        self.assertEqual(
            set(action_catalogue()),
            {"message", "hazard", "status", "despawn",
             "spawn", "wave", "queue_wave"})
        cases = {
            "message": {"text": "La porte s'ouvre"},
            "hazard": {"pos": "1,3", "amount": "8"},
            "status": {"unit": "jeanne", "status": "haste", "duration": 3},
            "despawn": {"unit": "wolf"},
            "spawn": {"actor_id": "new_wolf", "archetype": "wolf",
                      "name": "Loup", "team": "enemy", "pos": "1,3"},
            "wave": {"actor_id": "new_wolf", "archetype": "wolf",
                     "name": "Loup", "team": "enemy", "pos": "1,3",
                     "max_active": 10},
            "queue_wave": {"actor_id": "new_wolf", "archetype": "wolf",
                           "name": "Loup", "team": "enemy", "pos": "1,3"},
        }
        for kind, fields in cases.items():
            with self.subTest(kind=kind):
                row = tactical_action(kind, fields)
                self.assertEqual(row["kind"], kind)
                json.dumps(row)
        self.assertEqual(tactical_action("wave", cases["wave"])["max_active"], 10)
        with self.assertRaises((RuleError, ValueError)):
            tactical_action("script", {"code": "exec('something')"})
        with self.assertRaises((RuleError, ValueError)):
            tactical_action("hazard", {"pos": "1,2", "amount": "not_int"})

    def test_action_order_undo_and_authoring_validation(self):
        self.studio.create(MISSION, "r9c_event", condition("tick", tick=0),
                           [action("message", text="Début")])
        self.studio.add_tactical_command(
            MISSION, "r9c_event", "hazard", {"pos": "1,3", "amount": 7})
        self.assertEqual(self.studio.event(MISSION, "r9c_event")["actions"][1],
                         {"kind": "hazard", "pos": [1, 3], "amount": 7})
        self.studio.move_action(MISSION, "r9c_event", 1, -1)
        self.assertEqual(self.studio.event(MISSION, "r9c_event")["actions"][0]["kind"],
                         "hazard")
        self.studio.undo()
        self.assertEqual(self.studio.event(MISSION, "r9c_event")["actions"][0]["kind"],
                         "message")
        before = self.studio.documents()
        with self.assertRaises(AuthoringError):
            self.studio.add_tactical_command(
                MISSION, "r9c_event", "hazard", {"pos": "999,999", "amount": 4})
        self.assertEqual(self.studio.documents(), before)

    def test_presentation_dialogue_sound_actor_hooks_are_atomic(self):
        self.studio.create(MISSION, "r9c_scene", condition("tick", tick=0),
                           [action("message", text="Signal")])
        self.studio.add_presentation_cue(
            MISSION, "r9c_scene", clip_id="r9c_clip",
            clip_name="Rencontre", kind="dialogue", cue_id="intro_line",
            fields={"speaker": "Jeanne", "text": "Bonjour"})
        self.studio.add_presentation_cue(
            MISSION, "r9c_scene", clip_id="r9c_clip",
            clip_name="Rencontre", kind="sound", cue_id="intro_sound",
            start_ms=1000, duration_ms=2000, fields={"cue": "alarm"})
        self.studio.add_presentation_cue(
            MISSION, "r9c_scene", clip_id="r9c_clip",
            clip_name="Rencontre", kind="actor", cue_id="jeanne_walk",
            start_ms=2000, duration_ms=1000, fields={"actor": "jeanne"})
        project = self.studio.documents()["project"]
        clip = next(x for x in project["cinematics"] if x["id"] == "r9c_clip")
        self.assertEqual(clip["trigger"],
                         {"kind": "tactical_event",
                          "target": MISSION + "/r9c_scene"})
        self.assertEqual([cue["kind"] for cue in clip["events"]],
                         ["dialogue", "sound", "actor"])
        baseline = self.studio.documents()
        with self.assertRaises(AuthoringError):
            self.studio.add_presentation_cue(
                MISSION, "r9c_scene", clip_id="r9c_clip",
                clip_name="Rencontre", kind="sound", cue_id="intro_sound",
                fields={"cue": "second"})
        self.assertEqual(self.studio.documents(), baseline)
        self.studio.undo()
        self.assertEqual(len(self.studio.documents()["project"]["cinematics"][0]["events"]), 2)

    def test_overlay_matches_elevated_iso_tiles_and_never_mutates_scene(self):
        scene = self.studio.iso_scene(MISSION)
        source = deepcopy(scene)
        tile = next(t for t in scene["tiles"] if (t["x"], t["y"]) == (2, 4))
        tile["height"] = 3
        markers = [{"event_id": "open_gate", "pos": [2, 4], "kind": "trigger"},
                   {"event_id": "explosion", "pos": [1, 3], "kind": "effect"}]
        projected = project_event_markers(scene, markers, selected_id="open_gate")
        self.assertEqual(len(projected), 2)
        self.assertTrue(projected[0]["selected"])
        self.assertEqual((projected[0]["sx"], projected[0]["sy"]),
                         IsoProjection().project(2, 4, elevation=3))
        self.assertEqual(projected, project_event_markers(scene, markers,
                                                          selected_id="open_gate"))
        self.assertEqual(source["tiles"][0]["surface"], scene["tiles"][0]["surface"])
        with self.assertRaises(ValueError):
            project_event_markers(scene, [{"event_id": "bad", "kind": "trigger",
                                           "pos": [999, 999]}])
        with self.assertRaises(ValueError):
            project_event_markers(scene, markers * 1000, max_markers=100)

    def test_action_markers_from_canonical_spawn_source(self):
        self.studio.create(MISSION, "r9c_marker", condition("tick", tick=0),
                           [action("hazard", pos=[1, 3], amount=4)])
        markers = self.studio.map_markers(MISSION)
        self.assertIn({"event_id": "r9c_marker",
                       "pos": [1, 3], "kind": "effect"}, markers)


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Optional Qt 6 dependency not available")
class R9CQtSceneSmoke(unittest.TestCase):
    def test_offscreen_qml_shared_viewport_and_graph(self):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   QT_QUICK_BACKEND="software")
        result = subprocess.run(
            [sys.executable, "-m", "drawtemp.studio.event_studio", "--smoke"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=25, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

"""R7.19 pure authoring/Player invariants (no Tk or audio hardware)."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.cinematic_authoring4 import (
    add_motion_keyframe, update_motion_keyframe, remove_motion_keyframe,
    clone_event, move_event, resize_event)
from sporebound.cinematics import (
    cinematic_template, event_template, frame_at, motion_at)
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError


class CinematicStudio4ModelTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.clip = cinematic_template("studio4", "Studio UX 4.0",
                                       "campaign_start", "main")
        self.clip["duration_ms"] = 4000
        self.actor = event_template("actor", "jeanne_walk", 0, 2000)
        self.camera = event_template("camera", "arrival", 0, 2000)
        self.camera.update(**{"from": [0., 0.], "to": [1., 0.]},
                           zoom_from=1., zoom_to=2., easing="linear")
        self.clip["events"] = [self.actor, self.camera]

    def validate(self, events):
        project = deepcopy(self.project)
        clip = deepcopy(self.clip)
        clip["events"] = events
        project.cinematics = [clip]
        project.validate(self.content)
        return project

    def test_actor_keyframes_insert_edit_remove_and_exact_pose(self):
        original = deepcopy(self.actor)
        self.assertAlmostEqual(motion_at(original, 1000)[0][0], .4)
        actor = add_motion_keyframe(original, 1000)
        self.assertEqual(original, self.actor)
        self.assertEqual(actor["keyframes"],
                         [{"at_ms": 1000, "pos": [.4, .65]}])
        self.assertEqual(motion_at(actor, 1000), motion_at(original, 1000))
        actor = update_motion_keyframe(actor, 1000, at_ms=800,
                                       pos=[1.25, -.5])
        self.assertEqual(actor["keyframes"][0]["pos"], [1.25, -.5])
        project = self.validate([actor, self.camera])
        self.assertEqual(frame_at(project.cinematics[0], 800).actors[0][1],
                         (1.25, -.5))
        restored = remove_motion_keyframe(actor, 800)
        self.assertNotIn("keyframes", restored)
        self.assertEqual(restored, original)

    def test_camera_piecewise_keyframe_projection_and_boundaries(self):
        camera = add_motion_keyframe(self.camera, 1000)
        camera = update_motion_keyframe(camera, 1000, pos=[-.5, .4],
                                        zoom=3.0)
        clip = deepcopy(self.clip)
        clip["events"] = [self.actor, camera]
        self.validate(clip["events"])
        self.assertEqual(frame_at(clip, 1000).camera, (-.5, .4))
        self.assertEqual(frame_at(clip, 1000).zoom, 3.)
        self.assertEqual(frame_at(clip, 0).camera, (0., 0.))
        self.assertEqual(frame_at(clip, 2000).camera, (1., 0.))
        self.assertEqual(frame_at(clip, 2000).zoom, 2.)
        self.assertEqual(frame_at(clip, 1500), frame_at(clip, 1500))

    def test_motion_keyframe_strict_schema_and_reference_safety(self):
        actor = add_motion_keyframe(self.actor, 500)
        actor = add_motion_keyframe(actor, 1500)
        for mutation in (
                lambda x: x["keyframes"][0].update(pos=[3, 0]),
                lambda x: x["keyframes"][0].update(at_ms=0),
                lambda x: x["keyframes"][1].update(at_ms=500),
                lambda x: x["keyframes"].reverse(),
                lambda x: x["keyframes"][0].update(extra=1),
                lambda x: x["keyframes"][0].update(at_ms=True),
                lambda x: x["keyframes"][0].update(pos=[False, 0])):
            with self.subTest(mutation=repr(mutation)), self.assertRaises(RuleError):
                broken = deepcopy(actor)
                mutation(broken)
                self.validate([broken, self.camera])
        with self.assertRaises(RuleError):
            add_motion_keyframe(actor, 500)
        with self.assertRaises(RuleError):
            update_motion_keyframe(actor, 500, at_ms=1500)
        with self.assertRaises(RuleError):
            remove_motion_keyframe(actor, 600)
        self.assertEqual(actor["keyframes"][0]["at_ms"], 500)
        self.assertNotIn("keyframes", self.actor)

    def test_legacy_manifest_retained_and_new_keys_roundtrip(self):
        legacy = self.validate([self.actor, self.camera])
        old_payload = legacy.to_dict()
        rebuilt = GameProject.from_dict(old_payload, self.content)
        self.assertEqual(rebuilt.to_dict(), old_payload)
        actor = add_motion_keyframe(self.actor, 600)
        keyed = self.validate([actor, self.camera])
        with TemporaryDirectory() as folder:
            path = Path(folder) / "studio.game.json"
            keyed.save(path, self.content)
            loaded = GameProject.load(path, self.content)
            self.assertEqual(loaded.cinematics[0]["events"][0], actor)
        self.assertEqual(old_payload, legacy.to_dict())

    def test_retime_resize_and_duplicate_are_immutable_and_checked(self):
        actor = add_motion_keyframe(self.actor, 500)
        moved = move_event(actor, 1700, 4000)
        self.assertEqual(moved["keyframes"], actor["keyframes"])
        self.assertEqual(moved["start_ms"], 1700)
        self.assertEqual(actor["start_ms"], 0)
        compressed = resize_event(actor, 1000, 4000)
        self.assertEqual(compressed["keyframes"][0]["at_ms"], 250)
        self.assertEqual(compressed["duration_ms"], 1000)
        copy = clone_event(actor, "jeanne_clone", 2000, 4000)
        self.assertEqual(copy["id"], "jeanne_clone")
        self.validate([actor, copy])
        for action in (
                lambda: move_event(actor, 2500, 4000),
                lambda: resize_event(actor, 0, 4000),
                lambda: resize_event(actor, 5000, 4000),
                lambda: clone_event(actor, "../invalid", 0, 4000)):
            with self.assertRaises(RuleError):
                action()
        tighter = add_motion_keyframe(self.actor, 501)
        tighter = add_motion_keyframe(tighter, 502)
        with self.assertRaises(RuleError):
            resize_event(tighter, 4, 4000)

    def test_existing_cinematic_and_audio_events_unaffected(self):
        old = self.validate([self.actor, self.camera])
        samples = [frame_at(old.cinematics[0], ms)
                   for ms in (0, 500, 1000, 1500, 2000, 2500, 4000)]
        self.assertEqual(samples,
                         [frame_at(old.cinematics[0], ms)
                          for ms in (0, 500, 1000, 1500, 2000, 2500, 4000)])


if __name__ == "__main__":
    unittest.main()

"""Cinematic model, timing, manifest serialization and authoring safety."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.cinematics import (cinematic_template, event_template, frame_at,
                                   matching_cinematics)
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError


class CinematicTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        campaign = self.project.campaigns[0]["id"]
        self.clip = cinematic_template("jeanne_intro", "Jeanne aux champs",
                                       "campaign_start", campaign)
        self.clip["duration_ms"] = 8000
        self.clip["events"] = [
            event_template("background", "fields", 0, 8000),
            event_template("actor", "jeanne_move", 1000, 6000),
            event_template("dialogue", "voice", 2000, 3000),
            event_template("camera", "pan", 0, 8000),
            event_template("fade", "smoke", 7000, 1000),
            event_template("sound", "bells", 1000, 500),
        ]

    def test_project_roundtrip_and_trigger_matching(self):
        data = self.project.to_dict()
        data["cinematics"] = [self.clip]
        project = GameProject.from_dict(data, self.content)
        self.assertEqual(matching_cinematics(project, "campaign_start", "main")[0],
                         self.clip)
        self.assertEqual(matching_cinematics(project, "before_mission", "garden"), [])
        self.assertEqual(GameProject.from_dict(project.to_dict(), self.content).to_dict(),
                         project.to_dict())
        with TemporaryDirectory() as folder:
            file = Path(folder) / "cinematics.game.json"
            project.save(file, self.content)
            self.assertEqual(GameProject.load(file, self.content).cinematics, [self.clip])

    def test_legacy_manifest_remains_compatible(self):
        self.assertNotIn("cinematics", self.project.to_dict())
        self.assertEqual(GameProject.from_dict(self.project.to_dict(), self.content)
                         .cinematics, [])

    def test_seek_camera_actor_dialogue_and_fade(self):
        start = frame_at(self.clip, 0)
        self.assertEqual(start.actors, ())
        mid = frame_at(self.clip, 4000)
        self.assertEqual(mid.dialogue[0], "Jeanne")
        self.assertAlmostEqual(dict(mid.actors)["jeanne"][0], .4)
        self.assertAlmostEqual(mid.zoom, 1.0)
        self.assertEqual(frame_at(self.clip, 4000), mid)
        self.assertIsNone(frame_at(self.clip, 5100).dialogue)
        fade = frame_at(self.clip, 7500).fade
        self.assertEqual(fade[0], "#000000")
        self.assertAlmostEqual(fade[1], .5)
        self.assertEqual(frame_at(self.clip, -50).time_ms, 0)
        self.assertEqual(frame_at(self.clip, 50000).time_ms, 8000)

    def test_trigger_references_and_length_rejected(self):
        base = self.project.to_dict()
        for edit in (
            lambda c: c["trigger"].update(target="unreferenced"),
            lambda c: c.update(duration_ms=100),
            lambda c: c["events"][0].update(duration_ms=9000),
            lambda c: c["events"][1].update(**{"to": [100, 0]}),
            lambda c: c["events"][2].update(text=""),
            lambda c: c["events"][3].update(zoom_from=0),
            lambda c: c["events"][4].update(color="black"),
            lambda c: c["events"][5].update(cue="../outside"),
            lambda c: c["events"].append(deepcopy(c["events"][0])),
        ):
            with self.subTest(edit=repr(edit)), self.assertRaises(RuleError):
                clip = deepcopy(self.clip)
                edit(clip)
                GameProject.from_dict({**base, "cinematics": [clip]}, self.content)

    def test_before_and_after_mission_targets(self):
        mid = next(iter(self.content.missions))
        for kind in ("before_mission", "after_mission"):
            data = {**self.project.to_dict(), "cinematics": [
                cinematic_template("test", "Test", kind, mid)]}
            project = GameProject.from_dict(data, self.content)
            self.assertEqual(len(matching_cinematics(project, kind, mid)), 1)

    def test_empty_and_overlapping_tracks(self):
        empty = deepcopy(self.clip)
        empty["events"] = []
        data = {**self.project.to_dict(), "cinematics": [empty]}
        self.assertEqual(GameProject.from_dict(data, self.content).cinematics[0]["events"], [])
        frame = frame_at(self.clip, 2500)
        self.assertEqual(frame.background, "#243c56")
        self.assertEqual(frame.sounds, ())


if __name__ == "__main__":
    unittest.main()

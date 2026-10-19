"""R20.C.1 — authentic scene-cinematic acknowledgement through GameSession,
R1 Simulation and R12 Player. No synthetic story flag or direct Battle writes.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.simulation import Simulation, SimulationError
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound/content/jeanne.json"
PROJECT = ROOT / "sporebound/content/jeanne.r20c.game.json"
ORIGINAL = ROOT / "sporebound/content/jeanne.game.json"


class R20C1ScenePlayback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT)
        cls.project = GameProject.load(PROJECT, cls.content)
        cls.original = GameProject.load(ORIGINAL, cls.content)

    def test_pending_clip_acknowledges_once_in_campaign_checkpoint(self):
        session = GameSession.new(self.content, self.project, "jeanne", seed=17)
        before = session.recording()
        clip = session.pending_scene_cinematic()
        self.assertEqual(clip["id"], "r20c_ouverture")
        self.assertEqual(session.active_scene()["id"], "sc_p0_champs")
        with self.assertRaises(RuleError):
            session.acknowledge_scene_cinematic("r20c_domremy")
        self.assertEqual(session.recording(), before)
        session.acknowledge_scene_cinematic(clip["id"])
        self.assertIsNone(session.pending_scene_cinematic())
        self.assertEqual(session.progress.story_history, [])
        self.assertEqual(session.progress.completed, [])
        self.assertTrue(any(k.startswith("cine_") for k in session.progress.story_flags))
        with self.assertRaises(RuleError):
            session.acknowledge_scene_cinematic(clip["id"])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene.save.json"
            session.save(path)
            copy = GameSession.load(path, self.content, self.project)
            self.assertEqual(copy.progress, session.progress)
            self.assertIsNone(copy.pending_scene_cinematic())
            self.assertEqual(copy.recording()["digest"],
                             session.recording()["digest"])

    def test_revision_atomicity_and_immutable_projection(self):
        sim = Simulation.new(self.content, self.project, "jeanne", seed=17)
        snap = sim.snapshot()
        cue = sim.pending_scene_cinematic()
        self.assertEqual(cue["id"], "r20c_ouverture")
        before = sim.recording()
        with self.assertRaises(SimulationError):
            sim.acknowledge_scene_cinematic("forged", expected_revision=snap.revision)
        with self.assertRaises(SimulationError):
            sim.acknowledge_scene_cinematic(cue["id"],
                                            expected_revision=snap.revision + 1)
        self.assertEqual(sim.recording(), before)
        transition = sim.acknowledge_scene_cinematic(cue["id"],
                                                    expected_revision=snap.revision)
        self.assertEqual(transition.snapshot.revision, snap.revision + 1)
        self.assertEqual(transition.events[-1].kind,
                         "session.acknowledge_scene_cinematic")
        self.assertIsNone(sim.pending_scene_cinematic())
        self.assertEqual(sim.snapshot().progress["story_history"], ())
        self.assertEqual(sim.snapshot().progress["completed"], ())

    def test_player_blocks_only_story_commands_and_replays_mid_clip_on_load(self):
        with TemporaryDirectory() as tmp:
            ctl = PlayerController(self.content, self.project, "jeanne",
                                   Path(tmp), seed=17)
            intro = ctl.new_game()["cinematic"]
            self.assertEqual(intro["id"], "r20c_ouverture")
            self.assertEqual(ctl.state()["screen"], "exploration")
            start_recording = ctl.session.recording()
            ctl.cinematic_pause()
            ctl.cinematic_seek(2450)
            self.assertEqual(ctl.state()["cinematic"]["frame"]["timeMs"], 2450)
            self.assertFalse(ctl.state()["cinematic"]["playing"])
            ctl.cinematic_play()
            self.assertEqual(ctl.session.recording(), start_recording)
            with self.assertRaises(ValueError):
                ctl.explore_move(1, 0)
            with self.assertRaises(ValueError):
                ctl.choose("ecouter")
            self.assertEqual(ctl.session.recording(), start_recording)

            # Save before skip; a fresh app resumes that visible intro from
            # its start (the timestamp is not a gameplay checkpoint).
            ctl.save(1)
            app2 = PlayerController(self.content, self.project, "jeanne",
                                    Path(tmp), seed=17)
            loaded = app2.load(1)
            self.assertEqual(loaded["cinematic"]["id"], "r20c_ouverture")
            self.assertLess(loaded["cinematic"]["frame"]["timeMs"], 500)
            revision = loaded["revision"]
            app2.cinematic_skip()
            self.assertEqual(app2.state()["cinematic"], {})
            self.assertEqual(app2.state()["revision"], revision + 1)
            self.assertEqual(app2.state()["screen"], "exploration")
            self.assertEqual(app2.session.snapshot().progress["story_history"], ())

            # The acknowledgement survives both manual save and autosave.
            app2.save(1)
            app3 = PlayerController(self.content, self.project, "jeanne",
                                    Path(tmp), seed=17)
            self.assertEqual(app3.load(1)["cinematic"], {})
            self.assertEqual(app3.continue_game()["cinematic"], {})
            # Intro exploration is now available without inventing a reward.
            app3.explore_move(1, 0)
            self.assertEqual(app3.state()["screen"], "exploration")

    def test_old_project_remains_without_cinematic_or_new_flags(self):
        with TemporaryDirectory() as tmp:
            ctl = PlayerController(self.content, self.original, "jeanne",
                                   Path(tmp), seed=17)
            ctl.new_game()
            self.assertEqual(ctl.state()["cinematic"], {})
            self.assertFalse(any(k.startswith("cine_")
                                 for k in ctl.session.snapshot().progress["story_flags"]))
            ctl.explore_move(1, 0)
            self.assertEqual(ctl.session.snapshot().revision, 1)


if __name__ == "__main__":
    unittest.main()

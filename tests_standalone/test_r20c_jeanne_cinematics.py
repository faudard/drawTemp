"""R20.C — authored cinematics, authentic branches and save/replay regression.

R20.C's cinematic playback is presentation-only; a skip must not settle
tactical battles or change narrative progress.
"""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.cinematic_transport import CinematicTransport
from sporebound.cinematics import frame_at, matching_cinematics
from sporebound.game_project import GameProject
from sporebound.game_session import (GameSession, IncompatibleSaveError,
                                     gameplay_project_digest)
from sporebound.model import Content, RuleError
from tests_standalone.test_r20b_jeanne_playable import R20BJeanneTests

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound/content/jeanne.json"
R20B = ROOT / "sporebound/content/jeanne.r20b.game.json"
R20C = ROOT / "sporebound/content/jeanne.r20c.game.json"
ORIGINAL = ROOT / "sporebound/content/jeanne.game.json"

AFTERMATH = {
    "prendre_archives": ("a1_04a_archives", "sc_r20c_archives",
                          "consigner", "archives", "preuve_officielle",
                          "sc_r20c_fin_archives", "sceller_dossier", "preuves"),
    "liberer_otages": ("a1_04b_otages", "sc_r20c_otages",
                        "accueillir", "otages", "parole_otages",
                        "sc_r20c_fin_otages", "tenir_parole", "temoins"),
}


class JeanneR20CCinematicTests(unittest.TestCase):
    # Reuse actual cardinal-step navigation and real Battle.execute checks
    # from R20.B, never its GameProject fixture or old expectation graph.
    visit = R20BJeanneTests.visit
    clear_stage = R20BJeanneTests.clear_stage
    win = R20BJeanneTests.win

    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT)
        cls.original = GameProject.load(ORIGINAL, cls.content)
        cls.r20b = GameProject.load(R20B, cls.content)
        cls.project = GameProject.load(R20C, cls.content)

    def camp(self):
        session = GameSession.new(self.content, self.project, "jeanne", seed=17)
        # Isolated Act-I fixture only: the real Prologue tactical path is
        # exercised independently by test_jeanne_prologue.
        session.progress.completed = [
            "p0_01_lame", "p0_02_incendie", "p0_03a_secours", "p0_04_fuite"
        ]
        session.progress.story_pending = "sc_a1_camp"
        session.progress.story_flags["prologue_complete"] = True
        session.progress.story_flags["village_rescued"] = 2
        return session

    def go_to_branch(self, session, recruit, branch):
        self.clear_stage(session)
        session.choose_story_option(recruit)
        self.win(session, "a1_01_route")
        self.clear_stage(session)
        session.choose_story_option("tenir_passage")
        self.win(session, "a1_02_pont")
        self.clear_stage(session)
        session.choose_story_option("ravitailler")
        self.win(session, "a1_03_hospice")
        self.clear_stage(session)
        session.choose_story_option(branch)

    def test_project_validation_and_scene_trigger_contract(self):
        self.assertEqual(self.project.story["entry_scenes"],
                         self.r20b.story["entry_scenes"])
        self.assertEqual(self.project.exploration, self.r20b.exploration)
        self.assertEqual(len(self.project.cinematics), 10)
        targets = {clip["trigger"]["target"] for clip in self.project.cinematics}
        self.assertIn("sc_a1_dilemme", targets)
        self.assertIn("sc_r20c_archives", targets)
        self.assertIn("sc_r20c_otages", targets)
        for clip in self.project.cinematics:
            self.assertEqual(clip["trigger"]["kind"], "scene")
            self.assertEqual(
                matching_cinematics(self.project, "scene", clip["trigger"]["target"])[0]["trigger"],
                clip["trigger"])
            for at in (0, clip["duration_ms"] // 2, clip["duration_ms"]):
                self.assertEqual(frame_at(clip, at), frame_at(deepcopy(clip), at))
        self.assertNotEqual(gameplay_project_digest(self.r20b),
                            gameplay_project_digest(self.project))

    def test_save_isolation_and_rejection_without_mutation(self):
        for older in (self.original, self.r20b):
            with self.subTest(version=older.subtitle):
                old = GameSession.new(self.content, older, "jeanne", seed=17)
                with TemporaryDirectory() as tmp:
                    path = Path(tmp) / "checkpoint.json"
                    old.save(path)
                    bytes_before = path.read_bytes()
                    with self.assertRaises(IncompatibleSaveError):
                        GameSession.load(path, self.content, self.project)
                    self.assertEqual(path.read_bytes(), bytes_before)
                    upgraded = GameSession.new(self.content, self.project,
                                               "jeanne", seed=17)
                    upgraded.save(path)
                    after = path.read_bytes()
                    with self.assertRaises(IncompatibleSaveError):
                        GameSession.load(path, self.content, older)
                    self.assertEqual(path.read_bytes(), after)

    def test_skip_seek_and_pause_do_not_mutate_game_session(self):
        session = self.camp()
        snapshot = session.recording()
        for clip in self.project.cinematics:
            ticks = [0.]
            transport = CinematicTransport(clip["duration_ms"],
                                            monotonic=lambda: ticks[0])
            ticks[0] = 1.4
            middle = transport.read()
            self.assertTrue(0 <= middle <= clip["duration_ms"])
            transport.pause()
            frozen = transport.read()
            ticks[0] += 10
            self.assertEqual(transport.read(), frozen)
            transport.seek(clip["duration_ms"])  # preview skip only
            self.assertEqual(transport.read(), clip["duration_ms"])
            frame_at(clip, transport.read())
            self.assertEqual(session.recording(), snapshot)
            transport.restart()
            self.assertEqual(transport.read(), 0)

    def test_branch_paths_are_actual_battles_with_persisted_aftermath(self):
        for branch, info in AFTERMATH.items():
            (mission, scene, response, chosen, ending, epilogue,
             last_choice, conclusion) = info
            with self.subTest(branch=branch):
                session = self.camp()
                recruit = ("engager_etienne" if branch == "prendre_archives"
                           else "engager_agnes")
                self.go_to_branch(session, recruit, branch)
                self.assertEqual(session.available_missions(), [mission])
                self.win(session, mission)
                self.assertEqual(session.active_scene()["id"], scene)
                self.assertEqual(len(matching_cinematics(
                    self.project, "scene", scene)), 1)
                with TemporaryDirectory() as tmp:
                    save = Path(tmp) / "branch.json"
                    session.save(save)
                    restored = GameSession.load(save, self.content, self.project)
                    self.assertEqual(restored.progress, session.progress)
                    self.assertEqual(restored.active_scene()["id"], scene)
                    restored.choose_story_option(response)
                    self.assertEqual(restored.progress.story_flags["r20c_route_after"], chosen)
                    self.assertEqual(restored.active_scene()["id"], "sc_a1_debrief")
                    with self.assertRaises(RuleError):
                        restored.choose_story_option(response)  # cannot replay reward
                    restored.save(save)
                    restored = GameSession.load(save, self.content, self.project)
                    self.assertEqual(restored.progress.story_flags["r20c_route_after"],
                                     chosen)
                    restored.choose_story_option("avancer_vaucouleurs")
                    self.win(restored, "a1_05_vaucouleurs")
                    self.assertEqual(restored.active_scene()["id"], "sc_a1_fin")
                    self.assertNotIn(ending, {
                        "preuve_officielle" if branch == "liberer_otages"
                        else "parole_otages"
                    })
                    self.assertIn(ending, {o["id"] for o in restored.available_choices()})
                    restored.choose_story_option(ending)
                    self.assertEqual(restored.active_scene()["id"], epilogue)
                    self.assertTrue(restored.progress.story_flags["acte1_complete"])
                    restored.save(save)
                    restored = GameSession.load(save, self.content, self.project)
                    self.assertEqual(restored.active_scene()["id"], epilogue)
                    restored.choose_story_option(last_choice)
                    self.assertEqual(restored.progress.story_flags["r20c_act1_conclusion"],
                                     conclusion)
                    self.assertEqual(restored.active_scene(), None)
                    self.assertEqual(restored.available_missions(), [])
                    restored.save(save)
                    final = GameSession.load(save, self.content, self.project)
                    self.assertEqual(final.progress, restored.progress)
                    self.assertEqual(final.recording()["digest"],
                                     restored.recording()["digest"])

    def test_faith_fallback_has_independent_non_blocking_epilogue(self):
        session = self.camp()
        session.progress.story_pending = "sc_a1_fin"
        session.progress.story_flags["acte1_choix"] = "otages"
        self.assertIn("appel_de_jeanne",
                      {option["id"] for option in session.available_choices()})
        session.choose_story_option("appel_de_jeanne")
        self.assertEqual(session.active_scene()["id"], "sc_r20c_fin_foi")
        session.choose_story_option("partir_libre")
        self.assertEqual(session.progress.story_flags["r20c_act1_conclusion"],
                         "libre_arbitre")

    def test_invalid_cinematic_source_and_story_gate_fail_closed(self):
        altered = deepcopy(self.project)
        altered.cinematics[0]["trigger"]["target"] = "missing_scene"
        with self.assertRaises(RuleError):
            altered.validate(self.content)
        altered = deepcopy(self.project)
        ending = next(scene for scene in altered.story["scenes"]
                      if scene["id"] == "sc_a1_fin")
        guarded = next(choice for choice in ending["choices"]
                       if choice["id"] == "preuve_officielle")
        guarded["when"] = {"completed_mission": "not_a_mission"}
        with self.assertRaises(RuleError):
            altered.validate(self.content)


if __name__ == "__main__":
    unittest.main()

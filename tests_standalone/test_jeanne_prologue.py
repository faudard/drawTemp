"""Regression gates for Jeanne's separate, command-driven playable prologue.

The gameplay is intentionally small and uses the normal Content, GameProject,
GameSession, AI and replay contracts. Never settle battles by assigning result.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sporebound.ai import choose_command
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError


HERE = Path(__file__).resolve().parents[1]
CONTENT = HERE / "sporebound" / "content" / "jeanne.json"
PROJECT = HERE / "sporebound" / "content" / "jeanne.game.json"


class JeannePrologueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT)
        cls.project = GameProject.load(PROJECT, cls.content)

    def new_session(self):
        return GameSession.new(self.content, self.project, "jeanne", seed=17)

    def intro(self, session, response="ecouter"):
        self.assertEqual(session.active_scene()["id"], "sc_p0_champs")
        self.assertEqual(session.available_missions(), [])
        session.choose_story_option(response)
        self.assertEqual(session.active_scene()["id"], "sc_p0_visions")
        session.choose_story_option("repondre")
        self.assertEqual(session.active_scene()["id"], "sc_p0_fumee")
        session.choose_story_option("souvenir")
        self.assertEqual(session.available_missions(), ["p0_01_lame"])

    def win_mission(self, session, mission_id, limit=700):
        self.assertIn(mission_id, session.available_missions())
        battle = session.start_mission(mission_id)
        self.assertEqual(session.mode, "battle")
        self.assertEqual(battle.mission.id, mission_id)
        for _ in range(limit):
            if session.active_battle.result:
                break
            session.execute(choose_command(session.active_battle))
        self.assertEqual(
            session.active_battle.result, "victory",
            f"{mission_id}: incomplete/defeated after {limit} commands")
        self.assertIn(mission_id, session.progress.completed)
        self.assertTrue(session.finalized)
        session.return_to_campaign()

    def test_project_is_standalone_and_missions_valid(self):
        self.assertEqual(self.project.title, "Jeanne d'Arc — Les Cendres du Royaume")
        self.assertEqual(set(self.content.missions), {
            "p0_01_lame", "p0_02_incendie", "p0_03a_secours",
            "p0_03b_poursuite", "p0_04_fuite"})
        self.assertEqual(self.project.campaigns[0]["start_mission"], "p0_01_lame")
        self.assertTrue(all(not s.magical for s in self.content.skills.values()))
        self.assertEqual(
            {m for m in self.project.story["after_mission"]},
            set(self.content.missions))
        self.assertTrue(all(not m.next_missions for m in self.content.missions.values()))

    def test_prologue_branches_are_exclusive_and_replayable(self):
        paths = (
            ("secourir", "p0_03a_secours", "p0_03b_poursuite", "secours"),
            ("poursuivre", "p0_03b_poursuite", "p0_03a_secours", "poursuite"),
        )
        for choice, chosen, locked, label in paths:
            with self.subTest(path=label):
                session = self.new_session()
                self.intro(session)
                self.win_mission(session, "p0_01_lame")
                self.assertEqual(session.active_scene()["id"], "sc_p0_apres_lecon")
                session.choose_story_option("courir")
                self.win_mission(session, "p0_02_incendie")
                self.assertEqual(session.active_scene()["id"], "sc_p0_cendres")
                session.choose_story_option(choice)
                self.assertEqual(session.progress.story_flags["prologue_path"], label)
                self.assertEqual(session.available_missions(), [chosen])
                self.assertNotIn(locked, session.progress.unlocked)
                with self.assertRaises(RuleError):
                    session.start_mission(locked)
                with TemporaryDirectory() as tmp:
                    save = Path(tmp) / "jeanne.session.json"
                    session.save(save)
                    restored = GameSession.load(save, self.content, self.project)
                    self.assertEqual(restored.progress, session.progress)
                    self.assertEqual(restored.available_missions(), [chosen])
                    session = restored
                    self.win_mission(session, chosen)
                    self.assertEqual(session.active_scene()["id"], "sc_p0_apres_branche")
                    session.choose_story_option("partir")
                    self.assertEqual(session.available_missions(), ["p0_04_fuite"])
                    self.win_mission(session, "p0_04_fuite")
                    self.assertEqual(session.active_scene()["id"], "sc_p0_au_revoir")
                    session.choose_story_option("promesse")
                    self.assertEqual(session.progress.story_flags["prologue_complete"], True)
                    self.assertEqual(session.available_missions(), [])
                    self.assertEqual(len(session.progress.completed), 4)
                    self.assertNotIn(locked, session.progress.completed)
                    # Narrative flags are never paid or applied twice by a reload.
                    session.save(save)
                    finished = GameSession.load(save, self.content, self.project)
                    self.assertEqual(finished.progress, session.progress)
                    self.assertEqual(finished.progress.story_flags["prologue_path"], label)
                    self.assertEqual(finished.available_missions(), [])

    def test_midbattle_save_is_verified_and_does_not_award_rewards(self):
        session = self.new_session()
        self.intro(session, response="resister")
        session.start_mission("p0_01_lame")
        session.execute(choose_command(session.active_battle))
        self.assertEqual(session.progress.completed, [])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "combat.json"
            session.save(path)
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(session.active_battle.digest(),
                             restored.active_battle.digest())
            self.assertEqual(restored.progress.completed, [])
            self.assertEqual(restored.mode, "battle")

    def test_cannot_skip_unfinished_combat_into_story(self):
        session = self.new_session()
        self.intro(session)
        session.start_mission("p0_01_lame")
        with self.assertRaises(RuleError):
            session.return_to_campaign()
        with self.assertRaises(RuleError):
            session.choose_story_option("courir")
        self.assertEqual(session.progress.completed, [])
        session.abandon_encounter()
        self.assertEqual(session.available_missions(), ["p0_01_lame"])


if __name__ == "__main__":
    unittest.main()

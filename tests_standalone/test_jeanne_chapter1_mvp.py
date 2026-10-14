"""Jeanne Chapter I MVP: clean entry, five real encounters and save/reload."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from sporebound.__main__ import main
from sporebound.ai import choose_command
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.jeanne_chapter1 import CHAPTER_CAMPAIGN_ID, chapter_one_project
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController

ROOT = Path(__file__).resolve().parents[1]
CONTENT_FILE = ROOT / "sporebound/content/jeanne.json"
PROJECT_FILE = ROOT / "sporebound/content/jeanne.game.json"


class JeanneChapterOneMVPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT_FILE)
        cls.original = GameProject.load(PROJECT_FILE, cls.content)
        cls.project = chapter_one_project(cls.content, cls.original)

    def new_session(self):
        return GameSession.new(self.content, self.project, CHAPTER_CAMPAIGN_ID,
                               seed=17)

    def win(self, session, mission):
        self.assertEqual(session.available_missions(), [mission])
        session.start_mission(mission)
        for _ in range(850):
            if session.active_battle.result is not None:
                break
            session.execute(choose_command(session.active_battle))
        self.assertEqual(session.active_battle.result, "victory", mission)
        session.return_to_campaign()

    def test_isolated_entry_without_fictitious_prologue(self):
        before = deepcopy(self.original.to_dict())
        chapter = chapter_one_project(self.content, self.original)
        self.assertEqual(self.original.to_dict(), before)
        self.assertEqual(self.original.story["entry_scenes"]["jeanne"],
                         "sc_p0_champs")
        self.assertEqual(chapter.story["entry_scenes"],
                         {CHAPTER_CAMPAIGN_ID: "sc_a1_camp"})
        session = self.new_session()
        self.assertEqual(session.progress.completed, [])
        self.assertEqual(session.active_scene()["id"], "sc_a1_camp")
        self.assertEqual(session.available_missions(), [])
        with self.assertRaises(RuleError):
            session.start_mission("a1_01_route")
        session.choose_story_option("engager_agnes")
        self.assertTrue(session.progress.story_flags["recruited_agnes"])
        self.assertEqual(session.available_missions(), ["a1_01_route"])

    def test_both_branch_paths_to_vaucouleurs_survive_reload(self):
        paths = [
            ("engager_etienne", "prendre_archives",
             "a1_04a_archives", "a1_04b_otages", "archives"),
            ("engager_agnes", "liberer_otages",
             "a1_04b_otages", "a1_04a_archives", "temoins"),
        ]
        for recruit, branch, chosen, excluded, support in paths:
            with self.subTest(branch=branch), TemporaryDirectory() as directory:
                session = self.new_session()
                session.choose_story_option(recruit)
                self.win(session, "a1_01_route")
                self.assertEqual(session.active_scene()["id"], "sc_a1_pont")
                session.choose_story_option("tenir_passage")
                self.win(session, "a1_02_pont")
                session.choose_story_option("ravitailler")
                self.win(session, "a1_03_hospice")
                self.assertEqual(session.active_scene()["id"], "sc_a1_dilemme")
                session.choose_story_option(branch)
                self.assertEqual(session.available_missions(), [chosen])
                with self.assertRaises(RuleError):
                    session.start_mission(excluded)
                checkpoint = Path(directory) / "chapter1.json"
                session.save(checkpoint)
                session = GameSession.load(checkpoint, self.content, self.project)
                self.win(session, chosen)
                session.choose_story_option("avancer_vaucouleurs")
                self.win(session, "a1_05_vaucouleurs")
                self.assertEqual(session.active_scene()["id"], "sc_a1_fin")
                session.choose_story_option(
                    "preuve_officielle" if support == "archives"
                    else "parole_otages")
                self.assertTrue(session.progress.story_flags["acte1_complete"])
                self.assertEqual(session.progress.story_flags["acte2_appui"], support)
                self.assertEqual(session.available_missions(), [])
                self.assertNotIn(excluded, session.progress.completed)
                session.save(checkpoint)
                resumed = GameSession.load(checkpoint, self.content, self.project)
                self.assertEqual(resumed.progress, session.progress)

    def test_player_controller_checkpoint(self):
        with TemporaryDirectory() as directory:
            profile = Path(directory) / "chapter1.game.json"
            player = PlayerController(self.content, self.project, profile)
            player.new_game(CHAPTER_CAMPAIGN_ID, 1, seed=17)
            player.choose_story_option("engager_etienne")
            other = PlayerController(self.content, self.project, profile)
            self.assertEqual(
                other.load_game(CHAPTER_CAMPAIGN_ID, 1).available_missions(),
                ["a1_01_route"])

    def test_cli_entry(self):
        with patch("sporebound.player_app.launch") as launcher:
            self.assertEqual(main(["jeanne-chapter1"]), 0)
            launcher.assert_called_once_with(
                CONTENT_FILE, PROJECT_FILE, None, chapter_one=True)


    def test_briefings_cover_all_real_missions_and_no_other_games(self):
        from sporebound.jeanne_chapter1 import (
            CHAPTER_MISSIONS, chapter_mission_card, CHAPTER_BEATS)
        self.assertEqual(set(CHAPTER_MISSIONS), set(CHAPTER_BEATS))
        for mid in CHAPTER_MISSIONS:
            with self.subTest(mission=mid):
                card = chapter_mission_card(mid)
                self.assertIn(card["ordinal"], ("01", "02", "03", "04", "05"))
                self.assertTrue(card["context"] and card["objective"]
                                and card["tip"] and card["victory"])
                self.assertIn(mid, self.content.missions)
        with self.assertRaises(RuleError):
            chapter_mission_card("p0_01_lame")

    def test_demo_progress_preserves_actual_choices(self):
        from sporebound.jeanne_chapter1 import chapter_progress
        session = self.new_session()
        beginning = chapter_progress(session.progress)
        self.assertEqual(beginning["completed"], 0)
        self.assertEqual(beginning["companion"], "À recruter")
        self.assertFalse(beginning["finished"])
        session.choose_story_option("engager_etienne")
        self.assertEqual(chapter_progress(session.progress)["companion"], "Étienne")
        self.win(session, "a1_01_route")
        self.assertEqual(chapter_progress(session.progress)["completed"], 1)
        self.assertFalse(chapter_progress(session.progress)["finished"])

    def test_auto_enemy_only_in_enemy_turn_not_in_story_or_results(self):
        from types import SimpleNamespace
        from sporebound.jeanne_chapter1 import chapter_auto_enemy

        enemy = SimpleNamespace(team="enemy")
        battle = SimpleNamespace(active=enemy, deploying=False, result=None)
        session = SimpleNamespace(
            mode="battle", active_battle=battle, finalized=False,
            tactical_story_pending="",
            progress=SimpleNamespace(story_pending=""))
        self.assertTrue(chapter_auto_enemy(session))
        self.assertFalse(chapter_auto_enemy(session, enabled=False))
        session.tactical_story_pending = "sc_warning"
        self.assertFalse(chapter_auto_enemy(session))
        session.tactical_story_pending = ""
        battle.deploying = True
        self.assertFalse(chapter_auto_enemy(session))
        battle.deploying = False
        battle.result = "victory"
        self.assertFalse(chapter_auto_enemy(session))
        battle.result = None
        battle.active = SimpleNamespace(team="player")
        self.assertFalse(chapter_auto_enemy(session))
        battle.active = enemy
        session.mode = "campaign"
        self.assertFalse(chapter_auto_enemy(session))


if __name__ == "__main__":
    unittest.main()

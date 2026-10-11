"""Act I headless gates: authored path, real recruitment, gear, rewards and save."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.ai import choose_command
from sporebound.campaign import Campaign
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound/content/jeanne.json"
PROJECT = ROOT / "sporebound/content/jeanne.game.json"


class JeanneActeITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT)
        cls.project = GameProject.load(PROJECT, cls.content)

    def session_at_camp(self):
        # Isolate the Act I boundary; the real tactical prologue is already
        # exercised independently by test_jeanne_prologue.
        session = GameSession.new(self.content, self.project, "jeanne", seed=17)
        session.progress.completed = [
            "p0_01_lame", "p0_02_incendie", "p0_03a_secours", "p0_04_fuite"
        ]
        session.progress.story_pending = "sc_a1_camp"
        session.progress.story_flags["prologue_complete"] = True
        session.progress.story_flags["village_rescued"] = 2
        return session

    def win(self, session, mission_id, max_commands=850):
        self.assertEqual(session.available_missions(), [mission_id])
        session.start_mission(mission_id)
        for _ in range(max_commands):
            if session.active_battle.result is not None:
                break
            session.execute(choose_command(session.active_battle))
        self.assertEqual(session.active_battle.result, "victory", mission_id)
        self.assertIn(mission_id, session.progress.completed)
        session.return_to_campaign()

    def test_camp_recruitment_changes_actual_roster_and_equipment(self):
        for choice, ally, other, item in [
            ("engager_etienne", "etienne", "agnes", "gambison_ecuyer"),
            ("engager_agnes", "agnes", "etienne", "baton_hospice"),
        ]:
            with self.subTest(choice=choice):
                session = self.session_at_camp()
                self.assertEqual(session.active_scene()["id"], "sc_a1_camp")
                session.choose_story_option(choice)
                self.assertTrue(session.progress.story_flags["recruited_" + ally])
                self.assertEqual(session.progress.hero(ally).equipment[
                    self.content.equipment[item]["slot"]], item)
                self.assertEqual(session.progress.inventory[item], 0)
                battle = session.start_mission("a1_01_route")
                actual = {unit.id: unit for unit in battle.units if unit.team == "player"}
                self.assertEqual(set(actual), {"jeanne", ally})
                baseline = next(
                    u for u in self.content.missions["a1_01_route"].units
                    if u.id == ally)
                bonus = self.content.equipment[item]["bonuses"]
                for stat, value in bonus.items():
                    self.assertGreaterEqual(getattr(actual[ally], stat),
                                            getattr(baseline, stat) + value)
                with self.assertRaises(RuleError):
                    session.choose_story_option("engager_etienne")
                session.abandon_encounter()

    def test_two_exclusive_routes_and_act_ii_handoff(self):
        for recruit, branch, chosen, closed in [
            ("engager_etienne", "prendre_archives", "a1_04a_archives", "a1_04b_otages"),
            ("engager_agnes", "liberer_otages", "a1_04b_otages", "a1_04a_archives"),
        ]:
            with self.subTest(branch=branch):
                session = self.session_at_camp()
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
                self.assertNotIn(closed, session.progress.unlocked)
                with self.assertRaises(RuleError):
                    session.start_mission(closed)
                with TemporaryDirectory() as tmp:
                    save_path = Path(tmp) / "acte1.json"
                    session.save(save_path)
                    session = GameSession.load(save_path, self.content, self.project)
                    self.assertEqual(session.available_missions(), [chosen])
                    self.win(session, chosen)
                    self.assertEqual(session.active_scene()["id"], "sc_a1_debrief")
                    session.choose_story_option("avancer_vaucouleurs")
                    self.win(session, "a1_05_vaucouleurs")
                    self.assertEqual(session.active_scene()["id"], "sc_a1_fin")
                    if branch == "prendre_archives":
                        session.choose_story_option("preuve_officielle")
                        self.assertEqual(session.progress.story_flags["acte2_appui"], "archives")
                    else:
                        session.choose_story_option("parole_otages")
                        self.assertEqual(session.progress.story_flags["acte2_appui"], "temoins")
                    self.assertTrue(session.progress.story_flags["acte1_complete"])
                    self.assertTrue(session.progress.story_flags["acte2_route_ouverte"])
                    self.assertEqual(session.available_missions(), [])
                    self.assertNotIn(closed, session.progress.completed)
                    session.save(save_path)
                    restored = GameSession.load(save_path, self.content, self.project)
                    self.assertEqual(restored.progress, session.progress)
                    self.assertEqual(restored.available_missions(), [])

    def test_invalid_equipment_choice_is_atomic(self):
        session = self.session_at_camp()
        before = deepcopy(session.progress)
        with self.assertRaises(RuleError):
            session.progress.equip(self.content, "agnes", "baton_hospice")
        self.assertEqual(session.progress, before)
        session.choose_story_option("engager_agnes")
        self.assertEqual(session.progress.hero("agnes").equipment["weapon"], "baton_hospice")


if __name__ == "__main__":
    unittest.main()

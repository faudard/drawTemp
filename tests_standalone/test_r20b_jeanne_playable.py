"""R20.B — real village/forest/refuge exploration on the existing Jeanne battles.

The alternate authoring pack has its own project digest/save identity.
Victories here are actual Battle.execute commands, never patched results.
"""
from collections import deque
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.ai import choose_command
from sporebound.game_project import GameProject
from sporebound.game_session import (GameSession, IncompatibleSaveError,
                                    gameplay_project_digest)
from sporebound.model import Content, RuleError

ROOT = Path(__file__).resolve().parents[1]
CONTENT_PATH = ROOT / "sporebound/content/jeanne.json"
ORIGINAL_PATH = ROOT / "sporebound/content/jeanne.game.json"
R20B_PATH = ROOT / "sporebound/content/jeanne.r20b.game.json"

STAGES = {
    "sc_a1_camp": ("eline", "camp_rescued"),
    "sc_a1_pont": ("luc", "forest_rescued"),
    "sc_a1_hospice": ("lucie", "refuge_rescued"),
    "sc_a1_dilemme": (None, None),
}
MOVES = ((0, -1), (0, 1), (-1, 0), (1, 0))


class R20BJeanneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT_PATH)
        cls.original = GameProject.load(ORIGINAL_PATH, cls.content)
        cls.project = GameProject.load(R20B_PATH, cls.content)

    def camp(self):
        # The real prologue is covered by test_jeanne_prologue; do not assign
        # any fake tactical result to a Battle in this Act I integration gate.
        session = GameSession.new(self.content, self.project, "jeanne", seed=17)
        session.progress.completed = [
            "p0_01_lame", "p0_02_incendie", "p0_03a_secours", "p0_04_fuite"
        ]
        session.progress.story_pending = "sc_a1_camp"
        session.progress.story_flags["prologue_complete"] = True
        session.progress.story_flags["village_rescued"] = 2
        return session

    def visit(self, session, target_id):
        """Walk through actual cardinal moves to an authored interaction."""
        stage = session.exploration_state()
        target = next(point["pos"] for point in stage["interactions"]
                      if point["id"] == target_id)
        start = tuple(stage["position"])
        blocked = {tuple(xy) for xy in stage["blocked"]}
        seen, queue = {start}, deque([(start, [])])
        route = None
        while queue:
            pos, moves = queue.popleft()
            if abs(pos[0] - target[0]) + abs(pos[1] - target[1]) <= 1:
                route = moves
                break
            for dx, dy in MOVES:
                other = (pos[0] + dx, pos[1] + dy)
                if (0 <= other[0] < stage["width"]
                        and 0 <= other[1] < stage["height"]
                        and other not in blocked and other not in seen):
                    seen.add(other)
                    queue.append((other, moves + [(dx, dy)]))
        self.assertIsNotNone(route, "Unreachable stage target " + target_id)
        for dx, dy in route:
            session.explore_move(dx, dy)
        return session.explore_interact(target_id)

    def clear_stage(self, session, *, rescue=False):
        current = session.active_scene()["id"]
        self.assertIn(current, STAGES)
        stage = session.exploration_state()
        self.assertFalse(stage["completed"])
        self.assertEqual(session.available_choices(), [])
        actor_id, flag = STAGES[current]
        if rescue and actor_id:
            # Each civilian starts adjacent to Jeanne; rescue is optional
            # and only earns support through the canonical battle_support gate.
            report = session.explore_actor(actor_id, "rescue")
            self.assertTrue(report["rescued"])
            self.assertEqual(session.progress.story_flags[flag], 1)
            with self.assertRaises(RuleError):
                session.explore_actor(actor_id, "rescue")
        required = [p["id"] for p in stage["interactions"] if p["required"]]
        exit_id = next(p["id"] for p in stage["interactions"] if p["exit"])
        with self.assertRaises(RuleError):
            session.choose_story_option(session.active_scene()["choices"][0]["id"])
        # Trying to use the exit before visiting required locations is forbidden.
        for ident in required:
            report = self.visit(session, ident)
            self.assertFalse(report["finished"])
        report = self.visit(session, exit_id)
        self.assertTrue(report["finished"])
        self.assertTrue(session.exploration_state()["completed"])
        self.assertTrue(session.available_choices())

    def win(self, session, mid, expected_potions=None, max_commands=900):
        self.assertEqual(session.available_missions(), [mid])
        session.start_mission(mid)
        if expected_potions is not None:
            self.assertEqual(session.active_battle.inventory["player"]["potion"],
                             expected_potions, mid)
        for _ in range(max_commands):
            if session.active_battle.result:
                break
            session.execute(choose_command(session.active_battle))
        self.assertEqual(session.active_battle.result, "victory", mid)
        self.assertIn(mid, session.progress.completed)
        self.assertTrue(session.finalized)
        session.return_to_campaign()

    def test_variant_is_valid_and_original_saves_remain_isolated(self):
        self.assertEqual(self.original.story, self.project.story)
        self.assertEqual(self.original.assets, self.project.assets)
        self.assertNotEqual(gameplay_project_digest(self.original),
                            gameplay_project_digest(self.project))
        for sid, stage in self.original.exploration.items():
            self.assertEqual(self.project.exploration[sid], stage)
        for sid in STAGES:
            self.assertIn(sid, self.project.exploration)
            self.assertNotIn(sid, self.original.exploration)
        original = GameSession.new(self.content, self.original, "jeanne", seed=17)
        with TemporaryDirectory() as folder:
            save = Path(folder) / "legacy.json"
            original.save(save)
            self.assertEqual(GameSession.load(save, self.content,
                                              self.original).progress,
                             original.progress)
            with self.assertRaises(IncompatibleSaveError):
                GameSession.load(save, self.content, self.project)
            variant = GameSession.new(self.content, self.project,
                                      "jeanne", seed=17)
            variant.save(save)
            with self.assertRaises(IncompatibleSaveError):
                GameSession.load(save, self.content, self.original)

    def test_exploration_checkpoint_and_no_duplicate_rescue(self):
        session = self.camp()
        session.explore_actor("eline", "rescue")
        self.visit(session, "foyer")
        with TemporaryDirectory() as folder:
            path = Path(folder) / "checkpoint.json"
            session.save(path)
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(restored.exploration_state(),
                             session.exploration_state())
            self.assertEqual(restored.progress.story_flags["camp_rescued"], 1)
            with self.assertRaises(RuleError):
                restored.explore_actor("eline", "rescue")
            self.visit(restored, "provisions")
            self.visit(restored, "depart")
            restored.choose_story_option("engager_etienne")
            self.assertEqual(restored.progress.story_flags["recruited_etienne"], True)
            self.assertEqual(restored.available_missions(), ["a1_01_route"])
            # Baseline has one village-rescue potion, the camp rescue adds one.
            battle = restored.start_mission("a1_01_route")
            self.assertEqual(battle.inventory["player"]["potion"], 5)
            self.assertIsNone(battle.result)
            restored.abandon_encounter()

    def test_deadlines_are_optional_and_never_softlock_dialogue(self):
        session = self.camp()
        session.progress.story_pending = "sc_a1_pont"
        for _ in range(21):
            session.explore_wait()
        self.assertEqual(session.exploration_state()["actors"][0]["status"], "lost")
        with self.assertRaises(RuleError):
            session.explore_actor("luc", "rescue")
        self.assertNotIn("forest_rescued", session.progress.story_flags)
        self.clear_stage(session, rescue=False)
        session.choose_story_option("tenir_passage")
        self.assertEqual(session.available_missions(), ["a1_02_pont"])

    def test_all_act_i_stages_and_both_branches_real_battles(self):
        # This gate is intentionally separate from the full playable prologue.
        for recruit, route, mission, ending, save_rescues in (
            ("engager_etienne", "prendre_archives", "a1_04a_archives",
             "preuve_officielle", True),
            ("engager_agnes", "liberer_otages", "a1_04b_otages",
             "parole_otages", False),
        ):
            with self.subTest(route=route):
                session = self.camp()
                self.clear_stage(session, rescue=save_rescues)
                session.choose_story_option(recruit)
                self.win(session, "a1_01_route", 5 if save_rescues else 4)
                self.assertEqual(session.active_scene()["id"], "sc_a1_pont")
                self.clear_stage(session, rescue=save_rescues)
                session.choose_story_option("tenir_passage")
                self.win(session, "a1_02_pont", 5 if save_rescues else 4)
                self.assertEqual(session.active_scene()["id"], "sc_a1_hospice")
                self.clear_stage(session, rescue=save_rescues)
                session.choose_story_option("ravitailler")
                self.win(session, "a1_03_hospice", 5 if save_rescues else 4)
                self.assertEqual(session.active_scene()["id"], "sc_a1_dilemme")
                self.clear_stage(session)
                session.choose_story_option(route)
                self.assertEqual(session.available_missions(), [mission])
                self.win(session, mission)
                self.assertEqual(session.active_scene()["id"], "sc_a1_debrief")
                session.choose_story_option("avancer_vaucouleurs")
                self.win(session, "a1_05_vaucouleurs")
                self.assertEqual(session.active_scene()["id"], "sc_a1_fin")
                session.choose_story_option(ending)
                self.assertTrue(session.progress.story_flags["acte1_complete"])
                self.assertTrue(session.progress.story_flags["acte2_route_ouverte"])
                self.assertEqual(session.available_missions(), [])
                self.assertEqual(len(session.progress.completed), 9)
                with TemporaryDirectory() as folder:
                    path = Path(folder) / "act1.json"
                    session.save(path)
                    copy = GameSession.load(path, self.content, self.project)
                    self.assertEqual(copy.progress, session.progress)
                    self.assertEqual(copy.available_missions(), [])


if __name__ == "__main__":
    unittest.main()

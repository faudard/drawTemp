"""Living village: deterministic villagers, timed rescues and replayable supplies."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound" / "content" / "jeanne.json"
PROJECT = ROOT / "sporebound" / "content" / "jeanne.game.json"


class LivingVillageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(CONTENT)
        cls.project = GameProject.load(PROJECT, cls.content)

    def village(self):
        session = GameSession.new(self.content, self.project, "jeanne", seed=9)
        # Isolate a particular narrative stage; the full playable route remains
        # covered by test_jeanne_prologue.
        session.progress.story_pending = "sc_p0_cendres"
        return session

    def actor(self, session, ident):
        return next(a for a in session.exploration_state()["actors"]
                    if a["id"] == ident)

    def rescue_two(self, session):
        session.explore_actor("colin", "rescue")   # at [2,5]
        for step in ((1, 0), (1, 0), (1, 0), (0, 1)):
            session.explore_move(*step)
        self.assertEqual(session.exploration_state()["position"], [4, 6])
        self.assertEqual(self.actor(session, "isabeau")["pos"], [5, 6])
        session.explore_actor("isabeau", "rescue")

    def test_moves_actor_and_rescues_once(self):
        session = self.village()
        self.assertEqual(self.actor(session, "colin")["status"], "active")
        self.assertEqual(session.exploration_state()["tick"], 0)
        talk = session.explore_actor("colin", "talk")
        self.assertIn("boulanger", talk["title"])
        self.assertEqual(session.progress.story_flags.get("village_rescued", 0), 0)
        message = session.explore_actor("colin", "rescue")
        self.assertTrue(message["rescued"])
        self.assertEqual(session.progress.story_flags["village_rescued"], 1)
        with self.assertRaises(RuleError):
            session.explore_actor("colin", "rescue")
        self.assertEqual(session.progress.story_flags["village_rescued"], 1)
        session.explore_move(1, 0)
        self.assertEqual(session.exploration_state()["tick"], 1)
        self.assertEqual(self.actor(session, "isabeau")["pos"], [6, 6])

    def test_expired_rescue_is_not_a_softlock(self):
        session = self.village()
        for _ in range(16):
            session.explore_wait()
        self.assertEqual(self.actor(session, "colin")["status"], "lost")
        with self.assertRaises(RuleError):
            session.explore_actor("colin", "rescue")
        self.assertEqual(session.progress.story_flags.get("village_rescued", 0), 0)
        # Unrelated required exploration hotspots remain accessible.
        self.assertFalse(session.exploration_state()["completed"])
        self.assertEqual(session.available_choices(), [])
        session.explore_move(1, 0)
        self.assertEqual(session.exploration_state()["position"], [2, 5])

    def test_checkpoint_preserves_rescues_positions_and_clock(self):
        session = self.village()
        self.rescue_two(session)
        self.assertEqual(session.progress.story_flags["village_rescued"], 2)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "living_village.json"
            session.save(path)
            loaded = GameSession.load(path, self.content, self.project)
            self.assertEqual(loaded.exploration_state(), session.exploration_state())
            self.assertEqual(loaded.progress, session.progress)
            self.assertEqual(self.actor(loaded, "colin")["status"], "rescued")
            self.assertEqual(self.actor(loaded, "isabeau")["status"], "rescued")
            with self.assertRaises(RuleError):
                loaded.explore_actor("isabeau", "rescue")
            self.assertEqual(loaded.progress.story_flags["village_rescued"], 2)

    def test_saved_civilians_influence_real_tactical_inventory_and_replay(self):
        supported = self.village()
        self.rescue_two(supported)
        supported.progress.story_pending = ""
        supported.progress.unlocked.append("p0_03a_secours")
        battle = supported.start_mission("p0_03a_secours")
        self.assertEqual(battle.inventory["player"]["potion"], 5)
        self.assertEqual(battle.recording()["initial_state"]["inventory"]["potion"], 5)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "prepared_battle.json"
            supported.save(path)
            loaded = GameSession.load(path, self.content, self.project)
            self.assertEqual(loaded.active_battle.inventory["player"]["potion"], 5)
            self.assertEqual(loaded.active_battle.digest(), battle.digest())
            self.assertEqual(loaded.progress.story_flags["village_rescued"], 2)
        baseline = self.village()
        baseline.progress.story_pending = ""
        baseline.progress.unlocked.append("p0_03a_secours")
        normal = baseline.start_mission("p0_03a_secours")
        self.assertEqual(normal.inventory["player"]["potion"], 3)
        self.assertNotIn("initial_state", normal.recording())

    def test_validation_rejects_bad_actor_and_supply_configuration(self):
        project = self.project.to_dict()
        actors = project["exploration"]["sc_p0_cendres"]["actors"]
        wrong = deepcopy(project)
        wrong["exploration"]["sc_p0_cendres"]["actors"][0]["route"][1] = [9, 0]
        with self.assertRaises(RuleError):
            GameProject.from_dict(wrong, self.content)
        wrong = deepcopy(project)
        wrong["exploration"]["sc_p0_cendres"]["actors"][0]["id"] = "maison"
        with self.assertRaises(RuleError):
            GameProject.from_dict(wrong, self.content)
        wrong = deepcopy(project)
        wrong["battle_support"][0]["mission"] = "unknown"
        with self.assertRaises(RuleError):
            GameProject.from_dict(wrong, self.content)
        self.assertGreaterEqual(len(actors), 3)


if __name__ == "__main__":
    unittest.main()

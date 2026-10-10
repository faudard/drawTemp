"""Unified lifecycle integration: story, campaign, replay and strategic fronts."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError
from sporebound.player_session import PlayerSession


class UnifiedSessionTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.load(
            Path(DEFAULT_CONTENT).with_suffix(".game.json"), self.content)

    def session(self, campaign="main"):
        return GameSession.new(self.content, self.project, campaign, seed=17)

    def test_story_choice_checkpoint_and_mission_unlocks(self):
        session = self.session("relique")
        self.assertEqual(session.active_scene()["id"], "oath")
        self.assertEqual(session.available_missions(), [])
        session.choose_story_option("guard")
        self.assertEqual(session.active_scene()["id"], "oath_reward")
        session.choose_story_option("provisions")
        self.assertIsNone(session.active_scene())
        self.assertEqual(session.progress.gold, 25)
        self.assertEqual(session.available_missions(), ["crown"])
        with TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            session.save(path)
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(restored.progress, session.progress)
            self.assertEqual(restored.recording(), session.recording())

    def test_mid_combat_save_is_replayed_not_applied_to_campaign(self):
        session = self.session()
        battle = session.start_mission("garden")
        self.assertIs(battle, session.active_battle)
        self.assertFalse(session.finalized)
        self.assertEqual(session.progress.completed, [])
        session.execute({"kind": "end", "facing": [0, 1]})
        with TemporaryDirectory() as folder:
            path = Path(folder) / "combat.json"
            session.save(path)
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(restored.mode, "battle")
            self.assertEqual(restored.battle.digest(), session.battle.digest())
            self.assertEqual(restored.battle.commands, session.battle.commands)
            self.assertEqual(restored.progress.completed, [])
            restored.execute({"kind": "end", "facing": [0, 1]})
            self.assertEqual(restored.progress.completed, [])

    def test_rejected_command_rolls_back_entire_session(self):
        session = self.session()
        session.start_mission("garden")
        original = session.recording()
        with self.assertRaises(RuleError):
            session.execute({"kind": "nonexistent_action"})
        self.assertEqual(session.recording(), original)
        with self.assertRaises(RuleError):
            session.choose_story_option("missing")
        self.assertEqual(session.recording(), original)
        with self.assertRaises(RuleError):
            session.return_to_campaign()
        session.abandon_encounter()
        self.assertEqual(session.mode, "campaign")

    def test_victory_reward_and_story_route_settle_only_once(self):
        session = self.session()
        session.start_mission("garden")
        # Isolate the completion boundary, like the legacy PlayerSession tests.
        # Do not serialize this manually resolved Battle: only command-driven
        # results can generate a verified tactical replay.
        session.battle.result = "victory"
        session._settle()
        self.assertEqual(session.progress.completed, ["garden"])
        self.assertEqual(session.progress.story_pending, "council")
        xp = {key: hero.xp for key, hero in session.progress.heroes.items()}
        gold = session.progress.gold
        session._settle()
        self.assertEqual(session.progress.completed, ["garden"])
        self.assertEqual({key: hero.xp for key, hero in session.progress.heroes.items()}, xp)
        self.assertEqual(session.progress.gold, gold)
        self.assertTrue(session.finalized)
        session.return_to_campaign()
        session.choose_story_option("tunnel")
        self.assertEqual(session.available_missions(), ["escape"])
        self.assertEqual(session.progress.story_flags["chosen_route"], "tunnel")

    def test_checkpoint_corruption_and_identity_mismatch(self):
        session = self.session()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            session.save(path)
            changed = deepcopy(self.project)
            changed.title += " edition"
            with self.assertRaises(RuleError):
                GameSession.load(path, self.content, changed)
            row = json.loads(path.read_text(encoding="utf-8"))
            row["progress"]["gold"] = 500
            path.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaises(RuleError):
                GameSession.load(path, self.content, self.project)

    def test_multifront_journal_roundtrip(self):
        session = self.session()
        session.progress.unlocked.append("hold")
        session.start_fronts(
            {"garden": "garden", "defense": "hold"}, "garden",
            specs={"garden": {"strength": 8, "opposition": 8},
                   "defense": {"strength": 9, "opposition": 11,
                               "doctrine": "assault"}})
        session.set_doctrine("defense", "assault")
        session.advance_fronts()
        session.switch_front("defense")
        session.execute({"kind": "end", "facing": [0, 1]})
        with TemporaryDirectory() as folder:
            path = Path(folder) / "fronts.json"
            session.save(path)
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(restored.mode, "fronts")
            self.assertEqual(restored.fronts.digest(), session.fronts.digest())
            self.assertEqual(restored.fronts.history, session.fronts.history)
            self.assertEqual(restored.progress, session.progress)
            with self.assertRaises(RuleError):
                restored.switch_front("missing")

    def test_offscreen_strategic_victory_does_not_grant_campaign_reward(self):
        session = self.session()
        session.progress.unlocked.append("hold")
        session.start_fronts(
            {"garden": "garden", "other": "hold"}, "garden",
            specs={"garden": {"strength": 8, "opposition": 8},
                   "other": {"strength": 8, "opposition": 1,
                             "doctrine": "assault"}})
        session.advance_fronts()
        self.assertEqual(session.fronts.timeline.fronts["other"]["status"], "victory")
        self.assertEqual(session.progress.completed, [])
        self.assertEqual(session.settled_fronts, set())

    def test_legacy_player_slots_remain_distinct(self):
        with TemporaryDirectory() as folder:
            legacy = PlayerSession(self.content, self.project, Path(folder) / "game.json")
            legacy.new_game("main", 1)
            self.assertEqual(legacy.progress.completed, [])
            session = self.session()
            session.save(Path(folder) / "unified.json")
            old = PlayerSession(self.content, self.project, Path(folder) / "game.json")
            old.load_game("main", 1)
            self.assertEqual(old.progress.unlocked, ["garden"])


if __name__ == "__main__":
    unittest.main()

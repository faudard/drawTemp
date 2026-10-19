"""R35.B: faction receipts and one-claim-per-day canonical campaign rewards."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from tests_standalone.test_r35_living_world import fixture
from sporebound.living_world import EXTENSION


def with_quests():
    content, project = fixture()
    data = project.extensions[EXTENSION]["data"]
    data["factions"] = [{"id": "guild", "initial": 0}]
    data["daily_quests"] = [{
        "id": "delivery", "faction": "guild",
        "min_reputation": -10, "start_minute": 480,
        "end_minute": 1000, "completion_flag": "delivery_day",
        "reward_gold": 10, "reputation_delta": 3}]
    project.validate(content)
    return content, project


class FactionQuestTests(unittest.TestCase):
    def test_reputation_events_are_idempotent_and_saveable(self):
        content, project = with_quests()
        session = GameSession.new(content, project, "main")
        self.assertTrue(session.living_world_reputation_event("guild", 5, "helped"))
        self.assertFalse(session.living_world_reputation_event("guild", 5, "helped"))
        self.assertEqual(session.living_world_state()["reputation"]["guild"], 5)
        with self.assertRaises(RuleError):
            session.living_world_reputation_event("guild", -1, "helped")
        with self.assertRaises(RuleError):
            session.living_world_reputation_event("guild", 99, "overflow")
        with TemporaryDirectory() as temp:
            path = Path(temp) / "faction.json"
            session.save(path)
            restored = GameSession.load(path, content, project)
            self.assertEqual(restored.recording(), session.recording())
            self.assertFalse(restored.living_world_reputation_event("guild", 5, "helped"))
        invalid = deepcopy(session.recording())
        invalid["living_world"]["events"]["helped"]["delta"] = "five"
        invalid["digest"] = digest({k: v for k, v in invalid.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(invalid, content, project)

    def test_daily_completion_requires_current_day_flag_and_awards_once(self):
        content, project = with_quests()
        session = GameSession.new(content, project, "main")
        gold = session.progress.gold
        session.progress.story_flags["delivery_day"] = 0
        with self.assertRaises(RuleError):
            session.living_world_finish_daily_quest("delivery")
        session.living_world_advance(2)
        self.assertTrue(session.living_world_state()["daily_quests"][0]["ready"])
        self.assertTrue(session.living_world_finish_daily_quest("delivery"))
        self.assertFalse(session.living_world_finish_daily_quest("delivery"))
        self.assertEqual(session.progress.gold, gold + 10)
        self.assertEqual(session.living_world_state()["reputation"]["guild"], 3)
        checkpoint = session.recording()
        restored = GameSession.from_recording(checkpoint, content, project)
        self.assertFalse(restored.living_world_finish_daily_quest("delivery"))
        self.assertEqual(restored.progress.gold, gold + 10)
        restored.living_world_advance((1440 - 480) * 2)
        self.assertEqual(restored.living_world_state()["day"], 1)
        restored.living_world_advance(480 * 2)
        with self.assertRaises(RuleError):
            restored.living_world_finish_daily_quest("delivery")
        restored.progress.story_flags["delivery_day"] = 1
        self.assertTrue(restored.living_world_finish_daily_quest("delivery"))
        self.assertEqual(restored.progress.gold, gold + 20)
        self.assertEqual(restored.living_world_state()["reputation"]["guild"], 6)

    def test_quest_schema_and_claims_are_validated(self):
        content, project = with_quests()
        data = project.extensions[EXTENSION]["data"]
        bad = deepcopy(data)
        bad["daily_quests"][0]["faction"] = "missing"
        project.extensions[EXTENSION]["data"] = bad
        with self.assertRaises(RuleError):
            project.validate(content)
        project.extensions[EXTENSION]["data"] = data
        session = GameSession.new(content, project, "main")
        forged = session.recording()
        forged["living_world"]["claimed"]["delivery"] = 10
        forged["digest"] = digest({k: v for k, v in forged.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, content, project)


if __name__ == "__main__":
    unittest.main()

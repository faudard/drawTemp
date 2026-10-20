"""R45.A headless crafting and backwards-compatibility contract."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.living_world import EXTENSION
from sporebound.model import RuleError
from tests_standalone.test_r35_commerce import merchant_fixture


def crafting_fixture():
    content, project = merchant_fixture()
    project.extensions[EXTENSION]["data"]["recipes"] = [{
        "id": "brew_elixir", "npc": "merchant", "scene": "arrival",
        "activity": "trade", "faction": "guild", "min_reputation": 0,
        "inputs": [{"item": "herb", "quantity": 2}],
        "outputs": [{"item": "elixir", "quantity": 1}],
        "gold_cost": 4, "daily_limit": 2}]
    project.validate(content)
    return content, project


class R45CraftingTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = crafting_fixture()
        self.session = GameSession.new(self.content, self.project, "main")
        self.session.progress.gold = 100
        self.session.progress.story_flags["market_open"] = True

    def test_trade_craft_once_and_checkpoint_roundtrip(self):
        s = self.session
        s.living_world_advance(2)
        self.assertEqual(s.living_world_state()["recipes"][0]["remaining_today"], 2)
        self.assertTrue(s.living_world_trade(
            "village_shop", "herb", "buy", 4, "herb-purchase"))
        self.assertTrue(s.living_world_craft("brew_elixir", 2, "brew-once"))
        self.assertEqual((s.progress.gold, s.progress.inventory["herb"],
                          s.progress.inventory["elixir"]), (64, 0, 2))
        self.assertEqual(s.living_world_state()["recipes"][0]["remaining_today"], 0)
        checkpoint = s.recording()
        self.assertFalse(s.living_world_craft("brew_elixir", 2, "brew-once"))
        self.assertEqual(s.recording(), checkpoint)
        with TemporaryDirectory() as tmp:
            savefile = Path(tmp) / "save.json"
            s.save(savefile)
            loaded = GameSession.load(savefile, self.content, self.project)
            self.assertEqual(loaded.recording(), checkpoint)
            self.assertFalse(loaded.living_world_craft(
                "brew_elixir", 2, "brew-once"))
        self.assertEqual(GameProject.from_dict(
            self.project.to_dict(), self.content).to_dict(),
            self.project.to_dict())

    def test_failures_are_atomic_and_reputation_gated(self):
        s = self.session
        with self.assertRaises(RuleError):
            s.living_world_craft("brew_elixir", 1, "closed")
        s.living_world_advance(2)
        before = s.recording()
        for recipe, qty, receipt in (
            ("brew_elixir", True, "bool"),
            ("brew_elixir", 0, "zero"),
            ("brew_elixir", 3, "limit"),
            ("brew_elixir", 1, ""),
            ("missing", 1, "unknown"),
            ("brew_elixir", 1, "no-material")):
            with self.subTest(receipt=receipt), self.assertRaises(RuleError):
                s.living_world_craft(recipe, qty, receipt)
            self.assertEqual(s.recording(), before)
        s.progress.inventory["herb"] = 4
        self.assertTrue(s.living_world_craft("brew_elixir", 1, "first"))
        before = s.recording()
        with self.assertRaises(RuleError):
            s.living_world_craft("brew_elixir", 2, "first")
        self.assertEqual(s.recording(), before)
        s.living_world_reputation_event("guild", -10, "ban")
        before = s.recording()
        with self.assertRaises(RuleError):
            s.living_world_craft("brew_elixir", 1, "banned")
        self.assertEqual(s.recording(), before)

    def test_day_rollover_resets_quota_not_receipts(self):
        s = self.session
        s.living_world_advance(2)
        s.progress.inventory["herb"] = 8
        s.living_world_craft("brew_elixir", 2, "day-zero")
        with self.assertRaises(RuleError):
            s.living_world_craft("brew_elixir", 1, "excess")
        s.living_world_advance(1440 * 2)
        self.assertEqual(s.living_world_state()["day"], 1)
        self.assertEqual(s.living_world_state()["recipes"][0]["remaining_today"], 2)
        self.assertTrue(s.living_world_craft("brew_elixir", 1, "day-one"))
        self.assertFalse(s.living_world_craft("brew_elixir", 2, "day-zero"))
        self.assertEqual(GameSession.from_recording(
            s.recording(), self.content, self.project).recording(),
            s.recording())

    def test_schema_and_receipt_corruption_fail_closed(self):
        for kind in ("unknown", "bool", "schedule", "overlap", "duplicate",
                     "limit"):
            project = deepcopy(self.project)
            data = project.extensions[EXTENSION]["data"]
            r = data["recipes"][0]
            if kind == "unknown":
                r["inputs"][0]["item"] = "unregistered"
            elif kind == "bool":
                r["inputs"][0]["quantity"] = True
            elif kind == "schedule":
                r["activity"] = "missing_activity"
            elif kind == "overlap":
                r["outputs"][0]["item"] = "herb"
            elif kind == "duplicate":
                data["recipes"].append(deepcopy(r))
            elif kind == "limit":
                r["daily_limit"] = 1001
            with self.subTest(kind=kind), self.assertRaises(RuleError):
                project.validate(self.content)
        s = self.session
        s.living_world_advance(2)
        s.progress.inventory["herb"] = 4
        s.living_world_craft("brew_elixir", 1, "receipt")
        original = s.recording()
        for field, value in (("sequence", 4), ("day", 90),
                             ("quantity", 3), ("recipe", "absent")):
            forged = deepcopy(original)
            forged["living_world"]["crafts"]["receipt"][field] = value
            forged["digest"] = digest({k: v for k, v in forged.items()
                                        if k != "digest"})
            with self.subTest(field=field), self.assertRaises(RuleError):
                GameSession.from_recording(forged, self.content, self.project)
        self.assertEqual(s.recording(), original)

    def test_legacy_r35_checkpoint_does_not_change_shape(self):
        content, project = merchant_fixture()
        s = GameSession.new(content, project, "main")
        self.assertNotIn("crafts", s.recording()["living_world"])
        self.assertNotIn("recipes", s.living_world_state())
        self.assertEqual(GameSession.from_recording(
            s.recording(), content, project).recording(), s.recording())


if __name__ == "__main__":
    unittest.main()

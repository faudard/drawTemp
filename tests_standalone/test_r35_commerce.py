"""R35.B2: daily merchant stock and canonical GameSession transaction gates."""
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from sporebound.game_session import GameSession, digest
from sporebound.living_world import EXTENSION
from sporebound.model import RuleError
from tests_standalone.test_r35_factions_quests import with_quests


def merchant_fixture():
    content, project = with_quests()
    data = project.extensions[EXTENSION]["data"]
    data["factions"][0]["initial"] = 2
    data["shops"] = [{
        "id": "village_shop", "npc": "merchant", "scene": "arrival",
        "activity": "trade", "faction": "guild", "min_reputation": 0,
        "items": [
            {"id": "herb", "buy_price": 7, "sell_price": 3,
             "daily_stock": 5},
            {"id": "elixir", "buy_price": 40, "sell_price": 10,
             "daily_stock": 2}
        ]
    }]
    project.validate(content)
    return content, project


class R35MerchantTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = merchant_fixture()
        self.session = GameSession.new(
            self.content, self.project, "main", seed=47)
        self.session.progress.gold = 100
        self.session.progress.story_flags["market_open"] = True

    def test_buy_sell_daily_stock_and_save_load(self):
        s = self.session
        self.assertFalse(s.living_world_state()["shops"][0]["open"])
        with self.assertRaises(RuleError):
            s.living_world_trade("village_shop", "herb", "buy", 1, "early")
        self.assertEqual(s.progress.gold, 100)
        s.living_world_advance(2)
        self.assertTrue(s.living_world_state()["shops"][0]["open"])
        self.assertTrue(s.living_world_trade(
            "village_shop", "herb", "buy", 2, "purchase01"))
        self.assertFalse(s.living_world_trade(
            "village_shop", "herb", "buy", 2, "purchase01"))
        self.assertEqual((s.progress.gold, s.progress.inventory["herb"]), (86, 2))
        self.assertEqual(s.living_world_state()["shops"][0]["items"][0]["stock"], 3)
        self.assertTrue(s.living_world_trade(
            "village_shop", "herb", "sell", 1, "refund01"))
        self.assertEqual((s.progress.gold, s.progress.inventory["herb"]), (89, 1))
        self.assertEqual(s.living_world_state()["shops"][0]["items"][0]["stock"], 4)
        with TemporaryDirectory() as temp:
            file = Path(temp) / "checkpoint.json"
            s.save(file)
            restored = GameSession.load(file, self.content, self.project)
            self.assertEqual(restored.recording(), s.recording())
            self.assertEqual(
                restored.living_world_state()["shops"],
                s.living_world_state()["shops"])
            self.assertFalse(restored.living_world_trade(
                "village_shop", "herb", "buy", 2, "purchase01"))
            restored.living_world_advance((1440 - 480) * 2)
            self.assertEqual(restored.living_world_state()["day"], 1)
            self.assertEqual(restored.living_world_state()["shops"][0]["items"][0]["stock"], 5)

    def test_insufficient_funds_stock_sell_and_reputation_are_atomic(self):
        s = self.session
        s.living_world_advance(2)
        before = s.recording()
        for item, action, qty, tid in (
                ("elixir", "buy", 3, "oos"),
                ("elixir", "buy", 99, "qty"),
                ("elixir", "sell", 1, "noitem"),
                ("herb", "buy", True, "bool"),
                ("herb", "buy", 1, "",)):
            with self.subTest(tid=tid), self.assertRaises(RuleError):
                s.living_world_trade("village_shop", item, action, qty, tid)
            self.assertEqual(s.recording(), before)
        s.living_world_reputation_event("guild", -5, "shop_banned")
        with self.assertRaises(RuleError):
            s.living_world_trade("village_shop", "herb", "buy", 1, "banned")
        self.assertFalse(s.living_world_state()["shops"][0]["open"])

    def test_offscene_ct_and_condition_close_shop(self):
        s = self.session
        s.living_world_advance(2)
        s.progress.story_flags["market_open"] = False
        self.assertFalse(s.living_world_state()["shops"][0]["open"])
        with self.assertRaises(RuleError):
            s.living_world_trade("village_shop", "herb", "buy", 1, "closed")
        s.progress.story_flags["market_open"] = True
        s.progress.story_flags["portal_open"] = True
        s.route_transition("to_arena")
        with self.assertRaises(RuleError):
            s.living_world_trade("village_shop", "herb", "buy", 1, "in_battle")
        self.assertEqual(s.living_world_state()["ticks"], 2)

    def test_receipt_integrity_and_invalid_catalogue(self):
        s = self.session
        s.living_world_advance(2)
        s.living_world_trade("village_shop", "herb", "buy", 2, "r1")
        original = s.recording()
        bad = deepcopy(original)
        bad["living_world"]["trades"]["r1"]["total"] = 1
        bad["digest"] = digest({k: v for k, v in bad.items()
                                if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(bad, self.content, self.project)
        bad = deepcopy(self.project)
        bad.extensions[EXTENSION]["data"]["shops"][0]["items"][0]["sell_price"] = 999
        with self.assertRaises(RuleError):
            bad.validate(self.content)
        with self.assertRaises(RuleError):
            s.living_world_trade("village_shop", "herb", "sell", 2, "r1")
        self.assertEqual(s.recording(), original)


if __name__ == "__main__":
    unittest.main()

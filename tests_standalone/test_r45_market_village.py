"""R45.C: production-grade seven-day commerce regression and Player E2E."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.r45_market_village import (
    export_village, seven_day_gate, village_project)
from drawtemp.sdk.simulation import Simulation, SimulationError, thaw
from sporebound.game_session import GameSession, digest
from sporebound.game_project import GameProject
from sporebound.living_world import EXTENSION
from sporebound.model import RuleError


class R45VillageWeekTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = village_project()

    def test_7_days_transactions_stock_reputation_resume_and_offfocus(self):
        result = seven_day_gate()
        self.assertEqual(len(result["days"]), 7)
        self.assertEqual([day["gold"] for day in result["days"]],
                         [112, 124, 136, 148, 160, 172, 184])
        self.assertEqual([day["reputation"] for day in result["days"]],
                         [1, 2, 3, 4, 5, 6, 7])
        self.assertTrue(all(day["delivered"] for day in result["days"]))
        self.assertEqual(result["ending_day"], 7)
        self.assertEqual(result["ending_gold"], 184)
        self.assertEqual(result["trades"], 21)
        self.assertEqual(result["crafts"], 7)

    def test_exported_project_is_a_real_player_pair(self):
        with TemporaryDirectory() as temp:
            content_file, project_file = export_village(temp)
            self.assertTrue(content_file.exists())
            self.assertTrue(project_file.exists())
            from sporebound.model import Content
            loaded_content = Content.load(content_file)
            loaded_project = GameProject.load(project_file, loaded_content)
            self.assertEqual(loaded_content.to_dict(), self.content.to_dict())
            self.assertEqual(loaded_project.to_dict(), self.project.to_dict())

    def test_player_buy_craft_deliver_sell_and_verified_slot(self):
        with TemporaryDirectory() as temp:
            player = PlayerController(
                self.content, self.project, "main", Path(temp), seed=45)
            state = player.new_game()
            self.assertEqual(state["screen"], "exploration")
            self.assertEqual(state["economy"]["gold"], 100)
            self.assertTrue(state["economy"]["shops"][0]["open"])
            self.assertEqual(state["economy"]["day"], 0)
            player.market_trade("village_shop", "herb", "buy", 2)
            player.market_trade("village_shop", "elixir", "buy", 1)
            player.market_craft("brew_elixir")
            before_claim = player.state()
            self.assertTrue(before_claim["economy"]["daily_quests"][0]["can_deliver"])
            player.market_deliver("guild_delivery")
            player.market_trade("village_shop", "elixir", "sell", 1)
            self.assertEqual(player.state()["economy"]["gold"], 112)
            self.assertFalse(player.state()["economy"]["daily_quests"][0]["can_deliver"])
            recorded = player.session.recording()
            player.save(1)
            player.load(1)
            self.assertEqual(player.session.recording(), recorded)
            with self.assertRaises(ValueError):
                player.market_deliver("guild_delivery")
            self.assertEqual(player.session.recording(), recorded)
            player.market_next_morning()
            self.assertEqual(player.state()["economy"]["day"], 1)
            self.assertEqual(player.state()["economy"]["gold"], 112)
            self.assertTrue(player.state()["economy"]["shops"][0]["open"])
            # Receipt IDs derive from ledger lengths even after load.
            player.market_trade("village_shop", "herb", "buy", 1)
            saved_trades = player.session.recording()["living_world"]["trades"]
            self.assertEqual(len(saved_trades), 4)
            self.assertEqual(len(set(saved_trades)), 4)

    def test_all_invalid_delivery_paths_preserve_save_digest(self):
        session = GameSession.new(self.content, self.project, "main")
        before = session.recording()
        with self.assertRaises(RuleError):
            session.living_world_deliver_daily_quest("guild_delivery")
        self.assertEqual(session.recording(), before)
        session.living_world_trade("village_shop", "herb", "buy", 2, "buy_1")
        session.living_world_craft("brew_elixir", 1, "craft_1")
        self.assertTrue(session.living_world_deliver_daily_quest("guild_delivery"))
        history = session.recording()
        self.assertFalse(session.living_world_deliver_daily_quest("guild_delivery"))
        self.assertEqual(session.recording(), history)
        session.living_world_advance(1440 * 2)
        with self.assertRaises(RuleError):
            session.living_world_deliver_daily_quest("guild_delivery")
        self.assertEqual(session.progress.gold, 114)

    def test_schema_rejects_bad_start_or_unknown_delivery_and_keeps_legacy(self):
        for bad_value in (True, -1, 100001, "100"):
            corrupt = deepcopy(self.project)
            corrupt.extensions[EXTENSION]["data"]["starting_gold"] = bad_value
            with self.subTest(value=bad_value), self.assertRaises(RuleError):
                corrupt.validate(self.content)
        for broken in ("item", "count", "half", "scene"):
            corrupt = deepcopy(self.project)
            quest = corrupt.extensions[EXTENSION]["data"]["daily_quests"][0]
            if broken == "item":
                quest["delivery_item"] = "not_a_known_item"
            elif broken == "count":
                quest["delivery_quantity"] = 0
            elif broken == "scene":
                quest["delivery_scene"] = "unknown_scene"
            else:
                del quest["delivery_item"]
            with self.subTest(broken=broken), self.assertRaises(RuleError):
                corrupt.validate(self.content)
        from tests_standalone.test_r35_commerce import merchant_fixture
        old_content, old_project = merchant_fixture()
        self.assertNotIn("starting_gold",
                         old_project.extensions[EXTENSION]["data"])
        legacy = GameSession.new(old_content, old_project, "main")
        self.assertEqual(legacy.progress.gold, 0)
        self.assertEqual(GameSession.from_recording(
            legacy.recording(), old_content, old_project).recording(),
            legacy.recording())

    def test_delivery_cannot_be_claimed_from_remote_scene(self):
        s = GameSession.new(self.content, self.project, "main")
        s.living_world_trade("village_shop", "herb", "buy", 2, "herbs_remote")
        s.living_world_craft("brew_elixir", 1, "craft_remote")
        s.route_transition("to_outskirts")
        saved = s.recording()
        with self.assertRaises(RuleError):
            s.living_world_deliver_daily_quest("guild_delivery")
        self.assertEqual(s.recording(), saved)
        self.assertFalse(s.living_world_state(scene="outskirts")[
            "daily_quests"][0]["delivery_open"])
        s.route_transition("to_market")
        self.assertTrue(s.living_world_deliver_daily_quest("guild_delivery"))

    def test_forged_delivery_receipt_or_gold_mismatch_cannot_skip_digest(self):
        s = GameSession.new(self.content, self.project, "main")
        s.living_world_trade("village_shop", "herb", "buy", 2, "purchase")
        s.living_world_craft("brew_elixir", 1, "craft")
        s.living_world_deliver_daily_quest("guild_delivery")
        original = s.recording()
        bad = deepcopy(original)
        bad["living_world"]["claimed"]["guild_delivery"] = 6
        bad["digest"] = digest({key: value for key, value in bad.items()
                               if key != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(bad, self.content, self.project)
        self.assertEqual(s.recording(), original)


if __name__ == "__main__":
    unittest.main()

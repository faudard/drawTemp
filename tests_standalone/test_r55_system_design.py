"""R55 System Designer: graph invariants, atomic trading, save/replay and history."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.system_design_authoring import (
    apply_system_design, forecast_system_design, preview_system_design)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from sporebound.system_design import EXTENSION, SystemEconomy, validate_systems
from tests_standalone.test_r25_scene_router import scene_fixture


def system_spec():
    return {
        "version": 1,
        "resources": [
            {"id": "ore", "initial": 8, "capacity": 20},
            {"id": "ingot", "initial": 0, "capacity": 20},
            {"id": "gem", "initial": 0, "capacity": 10},
        ],
        "producers": [
            {"id": "smelter", "inputs": {"ore": 2},
             "outputs": {"ingot": 1}, "interval": 2},
            {"id": "jeweler", "inputs": {"ingot": 2},
             "outputs": {"gem": 1}, "interval": 3},
        ],
        "merchants": [
            {"id": "trader", "resource": "ingot",
             "scene": "arrival", "buy_price": 5, "sell_price": 2},
        ],
        "quests": [
            {"id": "delivery", "resource": "ingot",
             "quantity": 2, "flag": "delivered_ingots"},
        ],
    }


def fixture():
    content, project = scene_fixture()
    project.extensions[EXTENSION] = {
        "schema_version": 1, "data": system_spec(), "references": []}
    project.validate(content)
    return content, project


class R55SystemDesignerTests(unittest.TestCase):
    def test_typed_graph_rejects_cycles_invalid_schema_and_unbounded_amounts(self):
        spec = system_spec()
        self.assertEqual(validate_systems(spec, {"arrival"}), spec)
        for edit in (
                lambda x: x["producers"].append({
                    "id": "loop", "inputs": {"gem": 1},
                    "outputs": {"ore": 1}, "interval": 1}),
                lambda x: x["producers"][0].update(interval=True),
                lambda x: x["resources"][0].update(initial=-1),
                lambda x: x["resources"][0].update(capacity=0),
                lambda x: x["merchants"][0].update(scene="unknown"),
                lambda x: x.update(version=2),
                lambda x: x.update(extra="arbitrary_script"),
                lambda x: x["producers"][0].update(inputs={}),
                lambda x: x["producers"][0].update(outputs={"ingot": True}),
        ):
            with self.subTest(edit=edit), self.assertRaises(RuleError):
                altered = deepcopy(spec)
                edit(altered)
                validate_systems(altered, {"arrival"})

    def test_deterministic_production_order_conservation_and_preview(self):
        spec = system_spec()
        first = SystemEconomy(spec, {"arrival"})
        second = SystemEconomy(spec, {"arrival"})
        projection = first.preview(4)
        self.assertEqual(first.snapshot()["tick"], 0)
        self.assertEqual(projection["stocks"], {
            "ore": 4, "ingot": 2, "gem": 0})
        first.advance(4)
        for _ in range(4):
            second.advance(1)
        self.assertEqual(first.stocks, second.stocks)
        self.assertEqual(first.tick, second.tick)
        first.advance(2)
        self.assertEqual(first.stocks, {"ore": 2, "ingot": 1, "gem": 1})
        checkpoint = first.snapshot()
        copied = SystemEconomy(spec, {"arrival"})
        copied.restore(checkpoint)
        self.assertEqual(copied.snapshot(), checkpoint)
        with self.assertRaises(RuleError):
            copied.advance(True)
        with self.assertRaises(RuleError):
            copied.advance(257)
        self.assertEqual(copied.snapshot(), checkpoint)

    def test_session_canonical_trade_quest_and_reload(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=55)
        session.progress.gold = 100
        session.system_advance(4)
        self.assertEqual(session.system_state()["stocks"]["ingot"], 2)
        self.assertEqual(session.progress.inventory.get("ingot", 0), 0)
        self.assertTrue(session.system_trade("trader", "buy", 2, "purchase1"))
        self.assertEqual(session.progress.gold, 90)
        self.assertEqual(session.progress.inventory["ingot"], 2)
        self.assertEqual(session.system_state()["stocks"]["ingot"], 0)
        self.assertFalse(session.system_trade("trader", "buy", 2, "purchase1"))
        with self.assertRaises(RuleError):
            session.system_trade("trader", "buy", 1, "purchase1")
        before = session.recording()
        with self.assertRaises(RuleError):
            session.system_trade("trader", "buy", 1, "purchase2")
        self.assertEqual(session.recording(), before)
        self.assertTrue(session.system_fulfill("delivery"))
        self.assertEqual(session.progress.inventory["ingot"], 0)
        self.assertIs(session.progress.story_flags["delivered_ingots"], True)
        self.assertFalse(session.system_fulfill("delivery"))
        recorded = session.recording()
        restored = GameSession.from_recording(recorded, content, project)
        self.assertEqual(restored.recording(), recorded)
        self.assertEqual(restored.system_state(), session.system_state())

        # A rewritten stock with a recomputed top-level checksum must fail.
        tampered = deepcopy(recorded)
        tampered["systems"]["stocks"]["ingot"] += 1
        tampered["digest"] = digest({k: v for k, v in tampered.items()
                                     if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(tampered, content, project)
        tampered = deepcopy(recorded)
        tampered["progress"]["story_flags"].pop("delivered_ingots", None)
        tampered["digest"] = digest({k: v for k, v in tampered.items()
                                     if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(tampered, content, project)

    def test_atomic_sell_and_overflow_refusal(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main")
        session.progress.inventory["ingot"] = 1
        session.progress.gold = 10
        self.assertTrue(session.system_trade("trader", "sell", 1, "sale1"))
        self.assertEqual(session.progress.gold, 12)
        self.assertEqual(session.progress.inventory["ingot"], 0)
        self.assertEqual(session.system_state()["stocks"]["ingot"], 1)
        previous = session.recording()
        with self.assertRaises(RuleError):
            session.system_trade("trader", "sell", 1, "sale2")
        self.assertEqual(session.recording(), previous)

    def test_checkpoint_rejects_duplicate_receipts_and_unearned_resources(self):
        economy = SystemEconomy(system_spec(), {"arrival"})
        economy.advance(2)
        original = economy.snapshot()
        for mutate in (
                lambda x: x.update(tick=3),
                lambda x: x["stocks"].update(ore=99),
                lambda x: x["stocks"].update(ore=True),
                lambda x: x.update(tick=True),
                lambda x: x["journal"].append({"kind": "advance", "ticks": True}),
                lambda x: x["journal"].append({"kind": "magic", "ticks": 1}),
        ):
            invalid = deepcopy(original)
            mutate(invalid)
            with self.subTest(invalid=invalid), self.assertRaises(RuleError):
                economy.restore(invalid)
            self.assertEqual(economy.snapshot()["tick"], 2)

    def test_authoring_preview_commit_undo_redo_and_stale_revision(self):
        content, project = scene_fixture()
        session = AuthoringSession(content, project)
        before = session.snapshot().to_dict()
        proposal = preview_system_design(
            session, system_spec(), expected_revision=before["revision"])
        self.assertEqual(proposal.report["producer_count"], 2)
        self.assertEqual(session.snapshot().to_dict()["project"],
                         before["project"])
        apply_system_design(session, proposal)
        self.assertIn(EXTENSION, session.snapshot().to_dict()["project"]["extensions"])
        with self.assertRaises(ValueError):
            preview_system_design(session, system_spec(),
                                  expected_revision=before["revision"])
        session.undo()
        self.assertNotIn(EXTENSION,
                         session.snapshot().to_dict()["project"].get("extensions", {}))
        session.redo()
        self.assertIn(EXTENSION,
                      session.snapshot().to_dict()["project"]["extensions"])
        forecast = forecast_system_design(system_spec(), {"arrival"}, ticks=4)
        self.assertEqual(forecast["delta"]["ore"], -4)
        self.assertEqual(forecast["delta"]["ingot"], 2)

    def test_compact_tick_receipts_survive_long_player_session(self):
        economy = SystemEconomy(system_spec(), {"arrival"})
        for _ in range(600):
            economy.advance(1)
        state = economy.snapshot()
        self.assertEqual(state["tick"], 600)
        self.assertEqual(state["journal"], [{"kind": "advance", "ticks": 600}])
        restored = SystemEconomy(system_spec(), {"arrival"})
        restored.restore(state)
        self.assertEqual(restored.snapshot(), state)
        restored.advance(1)
        self.assertEqual(restored.snapshot()["journal"][0]["ticks"], 601)

    def test_fixed_player_movement_advances_once_and_failure_is_atomic(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=55)
        before = session.recording()
        with self.assertRaises(RuleError):
            session.route_realtime_step(5, 0)
        self.assertEqual(session.recording(), before)
        session.route_realtime_step(1, 0)
        self.assertEqual(session.system_state()["tick"], 1)
        self.assertEqual(session.system_state()["journal"],
                         [{"kind": "advance", "ticks": 1}])
        checkpoint = session.recording()
        resumed = GameSession.from_recording(checkpoint, content, project)
        self.assertEqual(resumed.recording(), checkpoint)
        resumed.route_realtime_step(0, 0)
        self.assertEqual(resumed.system_state()["tick"], 2)

        # Crossing the systems budget is refused *before* touching the
        # canonical movement journal and Campaign position.
        from sporebound.system_design import MAX_TICKS
        resumed._systems.tick = MAX_TICKS
        previous = resumed.route_realtime_state()
        with self.assertRaises(RuleError):
            resumed.route_realtime_step(0, 0)
        self.assertEqual(resumed.route_realtime_state(), previous)

    def test_multizone_market_quest_roundtrip_without_stock_duplication(self):
        content, project = fixture()
        project.story["scenes"].append({
            "id": "outpost", "title": "Avant-poste", "speaker": "Marchand",
            "text": "La route reste ouverte.",
            "choices": [{"id": "continue", "label": "Continuer"}],
        })
        project.exploration["outpost"] = deepcopy(project.exploration["arrival"])
        project.exploration["outpost"]["title"] = "Avant-poste"
        project.game_modes["scenes"]["outpost"] = {"preset": "action"}
        project.scene_routes["links"].extend([
            {"id": "to_outpost", "source": "arrival",
             "destination": "outpost", "spawn": [0, 1]},
            {"id": "to_market", "source": "outpost",
             "destination": "arrival", "spawn": [0, 1]},
        ])
        project.validate(content)
        session = GameSession.new(content, project, "main", seed=55)
        session.progress.gold = 100
        session.route_realtime_step(0, 0)
        session.route_realtime_step(0, 0)
        self.assertEqual(session.system_state()["stocks"]["ingot"], 1)
        session.route_transition("to_outpost")
        self.assertEqual(session.route_scene, "outpost")
        session.route_realtime_step(0, 0)
        session.route_realtime_step(0, 0)
        self.assertEqual(session.system_state()["stocks"]["ingot"], 2)
        with self.assertRaises(RuleError):
            session.system_trade("trader", "buy", 2, "offscene")
        checkpoint = session.recording()
        restored = GameSession.from_recording(checkpoint, content, project)
        self.assertEqual(restored.system_state(), session.system_state())
        restored.route_transition("to_market")
        self.assertTrue(restored.system_trade("trader", "buy", 2, "visit1"))
        self.assertTrue(restored.system_fulfill("delivery"))
        self.assertEqual(restored.progress.gold, 90)
        self.assertEqual(restored.progress.inventory["ingot"], 0)
        saved = restored.recording()
        again = GameSession.from_recording(saved, content, project)
        self.assertEqual(again.recording(), saved)
        self.assertFalse(again.system_trade("trader", "buy", 2, "visit1"))
        self.assertFalse(again.system_fulfill("delivery"))
        self.assertEqual(again.system_state()["stocks"]["ingot"], 0)
        self.assertEqual(again.progress.gold, 90)

    def test_legacy_save_is_unchanged_when_systems_are_disabled(self):
        content, project = scene_fixture()
        session = GameSession.new(content, project, "main")
        self.assertNotIn("systems", session.recording())
        with self.assertRaises(RuleError):
            session.system_state()
        with self.assertRaises(RuleError):
            session.system_advance(1)
        content2, project2 = fixture()
        fresh = GameSession.new(content2, project2, "main")
        incomplete = fresh.recording()
        incomplete.pop("systems")
        incomplete["digest"] = digest({k: v for k, v in incomplete.items()
                                        if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(incomplete, content2, project2)


if __name__ == "__main__":
    unittest.main()

"""End-to-end castle 2.8 gates: real commands, choices, endings, resume."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from examples.castle_vertical_slice import castle_blueprint, castle_content
from sporebound.model import Content, RuleError
from sporebound.tactical_rpg3 import tactical_rpg_rules
from sporebound.vertical_slice import CastleVerticalSlice


def compact_content():
    """Only speed up encounters, never manufacture a tactical result."""
    raw = castle_content().to_dict()
    for mission in raw["missions"]:
        if mission["id"] == "castle_courtyard":
            next(o for o in mission["objects"]
                 if o["id"] == "stone_drop")["pos"] = [2, 3]
        if mission["id"] == "castle_throne":
            mission["units"] = [u for u in mission["units"]
                                if u["id"] in {"captain", "engineer", "castellan"}]
            boss = next(u for u in mission["units"] if u["id"] == "castellan")
            boss.update(pos=[2, 3], hp=1, max_hp=1, speed=5)
    return Content.from_dict(raw, rules=tactical_rpg_rules())


def compact_blueprint():
    """Compact boss has no guard to stand down; preserve the intel treaty gate."""
    blueprint = castle_blueprint()
    blueprint["campaign"]["treaties"]["gate"].pop("final_stand_down")
    return blueprint


class CastleVerticalSliceTests(unittest.TestCase):
    def fresh(self):
        return CastleVerticalSlice(compact_content(), compact_blueprint(),
                                   seed=3, rules=tactical_rpg_rules())

    def throne_victory(self, game):
        game.switch("throne")
        game.execute({"kind": "start_battle"})
        game.execute({"kind": "act", "skill": "attack", "cell": [2, 3]})
        self.assertEqual(game.fronts.active.result, "victory")
        self.assertEqual(game.fronts.state()["campaign"]["status"], "victory")

    def test_preparation_squad_class_gear_and_departure_are_real(self):
        game = self.fresh()
        original = next(u for u in game.content.missions["castle_ram"].units
                        if u.id == "captain")
        game.set_job("captain", "vanguard")
        game.buy("sturdy_armor")
        game.equip("captain", "sturdy_armor")
        game.select_squad(["captain"])
        self.assertEqual(game.state()["gold"], 35)
        game.start("ram")
        captain = game.fronts.active.unit("captain")
        self.assertEqual(captain.max_hp, original.max_hp + 8)
        self.assertEqual(captain.defense, original.defense + 3)
        self.assertFalse(any(u.id == "engineer" for u in game.fronts.active.units))
        self.assertEqual(game.state()["chapter"], "approach")
        with self.assertRaises(RuleError):
            game.buy("swift_boots")

    def test_all_five_authored_approaches_are_valid(self):
        expected = {"ram": ("gate", "breach"),
                    "infiltration": ("walls", "breach"),
                    "tunnels": ("tunnels", "tunnels"),
                    "negotiation": ("supplies", "breach"),
                    "direct": ("supplies", "direct")}
        for approach, (front, route) in expected.items():
            with self.subTest(approach=approach):
                game = self.fresh()
                game.start(approach)
                self.assertEqual(game.fronts.timeline.focused, front)
                self.assertEqual(game.fronts.route_selected, route)
                with self.assertRaises(RuleError):
                    game.start(approach)

    def test_rejected_preparation_and_operations_do_not_mutate(self):
        game = self.fresh()
        initial = game.recording()
        with self.assertRaises(RuleError):
            game.equip("captain", "sturdy_armor")
        with self.assertRaises(RuleError):
            game.select_squad(["captain", "captain"])
        with self.assertRaises(RuleError):
            game.set_job("captain", "unknown")
        self.assertEqual(initial, game.recording())
        game.start("tunnels")
        initial = game.recording()
        with self.assertRaises(RuleError):
            game.switch("throne")
        with self.assertRaises(RuleError):
            game.execute({"kind": "not_a_command"})
        self.assertEqual(initial, game.recording())

    def test_mid_battle_checkpoint_roundtrip_and_tampering(self):
        game = self.fresh()
        game.set_job("engineer", "siege_engineer")
        game.start("ram")
        game.execute({"kind": "start_battle"})
        game.execute({"kind": "end"})
        with TemporaryDirectory() as folder:
            path = Path(folder) / "castle.json"
            game.save(path)
            restored = CastleVerticalSlice.load(
                path, compact_content(), compact_blueprint(),
                rules=tactical_rpg_rules())
            self.assertEqual(restored.recording(), game.recording())
            self.assertEqual(restored.state(), game.state())
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["fronts"]["operations"][0]["command"]["kind"] = "invalid"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(RuleError):
                CastleVerticalSlice.load(
                    path, compact_content(), compact_blueprint(),
                    rules=tactical_rpg_rules())

    def test_direct_route_needs_true_throne_victory(self):
        game = self.fresh()
        game.start("direct")
        self.assertIsNone(game.ending)
        self.assertEqual(game.fronts.logistics.supplies["player"], 2)
        self.assertFalse(game.fronts.active.result)
        self.throne_victory(game)
        self.assertEqual(game.ending, "victory")
        self.assertEqual(game.state()["chapter"], "epilogue")
        with self.assertRaises(RuleError):
            game.advance()
        restored = CastleVerticalSlice.from_recording(
            game.recording(), compact_content(), compact_blueprint(),
            rules=tactical_rpg_rules())
        self.assertEqual(restored.ending, "victory")

    def test_authenticated_diplomacy_and_partial_courtyard_yield_accord(self):
        game = self.fresh()
        game.start("negotiation")
        game.execute({"kind": "start_battle"})
        game.execute({"kind": "interact", "object": "supply_cache"})
        game.execute({"kind": "end"})
        game.switch("gate")
        game.execute({"kind": "start_battle"})
        game.negotiate("gate")
        self.assertEqual(game.fronts.timeline.fronts["gate"]["status"], "negotiated")
        game.switch("courtyard")
        game.execute({"kind": "start_battle"})
        game.execute({"kind": "interact", "object": "stone_drop"})
        game.execute({"kind": "end"})
        game.partial("courtyard")
        self.assertEqual(game.fronts.timeline.fronts["courtyard"]["status"], "partial")
        self.throne_victory(game)
        self.assertEqual(game.ending, "accord")
        self.assertEqual(
            CastleVerticalSlice.from_recording(
                game.recording(), compact_content(), compact_blueprint(),
                rules=tactical_rpg_rules()).ending, "accord")

    def test_defeat_is_explicit_and_persists(self):
        game = self.fresh()
        game.start("ram")
        game.concede()
        self.assertEqual(game.ending, "defeat")
        with self.assertRaises(RuleError):
            game.switch("walls")
        restored = CastleVerticalSlice.from_recording(
            game.recording(), compact_content(), compact_blueprint(),
            rules=tactical_rpg_rules())
        self.assertEqual(restored.ending, "defeat")

    def test_boss_has_real_phase_trigger(self):
        throne = castle_content().missions["castle_throne"]
        trigger = next(t for t in throne.triggers
                       if t["id"] == "castellan_second_phase")
        self.assertEqual(trigger["condition"], "hp_below")
        self.assertEqual(trigger["percent"], 50)
        self.assertIn("boss_phase", [a["kind"] for a in trigger["actions"]])
        self.assertIn("queue_wave", [a["kind"] for a in trigger["actions"]])


if __name__ == "__main__":
    unittest.main()

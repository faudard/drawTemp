"""Strategic logistics: finite reserves, travel, casualties and replay integrity."""
from copy import deepcopy
import unittest

from examples.siege_fronts import SIEGE_LINKS, siege_session
from examples.siege_scenarios import siege_content
from sporebound.fronts import MultiFrontSession
from sporebound.model import Content, RuleError


def reserve(uid, pos=(3, 6)):
    return {"id": uid, "name": uid, "team": "player", "pos": list(pos)}


class LogisticsTests(unittest.TestCase):
    def test_reserves_have_fixed_pool_capacity_and_arrival_turn(self):
        s = siege_session(focused="supplies", seed=8)
        convoy = s.send_reserves("walls", [reserve("shield_one")])
        self.assertEqual(convoy, "convoy_1")
        self.assertEqual(s.logistics.reserves["player"], 2)
        self.assertEqual(s.logistics.in_transit[0]["arrival"], 2)
        s.advance()
        self.assertNotIn("walls", s.pending_reinforcements)
        s.advance()
        self.assertEqual(s.logistics.in_transit, [])
        self.assertEqual(s.pending_reinforcements["walls"][0]["actors"][0]["id"],
                         "shield_one")
        self.assertEqual(s.timeline.fronts["walls"]["strength"], 5)
        s.switch("walls")
        self.assertEqual(len(s.active.encounter.pending), 1)
        s.execute({"kind": "start_battle"})
        self.assertIn("shield_one", [u.id for u in s.active.units])
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(),
                         s.digest())

    def test_transfer_relocates_real_actor_preserving_identity_and_stats(self):
        s = siege_session(seed=4)
        s.execute({"kind": "start_battle"})
        self.assertEqual(s.active.active_id, "captain")
        self.assertIn("supply_scout", [u.id for u in s.active.units])
        convoy = s.transfer_units("courtyard", {"supply_scout": [3, 6]})
        self.assertEqual(convoy, "convoy_1")
        self.assertNotIn("supply_scout", [u.id for u in s.active.units])
        self.assertEqual(s.timeline.fronts["supplies"]["strength"], 5)
        self.assertEqual(s.logistics.in_transit[0]["actors"][0]["hp"], 40)
        s.advance()
        self.assertEqual(len(s.logistics.in_transit), 1)
        s.advance()
        self.assertEqual(s.logistics.in_transit, [])
        s.switch("courtyard")
        s.execute({"kind": "start_battle"})
        moved = s.active.unit("supply_scout")
        self.assertEqual(moved.pos, (3, 6))
        self.assertEqual((moved.hp, moved.mp), (40, 12))
        self.assertEqual(MultiFrontSession.replay(s.recording()).state(),
                         s.state())

    def test_invalid_routes_and_budgets_are_strictly_rejected(self):
        config = {"capacity": 2, "reserves": {"player": 1},
                  "routes": [{"from": "reserve", "to": "gate", "turns": 1}]}
        for patch in (
            {"capacity": 0}, {"reserves": {"player": True}},
            {"routes": [{"from": "missing", "to": "gate", "turns": 1}]},
            {"routes": [{"from": "reserve", "to": "gate", "turns": 0}]},
            {"routes": config["routes"] + config["routes"]},
        ):
            with self.subTest(patch=patch), self.assertRaises(RuleError):
                MultiFrontSession(siege_content(), {"gate": "castle_ram"},
                                  "gate", logistics={**config, **patch})
        s = siege_session()
        with self.assertRaises(RuleError):
            s.send_reserves("walls", [reserve("a"), reserve("b"),
                                       reserve("c"), reserve("d")])
        self.assertEqual(s.logistics.reserves["player"], 3)
        self.assertEqual(s.logistics.in_transit, [])
        with self.assertRaises(RuleError):
            s.send_reserves("throne", [reserve("missing_route")])
        with self.assertRaises(RuleError):
            s.send_reserves("walls", [reserve("captain")])
        self.assertEqual(s.history, [])

    def test_unique_id_restrictions_include_pending_convoys(self):
        s = siege_session()
        s.send_reserves("walls", [reserve("shield_one")])
        before = s.digest()
        with self.assertRaises(RuleError):
            s.send_reserves("walls", [reserve("shield_one")])
        self.assertEqual(s.digest(), before)

    def test_active_actor_cannot_transfer_and_failed_order_is_atomic(self):
        s = siege_session()
        s.execute({"kind": "start_battle"})
        before = s.digest()
        with self.assertRaises(RuleError):
            s.transfer_units("courtyard", {"captain": [3, 6]})
        with self.assertRaises(RuleError):
            s.transfer_units("courtyard", {"supply_scout": [6, 2]})
        with self.assertRaises(RuleError):
            s.transfer_units("throne", {"supply_scout": [3, 6]})
        self.assertEqual(s.digest(), before)
        self.assertIn("supply_scout", [u.id for u in s.active.units])

    def test_no_one_escapes_battle_by_moving_all_players(self):
        s = siege_session()
        s.execute({"kind": "start_battle"})
        # An order evacuating all players necessarily includes the active hero.
        before = s.digest()
        with self.assertRaises(RuleError):
            s.transfer_units("courtyard",
                             {"captain": [3, 5], "engineer": [3, 6],
                              "supply_scout": [3, 7]})
        self.assertEqual(s.digest(), before)

    def test_convoys_lost_after_retreat_without_double_delivery(self):
        s = siege_session()
        s.send_reserves("gate", [reserve("late_guard")])
        s.set_doctrine("gate", "retreat")
        s.advance()
        self.assertEqual(s.timeline.fronts["gate"]["status"], "withdrawn")
        self.assertFalse(s.logistics.in_transit)
        self.assertNotIn("gate", s.pending_reinforcements)
        lost = [e for e in s.timeline.events if e["kind"] == "convoy_lost"]
        self.assertEqual(len(lost), 1)
        self.assertEqual(lost[0]["reason"], "front_inactive")
        with self.assertRaises(RuleError):
            s.switch("gate")
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(),
                         s.digest())

    def test_gate_defeat_causes_courtyard_losses_via_link_and_replays(self):
        data = siege_content().to_dict()
        gate = next(m for m in data["missions"] if m["id"] == "castle_ram")
        gate["protected_id"] = "captain"
        captain = next(u for u in gate["units"] if u["id"] == "captain")
        captain.update(hp=1, statuses={"poison": 500})
        content = Content.from_dict(data)
        config = {"capacity": 2, "reserves": {"player": 1},
                  "routes": [{"from": "reserve", "to": "courtyard", "turns": 1}]}
        s = MultiFrontSession(content, {"gate": "castle_ram",
                 "walls": "castle_ramparts", "courtyard": "castle_courtyard",
                 "supplies": "castle_supply", "throne": "castle_throne"},
                 "gate", links=SIEGE_LINKS, logistics=config)
        s.execute({"kind": "start_battle"})
        s.execute({"kind": "end"})
        self.assertEqual(s.active.result, "defeat")
        self.assertIn("gate_collapse", s.applied_links)
        self.assertEqual(s.timeline.fronts["courtyard"]["strength"], 7)
        s.switch("courtyard")
        self.assertEqual(s.active.unit("captain").hp, 37)
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(),
                         s.digest())

    def test_replay_detects_mutated_arrival_and_legacy_v2_still_loads(self):
        s = siege_session()
        s.send_reserves("walls", [reserve("shield_one")])
        s.advance()
        s.advance()
        recording = s.recording()
        self.assertEqual(recording["version"], 3)
        corrupt = deepcopy(recording)
        corrupt["operations"][0]["actors"][0]["pos"] = [4, 6]
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(corrupt)
        old = MultiFrontSession(siege_content(), {"gate": "castle_ram"}, "gate")
        legacy = old.recording()
        self.assertEqual(legacy["version"], 2)
        self.assertEqual(MultiFrontSession.replay(legacy).digest(),
                         old.digest())

    def test_example_demonstrates_both_convoy_types(self):
        s = siege_session()
        s.execute({"kind": "start_battle"})
        s.execute({"kind": "interact", "object": "supply_cache"})
        s.send_reserves("walls", [reserve("shield_reserve")])
        s.transfer_units("courtyard", {"supply_scout": [3, 6]})
        s.advance()
        s.advance()
        self.assertEqual(s.logistics.reserves["player"], 2)
        self.assertEqual(len(s.pending_reinforcements["walls"]), 1)
        self.assertEqual(len(s.pending_reinforcements["courtyard"]), 1)
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(),
                         s.digest())


if __name__ == "__main__":
    unittest.main()

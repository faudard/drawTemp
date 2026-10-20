"""Headless R67 research regression gate; no external network required."""
from copy import deepcopy
import unittest

from drawtemp.sdk.r67_network_feasibility import (
    AuthoritativeLab, SpikeError, run_spike, verify_journal, validate_command,
)


def command(player="p1", tick=1, seq=1, dx=1, dy=0):
    return {"version": 1, "player": player, "tick": tick,
            "seq": seq, "dx": dx, "dy": dy}


class R67FeasibilityTests(unittest.TestCase):
    def test_authority_ignores_client_position_and_rejects_spoofing(self):
        server = AuthoritativeLab()
        original = deepcopy(server.snapshot())
        for packet in ({**command(), "x": 100},
                       {**command(), "player": "p2"},
                       {**command(), "dx": 7},
                       {**command(), "version": 2},
                       {**command(), "dx": True},
                       {**command(), "dy": 1}):
            with self.assertRaises(SpikeError):
                server.submit("p1", packet)
        self.assertEqual(server.snapshot(), original)
        server.submit("p1", command())
        self.assertEqual(server.snapshot(), original)
        server.advance()
        self.assertEqual(server.positions["p1"], (2, 1))

    def test_stale_duplicate_future_and_replay_sequence_fail_closed(self):
        server = AuthoritativeLab()
        server.submit("p1", command())
        with self.assertRaises(SpikeError):
            server.submit("p1", command(seq=2))
        server.advance()
        for packet in (command(), command(tick=2, seq=1),
                       command(tick=18, seq=18)):
            with self.assertRaises(SpikeError):
                server.submit("p1", packet)
        server.submit("p2", command("p2", 2, 2, -1, 0))
        self.assertEqual(server.advance()["tick"], 2)

    def test_two_players_collision_bounds_and_replay(self):
        server = AuthoritativeLab()
        server.submit("p1", command("p1", 1, 1, -1, 0))
        server.submit("p2", command("p2", 1, 1, 1, 0))
        for _ in range(8):
            server.advance()
        self.assertEqual(server.positions, {"p1": (0, 1), "p2": (7, 4)})
        self.assertEqual(verify_journal(server.journal), server.snapshot()["digest"])
        changed = deepcopy(server.journal)
        changed[0]["commands"][0]["dx"] = 0
        with self.assertRaises(SpikeError):
            verify_journal(changed)
        changed = deepcopy(server.journal)
        changed[0]["commands"].append(command("p1", 1, 2))
        with self.assertRaises(SpikeError):
            verify_journal(changed)

    def test_packet_validation_exact_fields_and_types(self):
        for bad in (None, [], {**command(), "tick": True},
                    {**command(), "seq": -1}, {**command(), "player": 1},
                    {**command(), "dx": 0, "dy": -2}):
            with self.assertRaises(SpikeError):
                validate_command(bad, "p1")

    def test_seed_repeatability_and_loss_metrics(self):
        a = run_spike(seed=800, ticks=150, loss_percent=23,
                      latency_ticks=2, jitter_ticks=5, input_lead=4)
        self.assertEqual(a, run_spike(seed=800, ticks=150, loss_percent=23,
                                     latency_ticks=2, jitter_ticks=5, input_lead=4))
        self.assertTrue(a["replay_verified"])
        self.assertGreater(a["uplink_lost"], 0)
        self.assertGreater(a["downlink_lost"], 0)
        self.assertEqual(a["decision"], "REDUCE")
        self.assertFalse(a["production_multiplayer_ready"])

    def test_edge_conditions_zero_and_total_loss(self):
        zero = run_spike(ticks=50, loss_percent=0, latency_ticks=0,
                         jitter_ticks=0, input_lead=1, snapshot_interval=1)
        self.assertEqual(zero["final_client_lag_ticks"], {"p1": 0, "p2": 0})
        self.assertTrue(zero["replay_verified"])
        dead = run_spike(ticks=40, loss_percent=100)
        self.assertEqual(dead["final_client_lag_ticks"], {"p1": 40, "p2": 40})
        self.assertTrue(dead["replay_verified"])

    def test_invalid_probe_budget_is_rejected(self):
        for opts in ({"ticks": 1201}, {"ticks": True},
                     {"loss_percent": -1}, {"jitter_ticks": 13},
                     {"input_lead": 17}, {"seed": -1},
                     {"snapshot_interval": 0}):
            with self.assertRaises(SpikeError):
                run_spike(**opts)


if __name__ == "__main__":
    unittest.main()

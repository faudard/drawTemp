"""R71.C: cooperative certification harness and fail-closed release decision."""
from copy import deepcopy
import json
import unittest

from sporebound.connected_certification_r71 import (
    INITIAL, _hold, _start, certification_report, puzzle_reducer,
    run_coop_scene, run_rejoin_probe, run_overload_probe)
from sporebound.connected_lab_r71 import ConnectedLabSession
from sporebound.connected_service_r71 import FaultProfile
from sporebound.fixed_clock import _digest
from sporebound.model import RuleError


class R71CConnectedCertificationTests(unittest.TestCase):
    def test_two_clients_complete_one_gate_with_verifiable_server_replay(self):
        evidence = run_coop_scene(seed=71)
        self.assertEqual(evidence["kind"], "r71c-coop-scene-v1")
        self.assertTrue(evidence["puzzle_completed"])
        self.assertEqual(evidence["reward_or_unlock_count"], 1)
        self.assertEqual(evidence["accepted_holds"], 2)
        self.assertEqual(evidence["authoritative_tick"], 12)
        self.assertTrue(evidence["replay_verified"])
        self.assertEqual(evidence["link"]["counts"]["accepted"], 2)

    def test_packet_loss_duplication_and_reorder_are_seed_stable(self):
        profile = FaultProfile(latency_steps=2, jitter_steps=2,
                               drop_percent=30, duplicate_percent=30,
                               reorder_every=2, reorder_extra_steps=3)
        first = run_coop_scene(seed=81, faults=profile)
        second = run_coop_scene(seed=81, faults=profile)
        self.assertEqual(first, second)
        self.assertTrue(first["replay_verified"])
        self.assertIn(first["reward_or_unlock_count"], (0, 1))
        self.assertLessEqual(first["accepted_holds"], 2)
        self.assertEqual(first["link"]["counts"]["sent"], 2)
        self.assertNotIn("ticket", json.dumps(first))

    def test_delayed_inputs_miss_deadline_without_rollback_or_fake_success(self):
        report = run_coop_scene(seed=4, faults=FaultProfile(latency_steps=10))
        self.assertFalse(report["puzzle_completed"])
        self.assertEqual(report["accepted_holds"], 0)
        self.assertEqual(report["reward_or_unlock_count"], 0)
        self.assertEqual(report["link"]["counts"]["rejected"], 2)
        self.assertTrue(report["replay_verified"])

    def test_reconnection_resynchronizes_without_repeated_completion(self):
        recovery = run_rejoin_probe(seed=55)
        self.assertTrue(recovery["offline_rejected"])
        self.assertTrue(recovery["ticket_rotated"])
        self.assertTrue(recovery["rejoin_accepted"])
        self.assertTrue(recovery["puzzle_completed"])
        self.assertEqual(recovery["reward_or_unlock_count"], 1)
        self.assertTrue(recovery["replay_verified"])

    def test_overload_is_bounded_and_replay_remains_authoritative(self):
        stress = run_overload_probe(seed=71)
        self.assertTrue(stress["overflow_rejected"])
        self.assertEqual(stress["queued_before_rejection"], 256)
        self.assertEqual(stress["duplicates_rejected"], 255)
        self.assertEqual(stress["reward_or_unlock_count"], 0)
        self.assertEqual(stress["link"]["counts"]["accepted"], 1)
        self.assertTrue(stress["replay_verified"])

    def test_forged_replay_digest_cannot_hide_tick_divergence(self):
        service, _ = _start(71)
        self.assertTrue(service.receive(_hold("alice"))["accepted"])
        self.assertTrue(service.receive(_hold("bob"))["accepted"])
        for _ in range(12):
            service.advance()
        clean = service.recording()
        self.assertEqual(ConnectedLabSession.replay(
            clean, deepcopy(INITIAL), puzzle_reducer), service.snapshot())
        forged = deepcopy(clean)
        forged["journal"]["states"][7] = "f" * 64
        forged["journal"]["digest"] = _digest({
            k: v for k, v in forged["journal"].items() if k != "digest"})
        forged["digest"] = _digest({
            k: v for k, v in forged.items() if k != "digest"})
        with self.assertRaises(RuleError):
            ConnectedLabSession.replay(forged, deepcopy(INITIAL), puzzle_reducer)

    def test_unsupported_client_protocol_is_not_auto_migrated(self):
        service, _ = _start(71)
        info = {"version": 999, "session": "r71_private",
                "player": "alice", "last_tick": 0,
                "capabilities": ["commands_v1"]}
        with self.assertRaises(RuleError):
            service.connect(info, "any-old-ticket")
        before = service.snapshot()
        self.assertEqual(service.snapshot(), before)
        self.assertNotIn("ticket", json.dumps(service.diagnostics()))

    def test_release_decision_is_no_go_without_real_transport_and_r67_go(self):
        report = certification_report(seed=71)
        self.assertEqual(report["format"], "r71c-certification-lab-v1")
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["public_multiplayer_enabled"])
        self.assertTrue(report["checks"]["two_client_reliable_scene"])
        self.assertTrue(report["checks"]["authoritative_replay"])
        self.assertFalse(report["checks"]["r67_go"])
        self.assertFalse(report["checks"]["sender_bound_identity"])
        self.assertFalse(report["checks"]["two_physical_devices"])
        self.assertIn("cross_platform_ci_passed", report["blocking"])
        self.assertNotIn("ticket", json.dumps(report))
        self.assertNotIn("secret", json.dumps(report))
        self.assertEqual(report, certification_report(seed=71))

    def test_invalid_seed_is_rejected_before_mutation(self):
        for bad in (-1, True, 2**64, 1.25):
            with self.subTest(seed=bad), self.assertRaises(RuleError):
                run_coop_scene(seed=bad)


if __name__ == "__main__":
    unittest.main()

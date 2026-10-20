"""R72.A local-only cooperative contract and fault-injection tests."""
from copy import deepcopy
import unittest

from drawtemp.quality.r72_coop_probe import (
    Command, LocalCoopProbe, audit_local_probe, _digest,
)


class R72CoopProbeTests(unittest.TestCase):
    def setUp(self):
        self.probe = LocalCoopProbe("session-a", ("one", "two"))
        self.probe.connect("one")
        self.probe.connect("two")

    def action(self, player, action, dx=0, dy=0):
        p = self.probe
        cmd = Command(player, p.state()["last_seq"][player] + 1,
                      p.revision, action, dx, dy)
        return cmd, p.apply(cmd)

    def solve_puzzle(self):
        for player, moves in (("one", ((0, 1), (0, 1))),
                              ("two", ((0, 1), (0, 1)))):
            for dx, dy in moves:
                self.assertEqual(self.action(player, "move", dx, dy)[1].status,
                                 "accepted")
        self.assertTrue(self.probe.state()["puzzle_unlocked"])
        self.assertEqual(self.action("one", "move", 1, 0)[1].status, "accepted")
        self.assertEqual(self.action("two", "move", -1, 0)[1].status, "accepted")

    def test_lobby_membership_and_no_prejoin_mutation(self):
        p = LocalCoopProbe("local", ("one", "two"))
        cmd = Command("one", 1, 0, "move", 0, 1)
        self.assertEqual(p.apply(cmd).status, "offline")
        self.assertEqual(p.state()["revision"], 0)
        p.connect("one")
        self.assertEqual(p.apply(cmd).status, "accepted")
        with self.assertRaises(ValueError):
            p.connect("intruder")
        with self.assertRaises(ValueError):
            LocalCoopProbe("bad", ("one", "one"))

    def test_stale_conflict_rebase_and_sequence_gap(self):
        p = self.probe
        first = Command("one", 1, 0, "move", 0, 1)
        other = Command("two", 1, 0, "move", 0, 1)
        self.assertEqual(p.apply(first).status, "accepted")
        before = p.snapshot()
        self.assertEqual(p.apply(other).status, "stale_revision")
        self.assertEqual(p.snapshot(), before)
        self.assertEqual(p.apply(Command("two", 2, 1, "move", 0, 1)).status,
                         "invalid_sequence")
        self.assertEqual(p.apply(Command("two", 1, 1, "move", 0, 1)).status,
                         "accepted")

    def test_lost_ack_duplicate_and_sequence_payload_conflict(self):
        cmd, receipt = self.action("one", "move", 0, 1)
        state = self.probe.snapshot()
        self.probe.disconnect("one")
        self.assertEqual(self.probe.apply(cmd).status, "duplicate")
        self.assertEqual(self.probe.snapshot(), state)
        with self.assertRaises(ValueError):
            self.probe.apply(Command("one", cmd.seq, cmd.expected_revision,
                                     "move", 1, 0))

    def test_puzzle_boss_exactly_once_after_restore_and_reconnect(self):
        self.assertEqual(self.action("one", "attack")[1].status, "blocked")
        self.solve_puzzle()
        attack, receipt = self.action("one", "attack")
        self.assertEqual((receipt.status, receipt.reward_awarded),
                         ("accepted", False))
        self.probe.disconnect("two")
        checkpoint = self.probe.snapshot()
        restored = LocalCoopProbe.restore(checkpoint)
        self.assertEqual(restored.snapshot(), checkpoint)
        self.assertEqual(restored.apply(Command("two", 4, restored.revision,
                                                "attack")).status, "offline")
        restored.connect("two")
        second = Command("two", 4, restored.revision, "attack")
        finish = restored.apply(second)
        self.assertTrue(finish.reward_awarded)
        self.assertEqual(restored.state()["boss_hp"], 0)
        self.assertEqual(restored.state()["reward_count"], 1)
        self.assertEqual(restored.apply(second).status, "duplicate")
        self.assertEqual(restored.apply(attack).status, "duplicate")
        self.assertEqual(restored.state()["reward_count"], 1)
        final = LocalCoopProbe.restore(restored.snapshot())
        self.assertEqual(final.state(), restored.state())
        self.assertEqual(final.apply(second).status, "duplicate")
        self.assertEqual(final.state()["reward_count"], 1)

    def test_malformed_commands_are_atomic_and_fail_closed(self):
        before = self.probe.snapshot()
        for cmd in (Command("one", True, 0, "move", 0, 1),
                    Command("one", 1, 0, "move", 2, 0),
                    Command("one", 1, 0, "attack", 1, 0),
                    Command("one", 1, -1, "move", 0, 1),
                    Command("one", 1, 0, "arbitrary", 0, 0)):
            with self.subTest(cmd=cmd), self.assertRaises(ValueError):
                self.probe.apply(cmd)
            self.assertEqual(self.probe.snapshot(), before)
        self.assertEqual(self.action("one", "move", -1, 0)[1].status, "blocked")
        self.assertEqual(self.probe.snapshot(), before)

    def test_tamper_replay_and_version_refusal(self):
        self.action("one", "move", 0, 1)
        original = self.probe.snapshot()
        changed = deepcopy(original)
        changed["state"]["reward_count"] = 10
        with self.assertRaises(ValueError):
            LocalCoopProbe.restore(changed)
        # A digest is *not* a signature: even if recomputed, replay must fail.
        changed["digest"] = _digest({k: v for k, v in changed.items() if k != "digest"})
        with self.assertRaises(ValueError):
            LocalCoopProbe.restore(changed)
        changed = deepcopy(original)
        changed["events"][0]["expected_revision"] = 7
        changed["digest"] = _digest({k: v for k, v in changed.items() if k != "digest"})
        with self.assertRaises(ValueError):
            LocalCoopProbe.restore(changed)
        changed = deepcopy(original)
        changed["version"] = 2
        with self.assertRaises(ValueError):
            LocalCoopProbe.restore(changed)
        with self.assertRaises(ValueError):
            Command.parse({"player_id": "one", "seq": 1})

    def test_report_cannot_claim_network_release(self):
        report = audit_local_probe()
        self.assertTrue(report["source_checks_passed"])
        self.assertEqual(report["event_count"], 8)
        self.assertEqual(report["decision"], "NO-GO")
        self.assertFalse(report["release_ready"])
        self.assertGreater(len(report["missing_release_evidence"]), 0)


if __name__ == "__main__":
    unittest.main()

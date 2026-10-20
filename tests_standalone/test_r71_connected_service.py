"""R71.B in-process service, deterministic faults and client compatibility."""
from copy import deepcopy
import json
import unittest

from sporebound.connected_lab_r71 import ConnectedLabSession, encode_message
from sporebound.connected_service_r71 import (
    CAPABILITY, ConnectedLabService, FaultProfile,
    SimulatedSessionLink, plan_v0_hello_migration)
from sporebound.model import RuleError
from tests_standalone.test_r71_connected_lab import (
    TICKETS, KINDS, frame, make_lab, reducer)


def hello(player="alice", version=1, last_tick=0):
    return {"version": version, "session": "private_lab", "player": player,
            "last_tick": last_tick, "capabilities": [CAPABILITY]}


class ConnectedServiceR71BTests(unittest.TestCase):
    def test_two_clients_service_replay_and_offline_independence(self):
        lab = make_lab()
        service = ConnectedLabService(lab)
        a = service.connect(hello(), TICKETS["alice"])
        b = service.connect(hello("bob"), TICKETS["bob"])
        self.assertEqual((a["version"], b["capability"]), (1, CAPABILITY))
        link = SimulatedSessionLink(service, seed=71)
        link.send(encode_message(frame(), KINDS))
        link.send(encode_message(frame("bob", "hero_b", delta=3), KINDS))
        delivered = link.pump()
        self.assertEqual([x["result"]["accepted"] for x in delivered], [True, True])
        self.assertEqual(service.advance()["state"]["points"], {"hero_a": 1, "hero_b": 3})
        evidence = service.recording()
        self.assertEqual(ConnectedLabSession.replay(evidence, make_lab().snapshot()["state"],
                                                    reducer), lab.snapshot())
        metrics = json.dumps({"service": service.diagnostics(),
                              "link": link.diagnostics(), "recording": evidence})
        for secret in (*TICKETS.values(), a["ticket"], b["ticket"]):
            self.assertNotIn(secret, metrics)
        self.assertNotIn("player", json.dumps(service.diagnostics()))

    def test_handshake_fails_closed_and_explicit_legacy_upgrade(self):
        lab = make_lab()
        service = ConnectedLabService(lab)
        bad = [hello(version=0), hello(version=2), hello(version=True),
               {**hello(), "capabilities": []}, {**hello(), "unknown": True},
               {**hello(), "last_tick": True},
               {**hello(), "session": "not_this_one"}]
        for entry in bad:
            with self.subTest(entry=entry), self.assertRaises((RuleError, ValueError)):
                service.connect(entry, TICKETS["alice"])
        original = {"version": 0, "session": "private_lab",
                    "player": "alice", "cursor": 0}
        upgraded = plan_v0_hello_migration(original)
        self.assertEqual(original["version"], 0)
        self.assertEqual(upgraded, hello())
        self.assertEqual(service.connect(upgraded, TICKETS["alice"])["version"], 1)
        with self.assertRaises(RuleError):
            service.connect(hello(), TICKETS["alice"])  # ticket rotated
        self.assertEqual(service.diagnostics()["counts"]["handshake_rejected"], 8)

    def test_loss_duplication_and_reorder_with_reproducible_diagnostics(self):
        def scenario():
            svc = ConnectedLabService(make_lab())
            svc.connect(hello(), TICKETS["alice"])
            link = SimulatedSessionLink(svc, FaultProfile(
                latency_steps=1, drop_percent=0, duplicate_percent=100,
                reorder_every=2, reorder_extra_steps=3), seed=8)
            link.send(encode_message(frame(sequence=1, tick=3), KINDS))
            link.send(encode_message(frame(sequence=2, tick=3), KINDS))
            early = link.pump()
            self.assertEqual(early[0]["packet"], 2)
            self.assertFalse(early[0]["result"]["accepted"])
            later = link.pump(3)
            self.assertEqual(later[0]["packet"], 1)
            self.assertTrue(later[0]["result"]["accepted"])
            stats = link.diagnostics()
            self.assertEqual(stats["counts"]["duplicated"], 2)
            self.assertEqual(stats["counts"]["reordered"], 1)
            self.assertEqual(stats["counts"]["accepted"], 1)
            return early + later, stats, svc.diagnostics()
        self.assertEqual(scenario(), scenario())
        svc = ConnectedLabService(make_lab())
        svc.connect(hello(), TICKETS["alice"])
        dropped = SimulatedSessionLink(svc, FaultProfile(drop_percent=100), seed=5)
        dropped.send(encode_message(frame(), KINDS))
        self.assertEqual(dropped.pump(4), [])
        self.assertEqual(dropped.diagnostics()["counts"]["dropped"], 1)
        self.assertEqual(svc.advance()["state"]["points"]["hero_a"], 0)

    def test_rejoin_version_pinning_and_error_visibility_without_leaks(self):
        svc = ConnectedLabService(make_lab())
        auth = svc.connect(hello(), TICKETS["alice"])
        svc.disconnect("alice")
        denied = svc.receive(encode_message(frame(), KINDS))
        self.assertEqual(denied["code"], "HANDSHAKE_REQUIRED")
        auth2 = svc.connect(hello(), auth["ticket"])
        self.assertNotEqual(auth2["ticket"], auth["ticket"])
        self.assertTrue(svc.receive(encode_message(frame(), KINDS))["accepted"])
        self.assertFalse(svc.receive(encode_message(frame(), KINDS))["accepted"])
        self.assertEqual(svc.receive(b"broken")["code"], "MALFORMED_FRAME")
        self.assertEqual(svc.diagnostics()["counts"]["frames_rejected"], 3)
        metrics = svc.diagnostics()
        metrics["recent_events"].clear()
        self.assertTrue(svc.diagnostics()["recent_events"])

    def test_queue_bounds_atomicity_and_network_metrics(self):
        svc = ConnectedLabService(make_lab())
        svc.connect(hello(), TICKETS["alice"])
        frame1 = encode_message(frame(tick=5), KINDS)
        link = SimulatedSessionLink(svc, FaultProfile(
            latency_steps=2, duplicate_percent=100), seed=1)
        for _ in range(128):
            link.send(frame1)
        before = deepcopy(link.diagnostics())
        with self.assertRaises(RuleError):
            link.send(frame1)
        self.assertEqual(link.diagnostics(), before)
        self.assertEqual(link.diagnostics()["pending"], 256)
        link.pump(2)
        self.assertEqual(link.diagnostics()["pending"], 0)
        latency = link.diagnostics()["latency_steps"]
        self.assertEqual(latency, {"min": 2, "max": 2, "p95": 2})
        for profile in (FaultProfile(latency_steps=2),):
            self.assertEqual(profile.latency_steps, 2)
        with self.assertRaises(RuleError):
            FaultProfile(latency_steps=True)
        with self.assertRaises(RuleError):
            FaultProfile(drop_percent=101)
        with self.assertRaises(RuleError):
            link.pump(0)
        with self.assertRaises(RuleError):
            link.send(b" " * 4097)


if __name__ == "__main__":
    unittest.main()

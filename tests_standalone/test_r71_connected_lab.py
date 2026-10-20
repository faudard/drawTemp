"""R71.A lab-only protocol, authority, hostile frames and deterministic replay."""
from copy import deepcopy
import json
import unittest

from sporebound.connected_lab_r71 import (
    ConnectedLabSession, decode_message, encode_message)
from sporebound.model import RuleError
from sporebound.fixed_clock import _digest


OWNERS = {"hero_a": "alice", "hero_b": "bob"}
TICKETS = {"alice": "alice-long-secret-01", "bob": "bob-long-secret-02"}
KINDS = {"increment"}


def reducer(state, tick, rows):
    state["tick"] = tick
    for row in rows:
        actor = row["command"]["entity"]
        state["points"][actor] += row["command"]["args"]["delta"]
    return state


def make_lab():
    return ConnectedLabSession("private_lab", {"tick": 0, "points": {
        "hero_a": 0, "hero_b": 0}}, OWNERS, KINDS, reducer,
        tickets=TICKETS, rate=30, seed=71)


def frame(player="alice", entity="hero_a", tick=1, sequence=1, delta=1):
    return {"version": 1, "type": "command", "session": "private_lab",
            "player": player, "sequence": sequence, "tick": tick,
            "entity": entity, "command": {"kind": "increment", "args": {"delta": delta}}}


class ConnectedLabR71Tests(unittest.TestCase):
    def test_two_clients_authority_replay_and_no_credentials_in_evidence(self):
        lab = make_lab()
        for user, ticket in TICKETS.items():
            self.assertEqual(lab.resume(user, ticket)["tick"], 0)
        lab.submit(encode_message(frame(), KINDS))
        lab.submit(encode_message(frame("bob", "hero_b", delta=4), KINDS))
        before = lab.snapshot()
        before["state"]["points"]["hero_a"] = 999
        self.assertEqual(lab.snapshot()["state"]["points"]["hero_a"], 0)
        result = lab.step()
        self.assertEqual(result["state"]["points"], {"hero_a": 1, "hero_b": 4})
        record = json.loads(json.dumps(lab.recording()))
        self.assertEqual(ConnectedLabSession.replay(record, make_lab().snapshot()["state"],
                                                    reducer), result)
        self.assertNotIn("ticket", json.dumps(record))
        self.assertNotIn("secret", json.dumps(record))

    def test_wrong_owner_duplicate_sequence_and_disconnection_fail_closed(self):
        lab = make_lab()
        auth = lab.resume("alice", TICKETS["alice"])
        owners = lab.owners
        owners["hero_b"] = "alice"
        self.assertEqual(lab.owners["hero_b"], "bob")
        with self.assertRaises(RuleError):
            lab.submit(encode_message(frame(entity="hero_b"), KINDS))
        with self.assertRaises(RuleError):
            lab.submit(encode_message(frame(sequence=2), KINDS))
        lab.submit(encode_message(frame(), KINDS))
        with self.assertRaises(RuleError):
            lab.submit(encode_message(frame(), KINDS))
        lab.disconnect("alice")
        with self.assertRaises(RuleError):
            lab.submit(encode_message(frame(sequence=2), KINDS))
        with self.assertRaises(RuleError):
            lab.resume("alice", TICKETS["alice"])
        self.assertEqual(lab.resume("alice", auth["ticket"])["tick"], 0)
        lab.step()
        self.assertEqual(lab.snapshot()["state"]["points"]["hero_a"], 1)

    def test_bad_wire_schema_duplicate_keys_sizes_and_nonfinite(self):
        original = frame()
        invalids = [
            {**original, "version": True}, {**original, "version": 9},
            {**original, "tick": 0}, {**original, "tick": True},
            {**original, "sequence": 0}, {**original, "entity": "bad.name"},
            {**original, "command": {"kind": "__import__", "args": {}}},
            {**original, "command": {"kind": "increment", "args": {"x": []}}},
            {**original, "command": {"kind": "increment", "args": {"x": float("nan")}}},
            {**original, "unknown": "x"},
        ]
        for bad in invalids:
            with self.subTest(bad=bad), self.assertRaises((RuleError, ValueError)):
                encode_message(bad, KINDS)
        bad_wire = [b"{", b"\xff", b"{}", b" " * 4097,
                    b'{"a":1,"a":2}',
                    encode_message(original, KINDS).replace(b'"version":1',
                                                            b'"version":NaN')]
        for raw in bad_wire:
            with self.subTest(raw=raw[:30]), self.assertRaises((RuleError, ValueError)):
                decode_message(raw, KINDS)

    def test_future_tick_bounded_and_tick_reducer_failure_is_atomic(self):
        lab = make_lab()
        lab.resume("alice", TICKETS["alice"])
        with self.assertRaises(RuleError):
            lab.submit(encode_message(frame(tick=9), KINDS))
        lab.submit(encode_message(frame(tick=2), KINDS))
        with self.assertRaises(RuleError):
            lab.submit(encode_message(frame(tick=1, sequence=2), KINDS))
        lab.step()
        self.assertEqual(lab.tick, 1)
        with self.assertRaises(RuleError):
            lab.recording()  # cannot silently drop queued future commands
        self.assertEqual(lab.step()["state"]["points"]["hero_a"], 1)
        failing = make_lab()
        failing.resume("alice", TICKETS["alice"])
        failing.submit(encode_message(frame(), KINDS))
        failing._reducer = lambda *_: (_ for _ in ()).throw(RuntimeError("fault"))
        original = failing.snapshot()
        with self.assertRaises(RuntimeError):
            failing.step()
        self.assertEqual(failing.snapshot(), original)
        failing._reducer = reducer
        self.assertEqual(failing.step()["state"]["points"]["hero_a"], 1)

    def test_tampered_recording_wrong_rules_and_authority(self):
        lab = make_lab()
        lab.resume("alice", TICKETS["alice"])
        lab.submit(encode_message(frame(), KINDS))
        lab.step()
        record = lab.recording()
        variants = []
        corrupt = deepcopy(record)
        corrupt["journal"]["inputs"][0]["command"]["entity"] = "hero_b"
        # Recompute both checksums to prove that replay also checks ownership,
        # not merely that tampering changes the digest.
        corrupt["journal"]["digest"] = _digest({k: v for k, v in
            corrupt["journal"].items() if k != "digest"})
        corrupt["digest"] = _digest({k: v for k, v in
            corrupt.items() if k != "digest"})
        variants.append(corrupt)
        corrupt = deepcopy(record)
        corrupt["final_digest"] = "0" * 64
        variants.append(corrupt)
        corrupt = deepcopy(record)
        corrupt["journal"]["states"][0] = "0" * 64
        variants.append(corrupt)
        for bad in variants:
            with self.subTest(case=bad["final_digest"][:8]), self.assertRaises(RuleError):
                ConnectedLabSession.replay(bad, make_lab().snapshot()["state"], reducer)
        with self.assertRaises(RuleError):
            ConnectedLabSession.replay(record, {"points": {}}, reducer)
        with self.assertRaises(RuleError):
            ConnectedLabSession.replay(record, make_lab().snapshot()["state"],
                                       lambda *_: {"altered": True})


if __name__ == "__main__":
    unittest.main()

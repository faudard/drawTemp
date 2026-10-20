"""R73.A — fail-closed policy gates; no network runtime or GUI dependency."""
import json
import unittest

from drawtemp.sdk import SDK_FEATURES
from drawtemp.sdk.network_session_policy import (
    ALLOW, PROTOCOL, PolicyError, SessionPolicy, evaluate_command,
    evaluate_join, evaluate_rejoin,
)

GATES = frozenset({"R71", "R72"})
PROJECT = "a" * 64
CONTENT = "b" * 64
SNAPSHOT = "c" * 64


def policy():
    return SessionPolicy(
        opt_in=True, session_id="coop_lab", host_id="host",
        project_digest=PROJECT, content_digest=CONTENT,
        commands=("move", "pause"), host_only=("pause",),
        idle_timeout_ms=3_000, max_command_bytes=512,
    )


def hello(actor):
    return {
        "schema": 1, "session_id": "coop_lab", "protocol": PROTOCOL,
        "project_digest": PROJECT, "content_digest": CONTENT,
        "actor_id": actor,
    }


def command(actor="guest", kind="move", sequence=1, args=None):
    return json.dumps({
        "actor_id": actor, "type": kind, "sequence": sequence,
        "args": {} if args is None else args,
    }, separators=(",", ":")).encode("utf-8")


def checkpoint(revision=2, digest=SNAPSHOT, seen_sequence=1):
    return {
        "session_id": "coop_lab", "protocol": PROTOCOL,
        "project_digest": PROJECT, "content_digest": CONTENT,
        "revision": revision, "digest": digest,
        "seen_sequence": seen_sequence,
    }


class R73PolicyTests(unittest.TestCase):
    def test_default_offline_and_no_network_capability_claim(self):
        self.assertFalse(SessionPolicy().opt_in)
        self.assertEqual(evaluate_join(SessionPolicy(), hello("host"),
                                       trusted_actor_id="host", approved_gates=GATES).code,
                         "opt_in_required")
        self.assertNotIn("network-session.v1", SDK_FEATURES)

    def test_required_go_gates_are_host_side_and_fail_closed(self):
        p = policy()
        for gates in (frozenset(), frozenset({"R71"}), frozenset({"R72"})):
            self.assertEqual(evaluate_join(p, hello("host"), trusted_actor_id="host",
                                           approved_gates=gates).code,
                             "network_gate_no_go")
            self.assertEqual(evaluate_command(p, command("host"), trusted_actor_id="host",
                                              members=("host",), approved_gates=gates).code,
                             "network_gate_no_go")

    def test_schema_and_lan_only_policy_document_roundtrip(self):
        p = policy()
        self.assertEqual(SessionPolicy.from_document(p.to_document()), p)
        self.assertEqual(p.privacy, "local_only")
        bad = p.to_document()
        bad["evil"] = True
        with self.assertRaises(PolicyError):
            SessionPolicy.from_document(bad)
        for attr, value in (("privacy", "public"), ("protocol", "r73-lab/2"),
                            ("idle_timeout_ms", True), ("schema", True),
                            ("max_command_bytes", -1), ("project_digest", "nothex"),
                            ("commands", ("pause", "pause")),
                            ("host_only", ("admin",))):
            with self.subTest(attr=attr):
                doc = p.to_document()
                doc[attr] = list(value) if attr in {"commands", "host_only"} else value
                with self.assertRaises(PolicyError):
                    SessionPolicy.from_document(doc)

    def test_disabled_policy_rejects_hidden_opt_in_material(self):
        with self.assertRaises(PolicyError):
            SessionPolicy(commands=("move",))
        with self.assertRaises(PolicyError):
            SessionPolicy(opt_in=True)
        with self.assertRaises(PolicyError):
            SessionPolicy.from_document({})

    def test_join_requires_authenticated_host_then_guest(self):
        p = policy()
        self.assertEqual(evaluate_join(p, hello("host"), trusted_actor_id="host",
                                       approved_gates=GATES), ALLOW)
        self.assertEqual(evaluate_join(p, hello("guest"), trusted_actor_id="guest",
                                       members=("host",), approved_gates=GATES), ALLOW)
        self.assertEqual(evaluate_join(p, hello("guest"), trusted_actor_id="guest",
                                       approved_gates=GATES).code,
                         "session_full_or_host_missing")

    def test_join_rejects_spoofing_full_membership_and_duplicates(self):
        p = policy()
        self.assertEqual(evaluate_join(p, hello("host"), trusted_actor_id="attacker",
                                       approved_gates=GATES).code, "identity_unverified")
        self.assertEqual(evaluate_join(p, hello("host"), trusted_actor_id="host",
                                       members=("host",), approved_gates=GATES).code,
                         "already_connected")
        self.assertEqual(evaluate_join(p, hello("third"), trusted_actor_id="third",
                                       members=("host", "guest"),
                                       approved_gates=GATES).code,
                         "session_full_or_host_missing")

    def test_join_rejects_stale_protocol_schema_and_digests(self):
        for field, value, reason in (
            ("protocol", "r73-lab/2", "protocol_mismatch"),
            ("schema", 2, "unsupported_schema"),
            ("schema", True, "unsupported_schema"),
            ("project_digest", "d" * 64, "content_mismatch"),
            ("content_digest", "e" * 64, "content_mismatch"),
        ):
            with self.subTest(field=field):
                incoming = hello("host")
                incoming[field] = value
                self.assertEqual(evaluate_join(policy(), incoming,
                                               trusted_actor_id="host",
                                               approved_gates=GATES).code, reason)
        broken = hello("host")
        broken["unauthorized"] = "ignored?"
        self.assertEqual(evaluate_join(policy(), broken, trusted_actor_id="host",
                                       approved_gates=GATES).code, "invalid_hello")

    def test_command_validation_happy_path_and_host_only(self):
        p = policy()
        self.assertEqual(evaluate_command(p, command(), trusted_actor_id="guest",
                                          members=("host", "guest"),
                                          approved_gates=GATES), ALLOW)
        self.assertEqual(evaluate_command(p, command("guest", "pause"),
                                          trusted_actor_id="guest",
                                          members=("host", "guest"),
                                          approved_gates=GATES).code,
                         "host_permission_required")
        self.assertEqual(evaluate_command(p, command("host", "pause"),
                                          trusted_actor_id="host",
                                          members=("host", "guest"),
                                          approved_gates=GATES), ALLOW)

    def test_command_replay_out_of_order_and_invalid_sequence(self):
        for seq in (1, 3, 0, -1, True):
            with self.subTest(seq=seq):
                result = evaluate_command(policy(), command(sequence=seq),
                                          trusted_actor_id="guest",
                                          members=("host", "guest"),
                                          previous_sequence=1, approved_gates=GATES)
                self.assertEqual(result.code, "stale_or_out_of_order")
        self.assertEqual(evaluate_command(
            policy(), command(sequence=2), trusted_actor_id="guest",
            members=("host", "guest"), previous_sequence=1,
            approved_gates=GATES), ALLOW)

    def test_command_spoofing_disconnected_unknown_and_timeout(self):
        p = policy()
        common = {"members": ("host", "guest"), "approved_gates": GATES}
        self.assertEqual(evaluate_command(
            p, command(), trusted_actor_id="host", **common).code,
            "identity_unverified")
        self.assertEqual(evaluate_command(
            p, command("intruder"), trusted_actor_id="intruder",
            **common).code, "not_connected")
        self.assertEqual(evaluate_command(
            p, command("guest", "steal"), trusted_actor_id="guest",
            **common).code, "command_not_allowed")
        self.assertEqual(evaluate_command(
            p, command(), trusted_actor_id="guest", idle_ms=3_001,
            **common).code, "session_timed_out")
        self.assertEqual(evaluate_command(
            p, command(), trusted_actor_id="guest", idle_ms=3_000,
            **common), ALLOW)

    def test_command_rejects_oversize_duplicate_keys_and_malformed_json(self):
        p = policy()
        common = {"trusted_actor_id": "guest",
                  "members": ("host", "guest"), "approved_gates": GATES}
        for data in (
            b"{bad", b"\xff",
            b'{"actor_id":"guest","type":"move","sequence":1,"args":{}, "args":{}}',
            command(args={"big": "X" * 600}),
            command(args={"deep": [[[[[[[[[1]]]]]]]]]}),
            b'{"actor_id":"guest","type":"move","sequence":1,"args":{"x":NaN}}',
        ):
            with self.subTest(data=data[:20]):
                self.assertEqual(evaluate_command(p, data, **common).code,
                                 "invalid_command")

    def test_rejoin_requires_host_checkpoint_and_monotonic_sequence(self):
        p = policy()
        kwargs = {
            "trusted_actor_id": "guest", "known_actors": ("host", "guest"),
            "authoritative_revision": 2, "authoritative_digest": SNAPSHOT,
            "committed_sequence": 3, "approved_gates": GATES,
        }
        self.assertEqual(evaluate_rejoin(p, checkpoint(), **kwargs), ALLOW)
        self.assertEqual(evaluate_rejoin(p, checkpoint(seen_sequence=4),
                                         **kwargs).code,
                         "stale_or_unverified_checkpoint")
        self.assertEqual(evaluate_rejoin(p, checkpoint(revision=1),
                                         **kwargs).code,
                         "stale_or_unverified_checkpoint")
        self.assertEqual(evaluate_rejoin(p, checkpoint(digest="d" * 64),
                                         **kwargs).code,
                         "stale_or_unverified_checkpoint")
        self.assertEqual(evaluate_rejoin(
            p, checkpoint(), **{**kwargs, "trusted_actor_id": "intruder"}).code,
            "identity_unverified")

    def test_solo_does_not_create_network_side_effects(self):
        # Import and construct a disabled policy without Qt, IO, or socket calls.
        self.assertEqual(SessionPolicy().to_document()["opt_in"], False)
        self.assertEqual(evaluate_command(SessionPolicy(), command(),
                                          trusted_actor_id="guest").code,
                         "opt_in_required")


if __name__ == "__main__":
    unittest.main()

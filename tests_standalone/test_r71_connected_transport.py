"""R71.C operational lab: peer-bound authority, framing, opt-in LAN, mTLS loopback.

Loopback TLS test uses throwaway private CA/certificates in TemporaryDirectory.
It never connects to the Internet, binds to a public interface or checks keys
into the repository. Real two-device certification remains a separate gate.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from sporebound.connected_lab_r71 import (
    ConnectedLabSession, encode_message)
from sporebound.connected_service_r71 import ConnectedLabService
from sporebound.connected_certification_r71 import (
    INITIAL, OWNERS, SESSION, _hold, puzzle_reducer)
from sporebound.connected_transport_r71 import (
    PinnedPeerGateway, _validate_bind, read_packet, write_packet,
    serve_private_probe, submit_private_probe, tls_server_context,
    tls_client_context)
from sporebound.model import RuleError


def service_and_pins():
    a = b"fake-verified-alice-cert"
    b = b"fake-verified-bob-cert"
    pins = {hashlib.sha256(a).hexdigest(): "alice",
            hashlib.sha256(b).hexdigest(): "bob"}
    service = ConnectedLabService(ConnectedLabSession(
        SESSION, INITIAL, OWNERS, {"hold"}, puzzle_reducer,
        tickets={"alice": "long-alice-ticket-test", "bob": "long-bob-ticket-test"}))
    return service, pins, a, b


def hello(player):
    return {"version": 1, "session": SESSION, "player": player,
            "last_tick": 0, "capabilities": ["commands_v1"]}


class R71COperationalTests(unittest.TestCase):
    def test_pinned_identity_cannot_impersonate_other_player(self):
        service, pins, a, b = service_and_pins()
        gateway = PinnedPeerGateway(service, pins)
        with self.assertRaises(RuleError):
            gateway.admit(a, hello("bob"), "long-alice-ticket-test")
        with self.assertRaises(RuleError):
            gateway.admit(b"unknown-certificate", hello("alice"),
                          "long-alice-ticket-test")
        reply = gateway.admit(a, hello("alice"), "long-alice-ticket-test")
        self.assertGreaterEqual(len(reply["ticket"]), 16)
        with self.assertRaises(RuleError):
            gateway.admit(a, hello("alice"), reply["ticket"])
        self.assertFalse(gateway.submit(b, _hold("bob"))["accepted"])
        self.assertFalse(gateway.submit(a, _hold("bob"))["accepted"])
        self.assertTrue(gateway.submit(a, _hold("alice"))["accepted"])
        gateway.leave(a)
        self.assertFalse(gateway.submit(a, _hold("alice", sequence=2))["accepted"])
        self.assertEqual(service.snapshot()["tick"], 0)
        self.assertNotIn("ticket", json.dumps(gateway.diagnostics()))
        self.assertEqual(gateway.diagnostics()["counts"]["accepted"], 1)

    def test_second_peer_rejoin_and_snapshot_stays_authoritative(self):
        service, pins, a, b = service_and_pins()
        gateway = PinnedPeerGateway(service, pins)
        rotated = gateway.admit(a, hello("alice"), "long-alice-ticket-test")["ticket"]
        gateway.leave(a)
        with self.assertRaises(RuleError):
            gateway.admit(a, hello("alice"), "long-alice-ticket-test")
        gateway.admit(a, hello("alice"), rotated)
        gateway.admit(b, hello("bob"), "long-bob-ticket-test")
        self.assertTrue(gateway.submit(a, _hold("alice"))["accepted"])
        self.assertTrue(gateway.submit(b, _hold("bob"))["accepted"])
        for _ in range(12):
            service.advance()
        self.assertEqual(service.snapshot()["state"]["open_count"], 1)
        self.assertEqual(service.snapshot()["state"]["gate_open"], True)

    def test_no_implicit_public_lan_listener(self):
        _validate_bind("127.0.0.1", False)
        _validate_bind("localhost", False)
        with self.assertRaises(RuleError):
            _validate_bind("0.0.0.0", False)
        with self.assertRaises(RuleError):
            _validate_bind("192.168.1.20", False)
        _validate_bind("192.168.1.20", True)
        with self.assertRaises(RuleError):
            _validate_bind("127.0.0.1", 1)

    def test_truncated_and_oversized_packets_rejected_before_json(self):
        left, right = socket.socketpair()
        with left, right:
            right.sendall(struct.pack("!I", 8193))
            with self.assertRaises(RuleError):
                read_packet(left)
        left, right = socket.socketpair()
        with left, right:
            right.sendall(struct.pack("!I", 8) + b"tiny")
            right.shutdown(socket.SHUT_WR)
            with self.assertRaises(EOFError):
                read_packet(left)
        left, right = socket.socketpair()
        with left, right:
            size = write_packet(right, {"hello": 1})
            self.assertGreater(size, 4)
            self.assertEqual(read_packet(left), {"hello": 1})
            with self.assertRaises(RuleError):
                write_packet(right, {"huge": "x" * 8192}, max_bytes=50)

    def test_certificate_pins_cannot_share_owners(self):
        service, pins, a, b = service_and_pins()
        with self.assertRaises(RuleError):
            PinnedPeerGateway(service, {k: "alice" for k in pins})
        with self.assertRaises(RuleError):
            PinnedPeerGateway(service, {"xx": "alice",
                                        hashlib.sha256(b).hexdigest(): "bob"})


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL CLI needed for ephemeral loopback TLS")
class R71CMutualTlsLoopbackTests(unittest.TestCase):
    def _shell(self, home, *args):
        subprocess.run(["openssl", *args], cwd=home,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True, timeout=30)

    def _certs(self, home):
        self._shell(home, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", "ca.key", "-out", "ca.pem", "-days", "1",
                    "-subj", "/CN=R71 Test CA",
                    "-addext", "basicConstraints=critical,CA:TRUE")
        paths = {}
        for identity in ("server", "alice", "bob"):
            self._shell(home, "req", "-newkey", "rsa:2048", "-nodes",
                        "-keyout", identity + ".key", "-out", identity + ".csr",
                        "-subj", "/CN=" + ("localhost" if identity == "server"
                                         else identity + "-lab"))
            ext = home / (identity + ".ext")
            if identity == "server":
                ext.write_text("subjectAltName=DNS:localhost,IP:127.0.0.1\n"
                               "extendedKeyUsage=serverAuth\n")
            else:
                ext.write_text("extendedKeyUsage=clientAuth\n")
            self._shell(home, "x509", "-req", "-in", identity + ".csr",
                        "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
                        "-out", identity + ".pem", "-days", "1",
                        "-extfile", identity + ".ext")
            der = ssl.PEM_cert_to_DER_cert((home / (identity + ".pem")).read_text())
            paths[identity] = hashlib.sha256(der).hexdigest()
        return paths

    def test_two_separate_clients_over_real_localhost_mtls(self):
        with tempfile.TemporaryDirectory(prefix="r71c-local-tls-") as d:
            home = Path(d)
            pins = self._certs(home)
            server_ctx = tls_server_context(
                str(home / "server.pem"), str(home / "server.key"),
                str(home / "ca.pem"))
            tickets = {"alice": "alice-ephemeral-test-ticket",
                       "bob": "bob-ephemeral-test-ticket"}
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            outcome = {}
            def server():
                try:
                    outcome["report"] = serve_private_probe(
                        host="127.0.0.1", port=port, server_context=server_ctx,
                        pins={pins["alice"]: "alice", pins["bob"]: "bob"},
                        tickets=tickets, seed=71)
                except BaseException as exc:
                    outcome["error"] = repr(exc)
            thread = threading.Thread(target=server, daemon=True)
            thread.start()
            for player in ("alice", "bob"):
                client_ctx = tls_client_context(
                    str(home / (player + ".pem")),
                    str(home / (player + ".key")),
                    str(home / "ca.pem"))
                for attempt in range(40):
                    try:
                        answer = submit_private_probe(
                            host="127.0.0.1", port=port, context=client_ctx,
                            server_name="localhost",
                            expected_server_sha256=pins["server"],
                            player=player, ticket=tickets[player])
                        break
                    except ConnectionRefusedError:
                        if attempt == 39:
                            raise
                        time.sleep(.05)
                self.assertTrue(answer["command_accepted"])
                self.assertNotEqual(answer["rotated_ticket"], tickets[player])
                self.assertGreaterEqual(answer["rtt_ms"], 0)
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive(), "TLS server did not terminate")
            self.assertNotIn("error", outcome, outcome.get("error"))
            result = outcome["report"]
            self.assertEqual(result["decision"], "NO-GO")
            self.assertTrue(result["replay_verified"])
            self.assertEqual(result["reward_or_unlock_count"], 1)
            self.assertEqual(result["accepted_players"], 2)
            self.assertEqual(result["gateway"]["counts"]["accepted"], 2)
            self.assertGreater(result["metrics"]["app_bytes_received"], 0)
            self.assertGreater(result["metrics"]["app_bytes_sent"], 0)
            self.assertGreater(result["metrics"]["python_peak_alloc_bytes"], 0)
            for ticket in tickets.values():
                self.assertNotIn(ticket, json.dumps(result))


if __name__ == "__main__":
    unittest.main()

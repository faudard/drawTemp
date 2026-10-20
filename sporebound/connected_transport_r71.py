"""R71.C opt-in mTLS *test fixture* for two private clients, never Player runtime.

A separate operator provisions a CA, server/client certificates, per-client
certificate SHA-256 pins and rotating bearer tickets. This module opens no
listener on import. No self-signed test keys or authentication bypass ship.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
import socket
import ssl
import struct
import time
import tracemalloc

from .connected_lab_r71 import (ConnectedLabSession, MAX_WIRE_BYTES,
                                _pairs_no_duplicates, _deny_constant,
                                decode_message, encode_message)
from .connected_service_r71 import (CAPABILITY, ConnectedLabService)
from .connected_certification_r71 import (INITIAL, OWNERS, SESSION,
                                          DURATION_TICKS, puzzle_reducer)
from .model import RuleError, require

MAX_REQUEST_BYTES = 8192
MAX_REPLY_BYTES = 131072
READ_TIMEOUT_SECONDS = 15
MAX_ACCEPT_ATTEMPTS = 8
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _fingerprint(der):
    require(type(der) is bytes and 0 < len(der) <= 16384,
            "Missing or excessive verified peer certificate")
    return hashlib.sha256(der).hexdigest()


def _pins(mapping):
    require(type(mapping) is dict and len(mapping) == 2,
            "Two pinned peer certificates are required")
    require(all(type(pin) is str and _HEX.fullmatch(pin)
                and player in ("alice", "bob")
                for pin, player in mapping.items())
            and set(mapping.values()) == {"alice", "bob"},
            "Invalid or repeated pinned certificate identity")
    return dict(mapping)


def _json_bytes(value, limit):
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError("Invalid operational lab JSON") from exc
    require(0 < len(raw) <= limit, "Bounded TLS lab message too large")
    return raw


def _parse_json(raw, limit):
    require(type(raw) is bytes and 0 < len(raw) <= limit,
            "Invalid TLS lab frame")
    try:
        return json.loads(raw.decode("utf-8"),
                          object_pairs_hook=_pairs_no_duplicates,
                          parse_constant=_deny_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("Malformed TLS lab JSON") from exc


class PinnedPeerGateway:
    """Bind each decoded command to the verified TLS peer certificate.

    Only the TLS implementation is allowed to supply peer DER here. Tests may
    inject a fake DER to check isolation without pretending it is certified.
    """

    def __init__(self, service, pins):
        require(isinstance(service, ConnectedLabService),
                "Expected the existing connected service")
        self.service = service
        self._pins = _pins(pins)
        self._active = set()
        self._counts = {"admitted": 0, "denied": 0,
                        "accepted": 0, "rejected": 0}

    def admit(self, verified_peer_der, hello, ticket):
        pin = _fingerprint(verified_peer_der)
        player = self._pins.get(pin)
        try:
            require(player is not None and pin not in self._active,
                    "Unpinned or duplicated connected client")
            require(type(hello) is dict and hello.get("player") == player,
                    "Claimed player differs from mTLS identity")
            result = self.service.connect(hello, ticket)
        except (RuleError, ValueError):
            self._counts["denied"] += 1
            raise
        self._active.add(pin)
        self._counts["admitted"] += 1
        return result

    def submit(self, verified_peer_der, frame):
        pin = _fingerprint(verified_peer_der)
        player = self._pins.get(pin)
        try:
            require(pin in self._active and player is not None,
                    "Peer not currently authenticated")
            message = decode_message(frame, self.service._lab.allowed_kinds)
            require(message["player"] == player,
                    "Command claims a different TLS client identity")
        except (RuleError, ValueError):
            self._counts["rejected"] += 1
            return {"accepted": False, "code": "PEER_IDENTITY_OR_FRAME_DENIED",
                    "server_tick": self.service.tick}
        result = self.service.receive(frame)
        self._counts["accepted" if result["accepted"] else "rejected"] += 1
        return result

    def leave(self, verified_peer_der):
        pin = _fingerprint(verified_peer_der)
        if pin in self._active:
            self._active.remove(pin)
            self.service.disconnect(self._pins[pin])

    def diagnostics(self):
        return {"format": "r71c-bound-peer-metrics-v1",
                "counts": dict(self._counts), "active": len(self._active)}


def tls_server_context(certfile, keyfile, cafile):
    """Require mTLS and trust an operator-provisioned CA."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=cafile)
    context.load_cert_chain(certfile, keyfile)
    return context


def tls_client_context(certfile, keyfile, cafile):
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=cafile)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = True
    context.load_cert_chain(certfile, keyfile)
    return context


def _read_exact(sock, n):
    require(type(n) is int and 0 <= n <= MAX_REPLY_BYTES,
            "Invalid TLS read size")
    data = bytearray()
    while len(data) < n:
        piece = sock.recv(n - len(data))
        if not piece:
            raise EOFError("TLS lab peer closed early")
        data.extend(piece)
    return bytes(data)


def read_packet(sock, *, max_bytes=MAX_REQUEST_BYTES):
    require(type(max_bytes) is int and 1 <= max_bytes <= MAX_REPLY_BYTES,
            "Invalid TLS packet budget")
    length = struct.unpack("!I", _read_exact(sock, 4))[0]
    require(0 < length <= max_bytes, "TLS packet length exceeded")
    return _parse_json(_read_exact(sock, length), max_bytes)


def write_packet(sock, data, *, max_bytes=MAX_REPLY_BYTES):
    raw = _json_bytes(data, max_bytes)
    sock.sendall(struct.pack("!I", len(raw)) + raw)
    return len(raw) + 4


def _is_loopback(host):
    return host in ("127.0.0.1", "::1", "localhost")


def _validate_bind(host, allow_lan):
    require(type(host) is str and bool(host) and len(host) <= 255,
            "Invalid TLS listener host")
    require(type(allow_lan) is bool, "Expected explicit allow_lan boolean")
    require(allow_lan or _is_loopback(host),
            "Binding a non-loopback interface requires explicit --allow-lan")


def _make_session(tickets, seed):
    require(type(tickets) is dict and set(tickets) == {"alice", "bob"},
            "Both out-of-band client tickets are required")
    lab = ConnectedLabSession(SESSION, deepcopy(INITIAL), OWNERS, {"hold"},
                              puzzle_reducer, tickets=tickets, seed=seed)
    return ConnectedLabService(lab)


def serve_private_probe(*, host, port, server_context, pins, tickets,
                        seed=71, allow_lan=False):
    """Finite two-client mTLS test. Not a long-lived or hardened game server.

    Requires two *different pinned client certificates*. No client can advance
    the authoritative tick or claim a different player's commands.
    """
    _validate_bind(host, allow_lan)
    require(type(port) is int and 0 <= port <= 65535,
            "Invalid TLS listener port")
    require(isinstance(server_context, ssl.SSLContext)
            and server_context.verify_mode == ssl.CERT_REQUIRED,
            "Mutual TLS certificate verification required")
    service = _make_session(tickets, seed)
    gateway = PinnedPeerGateway(service, pins)
    admitted_players = set()
    received_bytes = sent_bytes = 0
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    tracemalloc.start()
    try:
        with socket.create_server((host, port), backlog=2) as listener:
            listener.settimeout(READ_TIMEOUT_SECONDS)
            port_bound = listener.getsockname()[1]
            while len(admitted_players) < 2:
                require(gateway.diagnostics()["counts"]["admitted"] <
                        MAX_ACCEPT_ATTEMPTS, "Too many TLS probe connections")
                try:
                    conn, _ = listener.accept()
                except socket.timeout as exc:
                    raise TimeoutError("Missing second TLS private client") from exc
                with conn:
                    conn.settimeout(READ_TIMEOUT_SECONDS)
                    peer = None
                    try:
                        with server_context.wrap_socket(conn, server_side=True) as tls:
                            peer = tls.getpeercert(binary_form=True)
                            require(bool(peer), "Verified TLS client certificate missing")
                            first = read_packet(tls)
                            received_bytes += len(_json_bytes(first, MAX_REQUEST_BYTES)) + 4
                            require(type(first) is dict
                                    and set(first) == {"op", "hello", "ticket"}
                                    and first["op"] == "hello",
                                    "Invalid TLS handshake envelope")
                            reply = gateway.admit(peer, first["hello"], first["ticket"])
                            sent_bytes += write_packet(tls, {"ok": True,
                                                             "admission": reply})
                            second = read_packet(tls)
                            received_bytes += len(_json_bytes(second, MAX_REQUEST_BYTES)) + 4
                            require(type(second) is dict
                                    and set(second) == {"op", "frame"}
                                    and second["op"] == "command",
                                    "Invalid TLS command envelope")
                            frame = encode_message(second["frame"], {"hold"})
                            result = gateway.submit(peer, frame)
                            sent_bytes += write_packet(tls, {"ok": result["accepted"],
                                                             "receipt": result})
                            if result["accepted"]:
                                admitted_players.add(first["hello"]["player"])
                    except (RuleError, ValueError, EOFError, ssl.SSLError, OSError):
                        # No credentials, framed commands, certificates, or stack
                        # traces are reflected into logs or result diagnostics.
                        pass
                    finally:
                        if peer is not None:
                            gateway.leave(peer)
            for _ in range(DURATION_TICKS):
                service.advance()
            recording = service.recording()
            snapshot = service.snapshot()
            replayed = ConnectedLabSession.replay(
                recording, deepcopy(INITIAL), puzzle_reducer)
            require(replayed == snapshot, "Private TLS probe replay mismatch")
            require(snapshot["state"]["open_count"] == 1,
                    "Private TLS cooperative gate was not completed")
            _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {"format": "r71c-mtls-two-client-probe-v1",
            "scope": "opt_in_operator_private_lan", "port": port_bound,
            "accepted_players": 2, "replay_verified": True,
            "state_digest": snapshot["digest"],
            "reward_or_unlock_count": snapshot["state"]["open_count"],
            "metrics": {"wall_ms": round((time.perf_counter()-start_wall)*1000, 3),
                        "process_cpu_ms": round((time.process_time()-start_cpu)*1000, 3),
                        "python_peak_alloc_bytes": peak,
                        "app_bytes_received": received_bytes,
                        "app_bytes_sent": sent_bytes},
            "gateway": gateway.diagnostics(), "decision": "NO-GO"}


def submit_private_probe(*, host, port, context, server_name,
                         expected_server_sha256, player, ticket):
    """One TLS client. Returns the *rotated* admission secret to its caller.

    Operator must store the new ticket privately for any future reconnect.
    """
    require(player in ("alice", "bob") and type(ticket) is str
            and 16 <= len(ticket) <= 256, "Invalid local TLS client credentials")
    require(type(expected_server_sha256) is str
            and _HEX.fullmatch(expected_server_sha256),
            "Pinned server certificate SHA-256 is required")
    require(type(port) is int and 1 <= port <= 65535,
            "Invalid TLS destination port")
    require(type(server_name) is str and bool(server_name),
            "Expected certificate SAN hostname")
    require(isinstance(context, ssl.SSLContext)
            and context.verify_mode == ssl.CERT_REQUIRED
            and context.check_hostname, "TLS server identity validation required")
    start = time.perf_counter()
    with socket.create_connection((host, port), timeout=READ_TIMEOUT_SECONDS) as tcp:
        with context.wrap_socket(tcp, server_hostname=server_name) as tls:
            tls.settimeout(READ_TIMEOUT_SECONDS)
            require(_fingerprint(tls.getpeercert(binary_form=True))
                    == expected_server_sha256,
                    "Pinned TLS server certificate mismatch")
            write_packet(tls, {"op": "hello", "hello": {
                "version": 1, "session": SESSION, "player": player,
                "last_tick": 0, "capabilities": [CAPABILITY]}, "ticket": ticket})
            admission = read_packet(tls, max_bytes=MAX_REPLY_BYTES)
            require(type(admission) is dict and admission.get("ok") is True,
                    "TLS session admission refused")
            entity = "plate_a" if player == "alice" else "plate_b"
            write_packet(tls, {"op": "command", "frame": {
                "version": 1, "type": "command", "session": SESSION,
                "player": player, "sequence": 1, "tick": 8, "entity": entity,
                "command": {"kind": "hold", "args": {}}}})
            receipt = read_packet(tls)
            require(receipt.get("ok") is True, "Cooperative command rejected")
            return {"format": "r71c-mtls-client-v1",
                    "player": player, "rotated_ticket": admission["admission"]["ticket"],
                    "command_accepted": True, "rtt_ms": round(
                        (time.perf_counter()-start)*1000, 3)}


__all__ = ["PinnedPeerGateway", "tls_server_context", "tls_client_context",
           "read_packet", "write_packet", "serve_private_probe",
           "submit_private_probe"]

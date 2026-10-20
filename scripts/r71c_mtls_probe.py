"""Operator-only R71.C mTLS two-device laboratory. No Player integration.

Operator provisions a private CA, server/client certs, SHA-256 pins and
out-of-band tickets. Do not commit secrets/certificates or send them in logs.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile

from sporebound.connected_transport_r71 import (
    serve_private_probe, submit_private_probe, tls_client_context,
    tls_server_context)


def _read_json(path):
    with open(path, "rb") as stream:
        raw = stream.read(8193)
    if len(raw) > 8192:
        raise ValueError("Lab credentials/pins file too large")
    return json.loads(raw.decode("utf-8"))


def _read_ticket(path):
    with open(path, "r", encoding="utf-8") as stream:
        ticket = stream.read(257).strip()
    if not 16 <= len(ticket) <= 256:
        raise ValueError("Invalid private client ticket")
    return ticket


def _save_rotated_ticket(path, ticket):
    # Never print secrets to stdout, logs or shell history. Atomic rotation.
    target = os.path.abspath(path)
    directory = os.path.dirname(target)
    handle, temporary = tempfile.mkstemp(prefix=".r71-ticket-", dir=directory)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
            stream.write(ticket + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    server = sub.add_parser("server", help="Explicitly start finite private mTLS probe")
    client = sub.add_parser("client", help="Send a single authorized hold through mTLS")
    for cmd in (server, client):
        cmd.add_argument("--cert", required=True, help="PEM leaf certificate")
        cmd.add_argument("--key", required=True, help="PEM private key")
        cmd.add_argument("--ca", required=True, help="PEM private trusted CA")
        cmd.add_argument("--port", type=int, required=True)
    server.add_argument("--bind-host", default="127.0.0.1")
    server.add_argument("--allow-lan", action="store_true",
                        help="Explicitly permit non-loopback binding")
    server.add_argument("--pins-file", required=True,
                        help='JSON: {"<client certificate sha256>":"alice", "...":"bob"}')
    server.add_argument("--tickets-file", required=True,
                        help='JSON: {"alice":"secret1", "bob":"secret2"}')
    server.add_argument("--seed", type=int, default=71)
    client.add_argument("--host", required=True)
    client.add_argument("--server-name", required=True,
                        help="Server certificate DNS SAN name to verify")
    client.add_argument("--server-sha256", required=True,
                        help="Pinned server leaf certificate SHA-256")
    client.add_argument("--player", required=True, choices=("alice", "bob"))
    client.add_argument("--ticket-file", required=True,
                        help="Private file with current bearer ticket; rotated in-place")
    args = parser.parse_args(argv)
    if args.mode == "server":
        context = tls_server_context(args.cert, args.key, args.ca)
        report = serve_private_probe(
            host=args.bind_host, port=args.port, server_context=context,
            pins=_read_json(args.pins_file), tickets=_read_json(args.tickets_file),
            seed=args.seed, allow_lan=args.allow_lan)
    else:
        context = tls_client_context(args.cert, args.key, args.ca)
        report = submit_private_probe(
            host=args.host, port=args.port, context=context,
            server_name=args.server_name,
            expected_server_sha256=args.server_sha256,
            player=args.player, ticket=_read_ticket(args.ticket_file))
        _save_rotated_ticket(args.ticket_file, report.pop("rotated_ticket"))
    print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

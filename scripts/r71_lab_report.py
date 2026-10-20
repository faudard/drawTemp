"""Generate a redacted, deterministic R71.B in-process network laboratory report.

Usage: python scripts/r71_lab_report.py --seed 71 --latency 2 --loss 20
This runs NO network listener; errors/rejected frames are expected under faults.
"""
import argparse
from dataclasses import asdict
import json
import secrets

from sporebound.connected_lab_r71 import ConnectedLabSession, encode_message
from sporebound.connected_service_r71 import (
    CAPABILITY, ConnectedLabService, FaultProfile, SimulatedSessionLink)


def build_report(seed=71, *, latency=1, jitter=0, loss=0, duplicate=0,
                 reorder_every=0, reorder_delay=0):
    profile = FaultProfile(latency_steps=latency, jitter_steps=jitter,
                           drop_percent=loss, duplicate_percent=duplicate,
                           reorder_every=reorder_every,
                           reorder_extra_steps=reorder_delay)

    def reducer(state, tick, events):
        state["tick"] = tick
        for row in events:
            state["moves"][row["command"]["entity"]] += row["command"]["args"]["step"]
        return state

    owners = {"hero_a": "alice", "hero_b": "bob"}
    tickets = {person: secrets.token_urlsafe(24) for person in owners.values()}
    initial = {"tick": 0, "moves": {key: 0 for key in owners}}
    laboratory = ConnectedLabSession("r71_local", initial, owners, {"move"},
                                     reducer, tickets=tickets, seed=seed)
    service = ConnectedLabService(laboratory)
    for player in sorted(set(owners.values())):
        service.connect({"version": 1, "session": "r71_local", "player": player,
                         "last_tick": 0, "capabilities": [CAPABILITY]}, tickets[player])

    link = SimulatedSessionLink(service, profile, seed=seed)
    for player, entity in sorted(((v, k) for k, v in owners.items())):
        link.send(encode_message({"version": 1, "type": "command", "session": "r71_local",
                                  "player": player, "sequence": 1, "tick": 8,
                                  "entity": entity,
                                  "command": {"kind": "move", "args": {"step": 1}}},
                                 {"move"}))
    for _ in range(8):
        link.pump()
        service.advance()

    recording = service.recording()
    return {"format": "r71b-lab-report-v1", "scope": "in_process_only",
            "seed": seed, "fault_profile": asdict(profile),
            "service": service.diagnostics(), "link": link.diagnostics(),
            "authoritative": service.snapshot(),
            "replay_digest": recording["digest"], "non_public": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=71)
    parser.add_argument("--latency", type=int, default=1)
    parser.add_argument("--jitter", type=int, default=0)
    parser.add_argument("--loss", type=int, default=0)
    parser.add_argument("--duplicate", type=int, default=0)
    parser.add_argument("--reorder-every", type=int, default=0)
    parser.add_argument("--reorder-delay", type=int, default=0)
    args = parser.parse_args(argv)
    data = build_report(args.seed, latency=args.latency, jitter=args.jitter,
                        loss=args.loss, duplicate=args.duplicate,
                        reorder_every=args.reorder_every, reorder_delay=args.reorder_delay)
    print(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

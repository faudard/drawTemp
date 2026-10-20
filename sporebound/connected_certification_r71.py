"""R71.C: isolated 2-client cooperative certification *evidence*, not multiplayer.

This is a deterministic, bounded in-memory pressure-plate scene that uses the
existing R71.A authoritative FixedTickJournal and R71.B virtual fault link.
It does not create sockets, modify GameSession/Player, or certify a release.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import secrets

from .connected_lab_r71 import ConnectedLabSession, encode_message, _digest
from .connected_service_r71 import (CAPABILITY, ConnectedLabService, FaultProfile,
                                    SimulatedSessionLink, MAX_PENDING_PACKETS)
from .model import RuleError, require

PLAYERS = ("alice", "bob")
OWNERS = {"plate_a": "alice", "plate_b": "bob"}
INITIAL = {"tick": 0, "held_this_tick": [], "gate_open": False,
           "open_count": 0, "accepted_holds": 0}
SESSION = "r71_private"
TARGET_TICK = 8
DURATION_TICKS = 12


def puzzle_reducer(state, tick, rows):
    """Trusted fixture reducer. Only *same-tick* holds unlock both plates.

    This is a tiny certification fixture, not a replacement gameplay engine.
    Incoming commands have already passed the R71.A ownership/allowlist check.
    """
    require(type(state) is dict and set(state) == set(INITIAL),
            "Invalid private cooperative scene state")
    held = set()
    for row in rows:
        command = row["command"]
        require(command["kind"] == "hold" and command["args"] == {},
                "Unexpected cooperative scene command")
        held.add(command["entity"])
    state["tick"] = tick
    state["held_this_tick"] = sorted(held)
    state["accepted_holds"] += len(rows)
    if not state["gate_open"] and held == set(OWNERS):
        state["gate_open"] = True
        state["open_count"] += 1
    require(state["open_count"] in (0, 1), "Duplicate cooperative gate completion")
    return state


def _start(seed):
    require(type(seed) is int and 0 <= seed <= 0xFFFFFFFF,
            "Invalid certification seed")
    # Credentials intentionally unpredictable and excluded from all reports.
    tickets = {p: secrets.token_urlsafe(24) for p in PLAYERS}
    lab = ConnectedLabSession(SESSION, deepcopy(INITIAL), OWNERS, {"hold"},
                              puzzle_reducer, tickets=tickets, seed=seed)
    service = ConnectedLabService(lab)
    rotated = {}
    for player in PLAYERS:
        answer = service.connect({
            "version": 1, "session": SESSION, "player": player,
            "last_tick": 0, "capabilities": [CAPABILITY]}, tickets[player])
        rotated[player] = answer["ticket"]
    return service, rotated


def _hold(player, sequence=1, tick=TARGET_TICK):
    require(player in PLAYERS, "Unknown cooperative participant")
    entity = next(name for name, owner in OWNERS.items() if owner == player)
    return encode_message({
        "version": 1, "type": "command", "session": SESSION,
        "player": player, "sequence": sequence, "tick": tick, "entity": entity,
        "command": {"kind": "hold", "args": {}}}, {"hold"})


def _evidence(service):
    recording = service.recording()
    snapshot = service.snapshot()
    reproduced = ConnectedLabSession.replay(
        recording, deepcopy(INITIAL), puzzle_reducer)
    require(reproduced == snapshot, "Authoritative replay mismatch")
    require(snapshot["state"]["open_count"] <= 1,
            "Cooperative scene duplicate unlock")
    return {"snapshot": snapshot, "recording_digest": recording["digest"],
            "replay_verified": True}


def run_coop_scene(*, seed=71, faults=None):
    """Two deterministic virtual clients, including optional link failure.

    Commands target tick 8. A packet arriving after that tick is rejected:
    this is intentional, not a claim of retransmission or rollback.
    """
    profile = faults if faults is not None else FaultProfile()
    require(isinstance(profile, FaultProfile), "Invalid fault profile")
    service, _ = _start(seed)
    link = SimulatedSessionLink(service, profile, seed=seed)
    for player in PLAYERS:
        link.send(_hold(player))
    for _ in range(DURATION_TICKS):
        link.pump()
        service.advance()
    result = _evidence(service)
    state = result["snapshot"]["state"]
    return {"kind": "r71c-coop-scene-v1", "seed": seed,
            "faults": asdict(profile), "puzzle_completed": state["gate_open"],
            "reward_or_unlock_count": state["open_count"],
            "accepted_holds": state["accepted_holds"],
            "authoritative_tick": result["snapshot"]["tick"],
            "state_digest": result["snapshot"]["digest"],
            "recording_digest": result["recording_digest"],
            "replay_verified": result["replay_verified"],
            "link": link.diagnostics(), "service": service.diagnostics()}


def run_rejoin_probe(*, seed=71):
    """Simulate connection loss, stale credentials and explicit recovery."""
    service, rotated = _start(seed)
    service.disconnect("alice")
    old_frame = service.receive(_hold("alice"))
    require(not old_frame["accepted"], "Offline command was accepted")
    # The admission ticket issued at the prior handshake is valid only once.
    answer = service.connect({
        "version": 1, "session": SESSION, "player": "alice",
        "last_tick": 0, "capabilities": [CAPABILITY]}, rotated["alice"])
    require(answer["ticket"] != rotated["alice"], "Reconnect ticket not rotated")
    first = service.receive(_hold("alice"))
    second = service.receive(_hold("bob"))
    require(first["accepted"] and second["accepted"],
            "Reconnect did not restore active command admission")
    for _ in range(DURATION_TICKS):
        service.advance()
    state = service.snapshot()["state"]
    report = _evidence(service)
    return {"offline_rejected": True, "ticket_rotated": True,
            "rejoin_accepted": True, "puzzle_completed": state["gate_open"],
            "reward_or_unlock_count": state["open_count"],
            "replay_verified": report["replay_verified"],
            "service": service.diagnostics()}


def run_overload_probe(*, seed=71):
    """Exercise bounded network queue and no partial mutation on overflow."""
    service, _ = _start(seed)
    link = SimulatedSessionLink(service, FaultProfile(latency_steps=3), seed=seed)
    payload = _hold("alice")
    for _ in range(MAX_PENDING_PACKETS):
        link.send(payload)
    before = link.diagnostics()
    rejected = False
    try:
        link.send(payload)
    except RuleError:
        rejected = True
    require(rejected and link.diagnostics() == before,
            "Queue overflow mutated transport state")
    require(service.tick == 0, "Overflow mutated authoritative tick")
    delivered = link.pump(3)
    require(len(delivered) == MAX_PENDING_PACKETS,
            "Virtual transport lost packets without configured loss")
    # The same sequence cannot be applied repeatedly even when packet floods.
    require(sum(bool(row["result"]["accepted"]) for row in delivered) == 1,
            "Flood bypassed server anti-replay sequence")
    for _ in range(DURATION_TICKS):
        service.advance()
    report = _evidence(service)
    return {"overflow_rejected": True,
            "queued_before_rejection": before["pending"],
            "duplicates_rejected": MAX_PENDING_PACKETS - 1,
            "reward_or_unlock_count": service.snapshot()["state"]["open_count"],
            "replay_verified": report["replay_verified"],
            "link": link.diagnostics(), "service": service.diagnostics()}


def certification_report(*, seed=71):
    """Fail-closed release assessment; local results never authorize a GO.

    R67 is REDUCE, not GO. Device/transport/CI/release checks must be supplied
    by independent evidence in a future certification process.
    """
    reliable = run_coop_scene(seed=seed)
    lossy = run_coop_scene(seed=seed, faults=FaultProfile(
        latency_steps=2, jitter_steps=2, drop_percent=30,
        duplicate_percent=30, reorder_every=2, reorder_extra_steps=3))
    rejoin = run_rejoin_probe(seed=seed)
    load = run_overload_probe(seed=seed)
    assertions = {
        "two_client_reliable_scene": reliable["puzzle_completed"],
        "authoritative_replay": all(x["replay_verified"]
                                    for x in (reliable, lossy, rejoin, load)),
        "single_unlock_under_faults": all(
            x["reward_or_unlock_count"] <= 1 for x in
            (reliable, lossy, rejoin, load)),
        "reconnect_ticket_rotation": rejoin["ticket_rotated"],
        "bounded_queue_overload": load["overflow_rejected"],
        # All remaining gates require evidence outside of this laboratory.
        "r67_go": False,
        "r70_certified": False,
        "real_authenticated_transport": False,
        "sender_bound_identity": False,
        "two_physical_devices": False,
        "real_cpu_memory_bandwidth_budgets": False,
        "security_review_passed": False,
        "cross_platform_ci_passed": False,
    }
    blocking = sorted(key for key, passed in assertions.items() if not passed)
    return {"format": "r71c-certification-lab-v1", "seed": seed,
            "scope": "offline_in_process_only", "decision": "NO-GO",
            "public_multiplayer_enabled": False, "checks": assertions,
            "blocking": blocking, "reliable": reliable, "lossy": lossy,
            "reconnect": rejoin, "overload": load}


__all__ = ["INITIAL", "OWNERS", "puzzle_reducer", "run_coop_scene",
           "run_rejoin_probe", "run_overload_probe", "certification_report"]

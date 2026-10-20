"""R72.A experimental, LOCAL-ONLY authoritative two-seat probe.

This is a fixed test fixture for contracts and fault injection, not a socket
server, multiplayer GameSession, authentication service, or production game.
It deliberately does not import or mutate the solo Player's state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any

FORMAT = "drawtemp.r72.local-probe"
VERSION = 1
MAX_EVENTS = 10_000
_IDENT = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
SPAWNS = ((0, 0), (4, 0))
PLATES = ((0, 2), (4, 2))
BOSS = (2, 2)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENT.fullmatch(value) is not None


@dataclass(frozen=True)
class Command:
    player_id: str
    seq: int
    expected_revision: int
    action: str
    dx: int = 0
    dy: int = 0

    def validate(self) -> None:
        if not _identifier(self.player_id):
            raise ValueError("invalid player identifier")
        if type(self.seq) is not int or not 1 <= self.seq <= MAX_EVENTS:
            raise ValueError("invalid command sequence")
        if type(self.expected_revision) is not int or self.expected_revision < 0:
            raise ValueError("invalid revision")
        if self.action not in ("move", "attack"):
            raise ValueError("unsupported command action")
        if type(self.dx) is not int or type(self.dy) is not int:
            raise ValueError("movement values must be integers")
        if self.action == "move" and abs(self.dx) + abs(self.dy) != 1:
            raise ValueError("move must be one cardinal cell")
        if self.action == "attack" and (self.dx, self.dy) != (0, 0):
            raise ValueError("attack cannot change position")

    @classmethod
    def parse(cls, raw: Any) -> "Command":
        if not isinstance(raw, dict) or set(raw) != {
            "player_id", "seq", "expected_revision", "action", "dx", "dy"
        }:
            raise ValueError("unexpected command schema")
        command = cls(**raw)
        command.validate()
        return command


@dataclass(frozen=True)
class Receipt:
    status: str
    revision: int
    reward_awarded: bool = False


class LocalCoopProbe:
    """In-memory command journal and two-seat puzzle/boss fixture.

    Trusted local test calls only. No claim of player identity validation over
    a transport; the R71 secure authority/transport gate is a prerequisite.
    """

    def __init__(self, session_id: str, players: tuple[str, str]):
        if not _identifier(session_id) or len(players) != 2 or any(
            not _identifier(p) for p in players
        ) or players[0] == players[1]:
            raise ValueError("two distinct valid players required")
        self.session_id = session_id
        self.players = tuple(players)
        self._positions = dict(zip(self.players, SPAWNS))
        self._connected = {p: False for p in self.players}
        self._last_seq = {p: 0 for p in self.players}
        self._journal: list[Command] = []
        self._receipts: dict[tuple[str, int], tuple[Command, Receipt]] = {}
        self._hits: set[str] = set()
        self._unlocked = False
        self._reward_count = 0
        self.revision = 0

    def _check_player(self, player_id: str) -> None:
        if player_id not in self.players or not _identifier(player_id):
            raise ValueError("player not in this session")

    def connect(self, player_id: str) -> dict[str, Any]:
        """Local rejoin: returns current authoritative state, not client state."""
        self._check_player(player_id)
        self._connected[player_id] = True
        return self.state()

    def disconnect(self, player_id: str) -> None:
        self._check_player(player_id)
        self._connected[player_id] = False

    def state(self) -> dict[str, Any]:
        return {
            "revision": self.revision,
            "positions": {p: list(self._positions[p]) for p in self.players},
            "puzzle_unlocked": self._unlocked,
            "boss_hp": 2 - len(self._hits),
            "boss_hits_by": sorted(self._hits),
            "reward_count": self._reward_count,
            "last_seq": dict(self._last_seq),
        }

    def apply(self, command: Command) -> Receipt:
        if not isinstance(command, Command):
            raise ValueError("expected Command")
        command.validate()
        self._check_player(command.player_id)
        key = (command.player_id, command.seq)
        existing = self._receipts.get(key)
        if existing is not None:
            if existing[0] != command:
                raise ValueError("sequence reused for different command")
            # An ACK lost in transit cannot repeat an attack or reward.
            return Receipt("duplicate", existing[1].revision,
                           existing[1].reward_awarded)
        if not self._connected[command.player_id]:
            return Receipt("offline", self.revision)
        if command.seq != self._last_seq[command.player_id] + 1:
            return Receipt("invalid_sequence", self.revision)
        if command.expected_revision != self.revision:
            return Receipt("stale_revision", self.revision)
        if len(self._journal) >= MAX_EVENTS:
            return Receipt("journal_full", self.revision)

        player = command.player_id
        awarded = False
        if command.action == "move":
            x, y = self._positions[player]
            target = (x + command.dx, y + command.dy)
            if not (0 <= target[0] < 5 and 0 <= target[1] < 5) or target == BOSS:
                return Receipt("blocked", self.revision)
            if target in (self._positions[p] for p in self.players if p != player):
                return Receipt("blocked", self.revision)
            self._positions[player] = target
            if all(self._positions[p] == plate for p, plate in zip(self.players, PLATES)):
                self._unlocked = True
        else:
            x, y = self._positions[player]
            if (not self._unlocked or player in self._hits or
                    abs(x - BOSS[0]) + abs(y - BOSS[1]) != 1 or
                    len(self._hits) == 2):
                return Receipt("blocked", self.revision)
            self._hits.add(player)
            if len(self._hits) == 2:
                self._reward_count = 1
                awarded = True

        self.revision += 1
        self._last_seq[player] = command.seq
        receipt = Receipt("accepted", self.revision, awarded)
        self._journal.append(command)
        self._receipts[key] = (command, receipt)
        return receipt

    def snapshot(self) -> dict[str, Any]:
        body = {
            "format": FORMAT, "version": VERSION,
            "session_id": self.session_id,
            "players": list(self.players),
            "events": [asdict(event) for event in self._journal],
            "state": self.state(),
        }
        return {**body, "digest": _digest(body)}

    @classmethod
    def restore(cls, snapshot: Any) -> "LocalCoopProbe":
        if not isinstance(snapshot, dict) or set(snapshot) != {
            "format", "version", "session_id", "players", "events", "state", "digest"
        }:
            raise ValueError("invalid snapshot schema")
        if snapshot["format"] != FORMAT or type(snapshot["version"]) is not int \
                or snapshot["version"] != VERSION:
            raise ValueError("unsupported snapshot format/version")
        if not isinstance(snapshot["digest"], str):
            raise ValueError("invalid snapshot digest")
        body = {k: v for k, v in snapshot.items() if k != "digest"}
        if not isinstance(snapshot["events"], list) or len(snapshot["events"]) > MAX_EVENTS:
            raise ValueError("invalid event journal")
        if _digest(body) != snapshot["digest"]:
            raise ValueError("snapshot mismatch")
        players = snapshot["players"]
        if not isinstance(players, list) or len(players) != 2:
            raise ValueError("invalid participant list")
        probe = cls(snapshot["session_id"], tuple(players))
        for p in probe.players:
            probe.connect(p)
        for event in snapshot["events"]:
            command = Command.parse(event)
            if probe.apply(command).status != "accepted":
                raise ValueError("invalid authoritative journal")
        if probe.state() != snapshot["state"]:
            raise ValueError("snapshot state diverges from replay")
        # Resume conservatively: no player is connected without a new join.
        for p in probe.players:
            probe.disconnect(p)
        return probe


def _drive(probe: LocalCoopProbe, player: str, action: str,
           dx: int = 0, dy: int = 0) -> tuple[Command, Receipt]:
    command = Command(player, probe.state()["last_seq"][player] + 1,
                      probe.revision, action, dx, dy)
    return command, probe.apply(command)


def audit_local_probe() -> dict[str, Any]:
    """Execute a small deterministic fault-injected vertical-slice probe."""
    p = LocalCoopProbe("r72-sample", ("hero-a", "hero-b"))
    p.connect("hero-a")
    p.connect("hero-b")
    for actor, dx, dy in (("hero-a", 0, 1), ("hero-a", 0, 1),
                          ("hero-b", 0, 1), ("hero-b", 0, 1),
                          ("hero-a", 1, 0), ("hero-b", -1, 0)):
        _, ack = _drive(p, actor, "move", dx, dy)
        if ack.status != "accepted":
            raise AssertionError("probe move rejected")
    first, ack = _drive(p, "hero-a", "attack")
    if ack.status != "accepted":
        raise AssertionError("first attack rejected")
    p.disconnect("hero-a")
    retransmission = p.apply(first)
    restored = LocalCoopProbe.restore(p.snapshot())
    restored.connect("hero-b")
    _, last = _drive(restored, "hero-b", "attack")
    success = (retransmission.status == "duplicate" and
               last.reward_awarded and restored.state()["reward_count"] == 1 and
               LocalCoopProbe.restore(restored.snapshot()).state() == restored.state())
    return {
        "kind": "r72-headless-local-probe",
        "source_checks_passed": success,
        "event_count": restored.revision,
        "snapshot_digest": restored.snapshot()["digest"],
        "release_ready": False,
        "decision": "NO-GO",
        "missing_release_evidence": [
            "R67/R71 network authority GO", "R70/R53/R65 dependencies",
            "R72.B isolated two-device Qt UX", "R72.C physical-network QA",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(audit_local_probe(), indent=2, ensure_ascii=False))

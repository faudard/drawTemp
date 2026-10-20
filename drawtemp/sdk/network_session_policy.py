"""R73.A research-only network session policy.

Pure, fail-closed checks for a *future* trusted R71/R72 transport.
No sockets, credential verification, GameSession mutation, save I/O or opt-in
side effects. Only a trusted host may supply approved_gates, identity and
authoritative checkpoint metadata; never deserialize these from a client.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Mapping

SCHEMA = 1
PROTOCOL = "r73-lab/1"  # Lab format, NOT a supported wire protocol.
REQUIRED_GATES = frozenset({"R71", "R72"})
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_ACTION = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_POLICY_KEYS = frozenset({
    "schema", "opt_in", "session_id", "host_id", "protocol",
    "project_digest", "content_digest", "commands", "host_only",
    "idle_timeout_ms", "max_command_bytes", "privacy",
})
_HELLO_KEYS = frozenset({
    "schema", "session_id", "protocol", "project_digest",
    "content_digest", "actor_id",
})
_COMMAND_KEYS = frozenset({"actor_id", "type", "sequence", "args"})


class PolicyError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str


ALLOW = Decision(True, "allowed")


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _strict_int(value: object) -> bool:
    return type(value) is int


@dataclass(frozen=True)
class SessionPolicy:
    """Opt-in lab policy; settings alone can never activate networking."""

    schema: int = SCHEMA
    opt_in: bool = False
    session_id: str = ""
    host_id: str = ""
    protocol: str = PROTOCOL
    project_digest: str = ""
    content_digest: str = ""
    commands: tuple[str, ...] = ()
    host_only: tuple[str, ...] = ()
    idle_timeout_ms: int = 15_000
    max_command_bytes: int = 8_192
    privacy: str = "local_only"

    def __post_init__(self):
        if not _strict_int(self.schema) or self.schema != SCHEMA:
            raise PolicyError("unsupported_schema")
        if type(self.opt_in) is not bool:
            raise PolicyError("invalid_opt_in")
        if self.protocol != PROTOCOL or type(self.protocol) is not str:
            raise PolicyError("unsupported_protocol")
        if self.privacy != "local_only":
            raise PolicyError("unsupported_privacy")
        if (not _strict_int(self.idle_timeout_ms) or
                not 1_000 <= self.idle_timeout_ms <= 120_000):
            raise PolicyError("invalid_timeout")
        if (not _strict_int(self.max_command_bytes) or
                not 128 <= self.max_command_bytes <= 65_536):
            raise PolicyError("invalid_payload_limit")
        if (type(self.commands) is not tuple or len(self.commands) > 32 or
                any(not isinstance(c, str) or _ACTION.fullmatch(c) is None
                    for c in self.commands) or len(set(self.commands)) != len(self.commands)):
            raise PolicyError("invalid_commands")
        if (type(self.host_only) is not tuple or
                any(not isinstance(c, str) for c in self.host_only) or
                len(set(self.host_only)) != len(self.host_only) or
                not set(self.host_only).issubset(self.commands)):
            raise PolicyError("invalid_host_only")
        if self.opt_in:
            if not (_valid_id(self.session_id) and _valid_id(self.host_id) and
                    _valid_digest(self.project_digest) and
                    _valid_digest(self.content_digest) and self.commands):
                raise PolicyError("invalid_enabled_policy")
        elif (self.session_id or self.host_id or self.project_digest or
              self.content_digest or self.commands or self.host_only):
            raise PolicyError("disabled_must_be_empty")

    @classmethod
    def from_document(cls, value: Mapping) -> "SessionPolicy":
        if not isinstance(value, Mapping) or set(value) != _POLICY_KEYS:
            raise PolicyError("invalid_policy_fields")
        if type(value["commands"]) is not list or type(value["host_only"]) is not list:
            raise PolicyError("invalid_policy_fields")
        return cls(**{**value, "commands": tuple(value["commands"]),
                      "host_only": tuple(value["host_only"])})

    def to_document(self) -> dict:
        return {**vars(self), "commands": list(self.commands),
                "host_only": list(self.host_only)}


def _ready(policy: SessionPolicy, approved_gates: frozenset[str]) -> Decision:
    if not isinstance(policy, SessionPolicy):
        return Decision(False, "invalid_policy")
    if not policy.opt_in:
        return Decision(False, "opt_in_required")
    # Gates must come from verified host-side evidence, never wire payload.
    if type(approved_gates) is not frozenset or not REQUIRED_GATES <= approved_gates:
        return Decision(False, "network_gate_no_go")
    return ALLOW


def _members(members: object, policy: SessionPolicy) -> bool:
    return (type(members) in (tuple, frozenset) and len(members) <= 2 and
            len(set(members)) == len(members) and
            all(_valid_id(member) for member in members) and
            (not members or policy.host_id in members))


def evaluate_join(policy: SessionPolicy, hello: object, *,
                  trusted_actor_id: str | None = None,
                  members: tuple[str, ...] = (),
                  approved_gates: frozenset[str] = frozenset()) -> Decision:
    """Check a proposed host/guest join; identity comes from a trusted transport."""
    ready = _ready(policy, approved_gates)
    if not ready.allowed:
        return ready
    if not _members(members, policy):
        return Decision(False, "invalid_membership")
    if not isinstance(hello, Mapping) or set(hello) != _HELLO_KEYS:
        return Decision(False, "invalid_hello")
    if not _strict_int(hello["schema"]) or hello["schema"] != SCHEMA:
        return Decision(False, "unsupported_schema")
    if hello["protocol"] != policy.protocol or type(hello["protocol"]) is not str:
        return Decision(False, "protocol_mismatch")
    if (hello["session_id"] != policy.session_id or
            hello["project_digest"] != policy.project_digest or
            hello["content_digest"] != policy.content_digest):
        return Decision(False, "content_mismatch")
    actor = hello["actor_id"]
    if not _valid_id(actor) or trusted_actor_id != actor:
        return Decision(False, "identity_unverified")
    if actor in members:
        return Decision(False, "already_connected")
    if len(members) >= 2 or (not members and actor != policy.host_id):
        return Decision(False, "session_full_or_host_missing")
    return ALLOW


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_key")
        value[key] = item
    return value


def _decode_command(raw: object, limit: int) -> dict | None:
    if type(raw) is not bytes or not 0 < len(raw) <= limit:
        return None
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        return None
    if not isinstance(value, dict) or set(value) != _COMMAND_KEYS:
        return None
    # Fixed byte budget plus bounded JSON complexity avoid oversized/deep input.
    def bounded(node, depth=0):
        if depth > 8:
            return False
        if isinstance(node, dict):
            return len(node) <= 64 and all(
                isinstance(k, str) and len(k) <= 64 and bounded(v, depth + 1)
                for k, v in node.items())
        if isinstance(node, list):
            return len(node) <= 64 and all(bounded(v, depth + 1) for v in node)
        return (node is None or isinstance(node, (str, int, float, bool)))
    if not isinstance(value["args"], dict) or not bounded(value):
        return None
    return value


def evaluate_command(policy: SessionPolicy, raw_command: object, *,
                     trusted_actor_id: str | None = None,
                     members: tuple[str, ...] = (),
                     previous_sequence: int = 0,
                     idle_ms: int = 0,
                     approved_gates: frozenset[str] = frozenset()) -> Decision:
    """Authorize shape/permission/ordering, but never execute a game command."""
    ready = _ready(policy, approved_gates)
    if not ready.allowed:
        return ready
    if not _members(members, policy) or policy.host_id not in members:
        return Decision(False, "invalid_membership")
    command = _decode_command(raw_command, policy.max_command_bytes)
    if command is None:
        return Decision(False, "invalid_command")
    actor = command["actor_id"]
    if not _valid_id(actor) or actor != trusted_actor_id:
        return Decision(False, "identity_unverified")
    if actor not in members:
        return Decision(False, "not_connected")
    if not _strict_int(idle_ms) or idle_ms < 0 or idle_ms > policy.idle_timeout_ms:
        return Decision(False, "session_timed_out")
    if (not _strict_int(previous_sequence) or previous_sequence < 0 or
            not _strict_int(command["sequence"]) or
            command["sequence"] != previous_sequence + 1):
        return Decision(False, "stale_or_out_of_order")
    name = command["type"]
    if not isinstance(name, str) or name not in policy.commands:
        return Decision(False, "command_not_allowed")
    if name in policy.host_only and actor != policy.host_id:
        return Decision(False, "host_permission_required")
    return ALLOW


def evaluate_rejoin(policy: SessionPolicy, checkpoint: object, *,
                    trusted_actor_id: str | None = None,
                    known_actors: tuple[str, ...] = (),
                    authoritative_revision: int = 0,
                    authoritative_digest: str = "",
                    committed_sequence: int = 0,
                    approved_gates: frozenset[str] = frozenset()) -> Decision:
    """Check restart/rejoin metadata against host-owned canonical checkpoint.

    This is not a restore implementation. Save/load and rewards stay exclusively
    with GameSession; never trust a client checkpoint to commit state.
    """
    ready = _ready(policy, approved_gates)
    if not ready.allowed:
        return ready
    if (not _valid_id(trusted_actor_id) or
            type(known_actors) is not tuple or
            len(known_actors) > 2 or len(set(known_actors)) != len(known_actors) or
            policy.host_id not in known_actors or
            trusted_actor_id not in known_actors):
        return Decision(False, "identity_unverified")
    expected = {"session_id", "protocol", "project_digest", "content_digest",
                "revision", "digest", "seen_sequence"}
    if not isinstance(checkpoint, Mapping) or set(checkpoint) != expected:
        return Decision(False, "invalid_checkpoint")
    if (checkpoint["session_id"] != policy.session_id or
            checkpoint["protocol"] != policy.protocol or
            checkpoint["project_digest"] != policy.project_digest or
            checkpoint["content_digest"] != policy.content_digest):
        return Decision(False, "content_mismatch")
    if (not _strict_int(authoritative_revision) or authoritative_revision < 0 or
            not _valid_digest(authoritative_digest) or
            not _strict_int(committed_sequence) or committed_sequence < 0):
        return Decision(False, "invalid_authority")
    if (not _strict_int(checkpoint["revision"]) or
            checkpoint["revision"] != authoritative_revision or
            checkpoint["digest"] != authoritative_digest or
            not _strict_int(checkpoint["seen_sequence"]) or
            not 0 <= checkpoint["seen_sequence"] <= committed_sequence):
        return Decision(False, "stale_or_unverified_checkpoint")
    return ALLOW

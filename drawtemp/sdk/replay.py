"""R1.7: canonical, bounded replay verification for campaign and tactical saves.

All gameplay and RNG are owned by GameSession/Battle/MultiFrontSession.
This module only witnesses replay, checksum and sequence consistency; it
does not implement another gameplay engine or serialization format.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from collections.abc import Mapping

from drawtemp.core import GameSession, RuleError


# Deliberately explicit: never dispatch arbitrary methods from a save file.
REPLAY_OPERATIONS = frozenset({
    "choose_story_option", "choose_tactical_story_option",
    "start_mission", "start_configured_siege", "start_fronts",
    "execute", "return_to_campaign", "abandon_encounter",
    "explore_move", "explore_interact", "explore_wait", "explore_actor",
    "world_destination", "world_advance", "switch_front", "advance_fronts",
    "set_doctrine", "select_route", "negotiate_front", "partial_front",
    "withdraw_front", "start_recovery", "abandon_recovery", "send_reserves",
    "transfer_units", "escort_convoy", "rescue_convoy", "ai_turn",
})


class ReplayError(RuleError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ReplayCommand:
    operation: str
    args: tuple = ()
    kwargs: Mapping = field(default_factory=dict)


@dataclass(frozen=True)
class ReplayCheckpoint:
    index: int
    operation: str
    mode: str
    session_digest: str
    content_digest: str
    project_digest: str
    tactical_digest: str | None


@dataclass(frozen=True)
class ReplayReport:
    campaign_id: str
    seed: int
    checkpoints: tuple[ReplayCheckpoint, ...]
    final_digest: str
    verified: bool


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def verify_recording(recording, content, project, *, rules=None):
    """Verify an existing v1 GameSession including nested tactical replay.

    The domain loader rejects forged checksums, unknown rules, wrong
    Content/GameProject, invalid mission unlocks and altered battle commands.
    """
    if not isinstance(recording, dict):
        raise ReplayError("invalid_recording", "Expected a v1 GameSession dictionary")
    copy = deepcopy(recording)
    try:
        restored = GameSession.from_recording(copy, content, project, rules=rules)
        round_trip = restored.recording()
        if round_trip != copy:
            raise ReplayError("replay_divergence", "Canonical round trip differs from source")
        verified_again = GameSession.from_recording(round_trip, content, project, rules=rules)
        if verified_again.recording() != round_trip:
            raise ReplayError("replay_divergence", "Second replay differs from first")
    except ReplayError:
        raise
    except (RuleError, TypeError, KeyError, ValueError, AttributeError,
            RecursionError) as exc:
        raise ReplayError("invalid_recording", str(exc)) from exc
    return restored


def _checkpoint(index, operation, recording):
    return ReplayCheckpoint(
        index, operation, recording["mode"], recording["digest"],
        recording["content_digest"], recording["project_digest"],
        _hash(recording["tactical"]) if recording["tactical"] is not None else None,
    )


def verify_sequence(content, project, campaign_id, commands=(), *,
                    seed=17, rules=None, max_commands=1000, initial=None):
    """Play a bounded trace and restore/check it after *every* operation.

    Can continue from any verified checkpoint (including a multi-front
    siege). Failed commands are rejected and leave the last good checkpoint
    available to the caller. The source input is never mutated.
    """
    if type(max_commands) is not int or not 1 <= max_commands <= 10000:
        raise ReplayError("invalid_budget", "Expected 1..10000 commands")
    commands = tuple(commands)
    if len(commands) > max_commands:
        raise ReplayError("invalid_budget", "Trace exceeds command limit")
    if initial is None:
        session = GameSession.new(content, project, campaign_id, seed=seed, rules=rules)
    else:
        session = verify_recording(initial, content, project, rules=rules)
        if session.campaign_id != campaign_id:
            raise ReplayError("wrong_campaign", "Trace belongs to another campaign")
        if seed != session.seed:
            raise ReplayError("wrong_seed", "Initial replay seed mismatch")
    checkpoints = [_checkpoint(0, "initial", session.recording())]
    for i, command in enumerate(commands, 1):
        if not isinstance(command, ReplayCommand) or command.operation not in REPLAY_OPERATIONS:
            raise ReplayError("invalid_command", "Operation is not in the canonical replay allowlist")
        if not isinstance(command.args, (tuple, list)) or not isinstance(command.kwargs, Mapping):
            raise ReplayError("invalid_command", "Malformed replay command arguments")
        # Immutable command input for the source caller; do not invoke arbitrary
        # callables or dynamic attributes from serialized data.
        try:
            args = deepcopy(command.args)
            kwargs = deepcopy(dict(command.kwargs))
            getattr(session, command.operation)(*args, **kwargs)
            record = session.recording()
            session = verify_recording(record, content, project, rules=rules)
        except (ReplayError, RuleError, ValueError, TypeError, KeyError) as exc:
            raise ReplayError("step_failed", "Step %d (%s): %s" %
                              (i, command.operation, exc)) from exc
        checkpoints.append(_checkpoint(i, command.operation, record))
    return ReplayReport(campaign_id, session.seed, tuple(checkpoints),
                        checkpoints[-1].session_digest, True)

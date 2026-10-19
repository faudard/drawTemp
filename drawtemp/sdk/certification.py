"""R1.E — fail-closed deterministic certification of canonical gameplay.

A continuous run, a replayed run and an actual disk-restored run must agree
after *every* command. This deliberately uses the existing GameSession,
Battle and MultiFrontSession; it does not simulate rules a second time.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.core import GameSession, RuleError
from drawtemp.sdk.replay import REPLAY_OPERATIONS, ReplayCommand, verify_recording
from sporebound.game_session import digest


class CertificationError(RuleError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class CertificationStep:
    index: int
    operation: str
    mode: str
    session_sha256: str
    tactical_sha256: str | None
    rng_sha256: str | None
    ct_sha256: str | None
    events_sha256: str | None
    fronts_sha256: str | None


@dataclass(frozen=True)
class CertificationReport:
    campaign_id: str
    seed: int
    steps: tuple[CertificationStep, ...]
    final_sha256: str
    verified: bool


def _witness(index, operation, session, record):
    """Hash domain-authoritative internals, not a UI or mock projection."""
    battle = session.active_battle
    state = battle.state() if battle is not None else None
    # CT and actor activation fields live in the canonical battle state.
    actors = [{"id": unit.get("id"), "ct": unit.get("ct"),
               "active": unit.get("active"), "hp": unit.get("hp"),
               "pos": unit.get("pos")} for unit in state["units"]] if state else None
    timeline = session.fronts.state() if session.fronts is not None else None
    return CertificationStep(
        index, operation, session.mode, record["digest"],
        digest(record["tactical"]) if record["tactical"] is not None else None,
        digest(state["rng"]) if state else None,
        digest({"tick": state["tick"], "active": state["active"],
                "units": actors}) if state else None,
        digest(state["events"]) if state else None,
        digest(timeline) if timeline is not None else None,
    )


def _without_ephemeral_ids(record, identities):
    """Normalize only previously witnessed random Battle identities.

    The map is persistent across steps, including after return_to_campaign,
    when a finished battle's UUID no longer occurs in the tactical record.
    Every other Content/CT/RNG/command/event field remains authoritative.
    """
    value = deepcopy(record)
    value.pop("digest", None)
    tactical = value.get("tactical")
    if isinstance(tactical, dict) and isinstance(tactical.get("battle_id"), str):
        original = tactical["battle_id"]
        token = identities.setdefault(
            original, "<battle-%d>" % len(set(identities.values())))
        tactical["battle_id"] = token
    groups = value.get("front_battle_ids")
    if isinstance(groups, dict):
        for group, battles in sorted(groups.items()):
            if isinstance(battles, dict):
                for key, original in sorted(battles.items()):
                    if isinstance(original, str):
                        token = identities.setdefault(
                            original, "<%s/%s>" % (group, key))
                        battles[key] = token

    # Campaign progress may retain UUIDs after its Battle is finalized. Only
    # strings equal to already witnessed battle IDs may be normalized.
    def known(value):
        if isinstance(value, str):
            return identities.get(value, value)
        if isinstance(value, dict):
            return {key: known(item) for key, item in value.items()}
        if isinstance(value, list):
            return [known(item) for item in value]
        return value

    if "progress" in value:
        value["progress"] = known(value["progress"])
    return value


def certify_trace(content, project, campaign_id, commands, *,
                  seed=17, initial=None, max_commands=1000):
    """Verify independent continuous/replayed/disk-restored execution paths.

    `initial` is a fully authenticated GameSession checkpoint, not a mutable
    state snapshot. Every accepted action must produce exactly the same JSON
    and RNG/CT/event hashes in both timelines and after a real disk write.
    """
    if type(max_commands) is not int or not 1 <= max_commands <= 10000:
        raise CertificationError("invalid_budget", "Expected 1..10000 commands")
    actions = tuple(commands)
    if len(actions) > max_commands:
        raise CertificationError("invalid_budget", "Trace exceeds command budget")
    try:
        continuous = (GameSession.new(content, project, campaign_id, seed=seed)
                      if initial is None
                      else verify_recording(initial, content, project))
        if continuous.campaign_id != campaign_id or continuous.seed != seed:
            raise CertificationError("wrong_start", "Campaign or seed differs from checkpoint")
        source = continuous.recording()
        replayed = verify_recording(source, content, project)
    except CertificationError:
        raise
    except (RuleError, TypeError, KeyError, ValueError) as exc:
        raise CertificationError("invalid_start", str(exc)) from exc

    steps = [_witness(0, "initial", continuous, source)]
    # Identifier leases survive battle completion and front transitions.
    continuous_ids, resumed_ids = {}, {}
    _without_ephemeral_ids(source, continuous_ids)
    _without_ephemeral_ids(source, resumed_ids)
    with TemporaryDirectory(prefix="drawtemp-r1e-") as folder:
        path = Path(folder) / "checkpoint.json"
        for index, command in enumerate(actions, 1):
            if (not isinstance(command, ReplayCommand)
                    or command.operation not in REPLAY_OPERATIONS
                    or not isinstance(command.args, (tuple, list))
                    or not isinstance(command.kwargs, dict)):
                raise CertificationError("invalid_command",
                                         "Unsupported or malformed command at step %d" % index)
            try:
                # Two independent mutable engines from the same verified origin.
                # All command values are copied to avoid cross-run aliasing.
                getattr(continuous, command.operation)(
                    *deepcopy(command.args), **deepcopy(command.kwargs))
                getattr(replayed, command.operation)(
                    *deepcopy(command.args), **deepcopy(command.kwargs))
                recorded = continuous.recording()
                second = replayed.recording()
                normal_continuous = _without_ephemeral_ids(recorded, continuous_ids)
                normal_resumed = _without_ephemeral_ids(second, resumed_ids)
                if normal_continuous != normal_resumed:
                    # Identify the first real mismatching field without
                    # weakening exact comparison of the two authenticated
                    # recordings. This diagnostics-only path is especially
                    # useful for UUID and campaign-progress regressions.
                    def first_difference(left, right, location="$"):
                        if type(left) is not type(right):
                            return location + " (type)"
                        if isinstance(left, dict):
                            if set(left) != set(right):
                                return location + " (keys " + repr(
                                    sorted(set(left) ^ set(right))) + ")"
                            for key in sorted(left):
                                if left[key] != right[key]:
                                    return first_difference(
                                        left[key], right[key], location + "." + str(key))
                        elif isinstance(left, list):
                            if len(left) != len(right):
                                return location + " (length)"
                            for offset, (a, b) in enumerate(zip(left, right)):
                                if a != b:
                                    return first_difference(
                                        a, b, location + "[" + str(offset) + "]")
                        return location
                    raise CertificationError(
                        "runtime_divergence",
                        "Continuous and independently resumed engines differ at " +
                        first_difference(normal_continuous, normal_resumed))
                # Verify CT, RNG, event streams and front timelines *before*
                # re-binding the resumed handle to the canonical source UUID.
                left = _witness(index, command.operation, continuous, recorded)
                right = _witness(index, command.operation, replayed, second)
                if (left.mode, left.rng_sha256, left.ct_sha256,
                    left.events_sha256, left.fronts_sha256) != (
                    right.mode, right.rng_sha256, right.ct_sha256,
                    right.events_sha256, right.fronts_sha256):
                    raise CertificationError("state_divergence",
                                             "CT/RNG/events/fronts differ across independent runs")
                # Real disk roundtrip, not an in-memory deepcopy.
                continuous.save(path)
                raw = path.read_bytes()
                disk = GameSession.load(path, content, project)
                if path.read_bytes() != raw:
                    raise CertificationError("disk_mutation", "Loading modified checkpoint")
                if disk.recording() != recorded:
                    raise CertificationError("disk_divergence",
                                             "Checkpoint changes after disk replay")
                replayed = verify_recording(recorded, content, project)
                # The resumed timeline now holds the authenticated continuous
                # battle IDs, rather than the independent IDs from the command
                # just executed. Preserve each established token lease across
                # this switch; a later command must not mislabel the same
                # battle as a fresh identity or rewrite campaign history.
                resumed_ids.update(continuous_ids)
                replay_step = _witness(index, command.operation, replayed, recorded)
                if replay_step != _witness(index, command.operation, continuous, recorded):
                    raise CertificationError("state_divergence",
                                             "CT/RNG/events/fronts differ after replay")
            except CertificationError:
                raise
            except (RuleError, ValueError, TypeError, OSError, KeyError) as exc:
                raise CertificationError(
                    "step_failed", "Step %d (%s): %s" %
                    (index, command.operation, exc)) from exc
            steps.append(replay_step)
    return CertificationReport(campaign_id, seed, tuple(steps),
                               steps[-1].session_sha256, True)

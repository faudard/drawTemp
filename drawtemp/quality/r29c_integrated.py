"""R29.C independent verification of real ActionRuntime and GameSession routes.

Proof of two separate runtimes does NOT certify a combined action/CT session.
No shadow engine, new save schema or fabricated release evidence.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

MAX_COMMANDS = 2000
ALLOWED_ROUTE_OPS = frozenset({
    "route_move", "route_transition", "execute", "abandon_encounter",
    "return_to_campaign",
})


def _digest(document):
    return sha256(json.dumps(document, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _trace(commands, *, route=False):
    if type(commands) is not list or not 1 <= len(commands) <= MAX_COMMANDS:
        raise ValueError("Provide 1..2000 commands")
    detached = deepcopy(commands)
    if route:
        for entry in detached:
            if (type(entry) is not dict or set(entry) != {"op", "args"}
                    or type(entry["op"]) is not str
                    or entry["op"] not in ALLOWED_ROUTE_OPS
                    or type(entry["args"]) is not list):
                raise ValueError("Unknown or malformed GameSession route command")
    else:
        for tick, entry in enumerate(detached, 1):
            if (type(entry) is not dict or type(entry.get("tick")) is not int
                    or entry["tick"] != tick):
                raise ValueError("R26 input ticks must be contiguous integers starting at 1")
    return detached


def _interval(value):
    if type(value) is not int or not 1 <= value <= 500:
        raise ValueError("Checkpoint interval must be 1..500")
    return value


def _blocked(component):
    return {"status": "blocked", "component": component,
            "reason": "Required gameplay capability not present on this commit",
            "runtime_verified": False, "release_certified": False}


def audit_action_disk(scene, commands, *, checkpoint_every=5):
    """Compare a live R26 execution to an independently saved/reloaded copy.

    Enforce tick equality, disk restore parity, invalid-checkpoint rejection
    and non-mutation. Passing this is PARTIAL, never hybrid certification.
    """
    _interval(checkpoint_every)
    trace = _trace(commands)
    from importlib.util import find_spec
    try:
        available = find_spec("sporebound.action_runtime")
    except ModuleNotFoundError:
        available = None
    if available is None:
        return _blocked("R26 ActionRuntime")
    from sporebound.action_runtime import ActionRuntime

    source = deepcopy(scene)
    original = deepcopy(commands)
    live, recovered = ActionRuntime(source), ActionRuntime(source)
    checkpoints, tick_digests = [], []
    with TemporaryDirectory(prefix="drawtemp-r29c-action-") as directory:
        root = Path(directory)
        for index, cmd in enumerate(trace, 1):
            events_live = live.step(deepcopy(cmd))
            events_recovered = recovered.step(deepcopy(cmd))
            if events_live != events_recovered or live.digest() != recovered.digest():
                raise ValueError(f"R26 divergence at tick {index}")
            tick_digests.append(live.digest())
            if index % checkpoint_every == 0 or index == len(trace):
                slot = root / "action-save.json"
                recovered.save(slot)
                before = slot.read_bytes()
                recovered = ActionRuntime.load(slot, expected_scene=source)
                if before != slot.read_bytes() or recovered.recording() != live.recording():
                    raise ValueError(f"R26 disk restore diverged at tick {index}")
                checkpoints.append({"tick": index, "state_sha256": recovered.digest(),
                                    "save_sha256": sha256(before).hexdigest()})
                altered = json.loads(before)
                altered["state_digest"] = "0" * 64
                broken = root / "corrupted.json"
                broken.write_text(json.dumps(altered), encoding="utf-8")
                try:
                    ActionRuntime.load(broken, expected_scene=source)
                except (ValueError, TypeError, KeyError):
                    pass
                else:
                    raise ValueError("R26 accepted a forged action checkpoint")
        if live.recording() != recovered.recording():
            raise ValueError("R26 final continuous and resumed recordings differ")
        if ActionRuntime.from_recording(live.recording(), expected_scene=source).digest() != live.digest():
            raise ValueError("R26 final replay diverged")
    if commands != original or scene != source:
        raise ValueError("R26 certification mutated its source input")
    return {"schema": 1, "status": "partial", "component": "R26 ActionRuntime",
            "scene_sha256": _digest(scene), "inputs_sha256": _digest(commands),
            "ticks": len(trace), "tick_digests_sha256": _digest(tick_digests),
            "checkpoints": checkpoints, "final_state_sha256": live.digest(),
            "tamper_rejected": True, "runtime_verified": True,
            "release_certified": False,
            "scope": "real R26 single-scene save/restore and deterministic tick replay only"}


def audit_route_disk(session, commands, *, checkpoint_every=2):
    """Compare live and disk-restored *real* GameSession route commands.

    Authored flags/prerequisites are obtained from the initial genuine session;
    this does not bypass any transition guards or create a new router.
    """
    _interval(checkpoint_every)
    trace = _trace(commands, route=True)
    if (not hasattr(session, "route_transition") or
            not getattr(getattr(session, "scene_router", None), "enabled", False)):
        return _blocked("R25.B GameSession.SceneRouter")
    from sporebound.game_session import GameSession

    initial = session.recording()
    content, project = session.content, session.project
    source_project = project.to_dict()
    live = GameSession.from_recording(initial, content, project)
    recovered = GameSession.from_recording(initial, content, project)
    visited_modes, visits, checkpoints = [live.mode], [live.route_scene], []
    with TemporaryDirectory(prefix="drawtemp-r29c-route-") as directory:
        slot = Path(directory) / "route-save.json"
        for index, entry in enumerate(trace, 1):
            op, args = entry["op"], entry["args"]
            getattr(live, op)(*deepcopy(args))
            getattr(recovered, op)(*deepcopy(args))
            if live.recording() != recovered.recording():
                raise ValueError(f"GameSession route diverged at operation {index}")
            visited_modes.append(live.mode)
            visits.append(live.route_scene)
            if index % checkpoint_every == 0 or index == len(trace):
                recovered.save(slot)
                original_bytes = slot.read_bytes()
                recovered = GameSession.load(slot, content, project)
                if (original_bytes != slot.read_bytes() or
                        recovered.recording() != live.recording()):
                    raise ValueError(f"GameSession route restore diverged at operation {index}")
                checkpoints.append({"operation": index,
                                    "recording_sha256": _digest(live.recording()),
                                    "save_sha256": sha256(original_bytes).hexdigest()})
        if live.recording() != recovered.recording():
            raise ValueError("GameSession final route recording diverged")
    if project.to_dict() != source_project or session.recording() != initial:
        raise ValueError("Route certification mutated project or original session")
    crossed = ("battle" in visited_modes and visited_modes[-1] == "campaign"
               and len(set(visits)) > 1 and len(visits) >= 3)
    return {"schema": 1, "status": "partial" if crossed else "inconclusive",
            "component": "R25.B GameSession.SceneRouter",
            "initial_sha256": _digest(initial), "commands_sha256": _digest(trace),
            "operations": len(trace), "visited_modes": visited_modes,
            "visited_scenes": visits, "checkpoints": checkpoints,
            "final_recording_sha256": _digest(live.recording()),
            "real_ct_route_verified": crossed, "runtime_verified": crossed,
            "release_certified": False,
            "scope": "real GameSession tactical route and persistence; not R26 realtime handoff"}


def assemble_evidence(action=None, routes=None, *, revision="unknown"):
    """NO-GO until one canonical session owns action and CT simulations."""
    for item in (action, routes):
        if item is not None and (type(item) is not dict or
                                 item.get("status") not in ("partial", "blocked", "inconclusive", "fail")):
            raise ValueError("Invalid runtime audit evidence")
    return {"schema": 1, "kind": "drawtemp-r29c-dual-runtime-evidence",
            "revision": revision,
            "action": action or _blocked("R26 ActionRuntime"),
            "tactical_route": routes or _blocked("R25.B GameSession.SceneRouter"),
            "hybrid": {"status": "blocked", "reason":
                "No GameSession-owned action runtime, shared cross-mode checkpoint,"
                " inventory transfer and 60Hz↔CT replay in integrated master"},
            "release_ready": False, "decision": "no-go"}

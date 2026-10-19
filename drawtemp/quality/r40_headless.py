"""R40.B source-level proof for reference journeys, NEVER release certification.

The four routes below use canonical GameSession implementations, validated
Content/GameProject and actual disk checkpoints; no mocked or substitute engine.
The report records missing end-to-end Player, UX, GPU, licensing and clean-PC
release evidence explicitly, even when every headless route succeeds.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.core import GameSession
from drawtemp.sdk.r40_starters import STARTER_KINDS, create_starter_pair
from drawtemp.sdk.reference import MISSION
from sporebound.ai import choose_command
from sporebound.metroidvania import analyze_metroidvania
from sporebound.model import RuleError


BLOCKERS = (
    "R40.1: schema compatibility/migration audit across 6.x and 7.x",
    "R40.2: complete independently playtested Jeanne/siege game",
    "R40.3: original full village/dungeon/puzzles/boss journey and Player",
    "R40.4: ability-gated physical platform traversal, boss and Player",
    "R40.5: visually instanced roguelite rooms, encounters and Player",
    "R40.7: novice Studio creation/edit/playtest with human observation",
    "R40.8: reproducible CPU/RAM/GPU p95/p99 and endurance on hardware",
    "R40.9: three-OS clean-machine export, crash recovery, asset-rights proof",
    "R40.10: accessibility, localized GUI and visual review",
    "R40.11: dependency/SBOM, plugin and asset license review",
    "R40.12: signed GO/NO-GO from final master SHA",
)


@dataclass(frozen=True)
class SourceProbe:
    starter: str
    passed: bool
    scenario: str
    checkpoints: int
    error: str = ""


def _restore(session, content, project):
    """Real save/load; compare serialized authoritative state byte-for-byte."""
    with TemporaryDirectory(prefix="drawtemp-r40-") as directory:
        path = Path(directory) / "checkpoint.json"
        session.save(path)
        loaded = GameSession.load(path, content, project)
        if loaded.recording() != session.recording():
            raise AssertionError("GameSession changed across disk checkpoint")
        return loaded


def _arrive_at_waystone(session):
    """Fixed-step replay into an interactive tile, no frame clock or Qt."""
    for _ in range(4):
        session.route_realtime_step(1, 0)
    if session.route_state()["position"] != [2, 1]:
        raise AssertionError("Unexpected deterministic waypoint position")
    session.route_interact("waystone")


def _srpg(content, project):
    session = GameSession.new(content, project, "main", seed=17)
    session.choose_story_option("enter")
    session.start_mission(MISSION)
    session.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
    if session.active_battle.board.tile((3, 4)).blocked:
        raise AssertionError("Authentic tactical lever did not open the gate")
    session = _restore(session, content, project)
    if session.active_battle is None or session.mode != "battle":
        raise AssertionError("CT mission did not restore")
    return 1


def _adventure(content, project):
    session = GameSession.new(content, project, "main", seed=17)
    if session.route_scene != "arrival":
        raise AssertionError("Starter did not enter its authored village")
    before = session.recording()
    try:
        session.route_transition("to_ruins")
    except RuleError:
        pass
    else:
        raise AssertionError("Missing-waystone route was unexpectedly allowed")
    if session.recording() != before:
        raise AssertionError("Rejected transition mutated the checkpoint")
    _arrive_at_waystone(session)
    session = _restore(session, content, project)
    session.route_transition("to_ruins")
    _arrive_at_waystone(session)
    session = _restore(session, content, project)
    session.route_transition("to_citadel")
    # Follow a real movement path to the exit; avoid the blocked [3, 2].
    for _ in range(24):
        session.route_realtime_step(1, 0)
    for _ in range(16):
        session.route_realtime_step(0, 1)
    outcome = session.route_interact("exit")
    if not outcome["finished"] or not session.route_state()["completed"]:
        raise AssertionError("Final authored exploration scene not completed")
    session = _restore(session, content, project)
    if session.route_scene != "r40_citadel" or session.mode != "campaign":
        raise AssertionError("End-of-journey route was lost")
    if session.route_history != ["to_ruins", "to_citadel"]:
        raise AssertionError("Route history did not survive checkpoints")
    return 3


def _metroidvania(content, project):
    graph = project.extensions["drawtemp.metroidvania"]["data"]
    proof = analyze_metroidvania(graph, scene_ids=project.exploration)
    if not (proof["complete"] and proof["safe"]
            and proof["goal_reachable"]):
        raise AssertionError("Abstract ability graph is not safe")
    witness = [step["room"] for step in proof["witness"]]
    if witness != ["arrival", "r40_ruins", "arrival", "r40_citadel"]:
        raise AssertionError("Double-jump dependency witness changed")
    # Existing R25 routes are narrative interactions only. Never claim
    # that the R33 capability pickup powers physical R32 jumping.
    session = GameSession.new(content, project, "main", seed=17)
    _arrive_at_waystone(session)
    session.route_transition("to_ruins")
    _arrive_at_waystone(session)
    session = _restore(session, content, project)
    session.route_transition("to_citadel")
    session = _restore(session, content, project)
    if session.route_scene != "r40_citadel":
        raise AssertionError("Authored room cursor was not persisted")
    return 2


def _roguelite(content, project):
    session = GameSession.new(content, project, "main", seed=19)
    before_gold = session.progress.gold
    state = session.roguelite_state()
    session.roguelite_checkpoint()
    for room in state["layout"]["route"][1:]:
        session.roguelite_move(room)
    finished = session.roguelite_state()
    if finished["status"] != "won" or finished["meta"]["coins"] != 7:
        raise AssertionError("Original R34 run did not settle exactly once")
    if session.progress.gold != before_gold:
        raise AssertionError("Roguelite reward leaked into legacy CT campaign")
    session = _restore(session, content, project)
    session.roguelite_restart()
    if session.roguelite_state()["meta"]["wins"] != 1:
        raise AssertionError("Historical meta reward was duplicated")
    if session.roguelite_state()["inventory"]["loot"] != 0:
        raise AssertionError("Run inventory leaked across restart")
    _restore(session, content, project)
    return 2


_PROBES = {
    "r40-srpg": (_srpg, "Tactical lever, battle and disk checkpoint"),
    "r40-adventure": (_adventure, "Gated village > ruins > citadel, fixed ticks, disk resume"),
    "r40-metroidvania": (_metroidvania, "Static ability witness and real routed scene checkpoints"),
    "r40-roguelite": (_roguelite, "Seeded R34 run win, durable meta and restart"),
}


def audit_r40_source() -> dict:
    """Run bounded authoritative source checks; always retain release blockers."""
    if set(_PROBES) != set(STARTER_KINDS):
        raise AssertionError("R40 source probes and starter catalogue diverge")
    probes = []
    for kind in STARTER_KINDS:
        fn, scenario = _PROBES[kind]
        try:
            content, project = create_starter_pair(kind)
            project.validate(content)
            checkpoints = fn(content, project)
            probes.append(SourceProbe(kind, True, scenario, checkpoints))
        except Exception as exc:  # Report every failing genre without false green.
            probes.append(SourceProbe(kind, False, scenario, 0,
                                      type(exc).__name__ + ": " + str(exc)))
    return {
        "schema": 1, "kind": "drawtemp-r40-source-audit",
        "source_checks_passed": all(probe.passed for probe in probes),
        "probes": [asdict(probe) for probe in probes],
        "release_ready": False,
        "decision": "NO-GO",
        "missing_release_evidence": list(BLOCKERS),
        "limits": [
            "No Player Qt runtime, 3-OS packaged export, or actual GPU certified",
            "R33 reachability is abstract; real jumping and boss gates unproven",
            "R40 source starters are not four complete production games",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--require-release", action="store_true",
                        help="Fail closed: release is not yet certified")
    args = parser.parse_args(argv)
    result = audit_r40_source()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    if not result["source_checks_passed"]:
        return 1
    return 2 if args.require_release else 0


if __name__ == "__main__":
    raise SystemExit(main())

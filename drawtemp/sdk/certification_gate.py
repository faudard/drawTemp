"""Executable R1.E certification gate: canonical Jeanne trace + disk recovery.

Run: python -m drawtemp.sdk.certification_gate --report r1e-certification.json
This is a *headless* gate, not an R14 GUI/GPU certification.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from drawtemp.core import GameSession
from drawtemp.sdk.certification import certify_trace
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.replay import ReplayCommand
from sporebound.ai import choose_command
from sporebound.storage import write_json


def sample_trace(content, project, seed, max_combat_steps):
    session = GameSession.new(content, project, "main", seed=seed)
    trace = [
        ReplayCommand("choose_story_option", ("enter",)),
        ReplayCommand("start_mission", (MISSION,)),
        ReplayCommand("execute", ({"kind": "interact", "unit": "jeanne",
                                   "object": "lever"},)),
    ]
    for command in trace:
        getattr(session, command.operation)(*command.args, **command.kwargs)
    if session.active_battle.board.tile((3, 4)).blocked:
        raise RuntimeError("Jeanne gate/lever invariant failed")
    for _ in range(max_combat_steps):
        battle = session.active_battle
        if battle is None or battle.result:
            break
        command = choose_command(battle)
        session.execute(command)
        trace.append(ReplayCommand("execute", (command,)))
    return tuple(trace)


def run_certification(*, seeds=(1, 17, 221), max_combat_steps=12):
    if type(max_combat_steps) is not int or not 1 <= max_combat_steps <= 100:
        raise ValueError("Expected 1..100 tactical actions")
    content, project = reference_project()
    results = []
    for seed in seeds:
        if type(seed) is not int or seed < 0:
            raise ValueError("Seeds must be positive integers")
        trace = sample_trace(content, project, seed, max_combat_steps)
        report = certify_trace(content, project, "main", trace, seed=seed)
        if not report.verified or len(report.steps) != len(trace) + 1:
            raise AssertionError("Incomplete R1.E certification report")
        if not any(step.rng_sha256 and step.ct_sha256 and step.events_sha256
                   for step in report.steps):
            raise AssertionError("RNG/CT/events witnesses missing")
        results.append(asdict(report))
    return {
        "kind": "drawtemp_r1e_headless_certification",
        "schema": 1, "result": "pass", "content_version": 1,
        "project_version": 1, "game_session_version": 1,
        "scenarios": results,
        "scope": "Jeanne R1: replay, RNG, CT, events and disk restore per action",
        "exclusions": ["Qt/UI", "GPU/real hardware", "R14 platform packaging"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 17, 221])
    parser.add_argument("--combat-steps", type=int, default=12)
    args = parser.parse_args(argv)
    data = run_certification(seeds=tuple(args.seeds),
                             max_combat_steps=args.combat_steps)
    if args.report:
        write_json(args.report, data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

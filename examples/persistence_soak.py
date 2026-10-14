"""R8.13 deterministic persistence soak with JSON metrics and no GUI.

python -m examples.persistence_soak --iterations 3 --commands 48 --output persistence.json
"""
from __future__ import annotations

import argparse
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc

from examples.reliability_gate import fixture, run_case
from sporebound.game_session import GameSession, digest
from sporebound.long_session import LongSessionAutosave, LongSessionStore
from sporebound.model import require
from sporebound.storage import write_json


def percentile(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p / 100))] if ordered else 0.0


def run_soak(*, iterations=3, commands=48):
    require(type(iterations) is int and 1 <= iterations <= 100, "Invalid soak iterations")
    require(type(commands) is int and 1 <= commands <= 500, "Invalid soak command count")
    content, project = fixture()
    tracemalloc.start()
    total_start = perf_counter()
    durations, cases = [], []
    try:
        for index in range(iterations):
            seed = index + 1
            with TemporaryDirectory() as folder:
                # Creation/deletion of temporary campaign slot files is part
                # of the gate. Each case uses its own independently owned slot.
                store = LongSessionStore(Path(folder) / "slot.json", checkpoint_every=8)
                actor = LongSessionAutosave(
                    GameSession.new(content, project, "main", seed=seed), store)
                store.initialize(actor.session)
                for request_id, op, arguments in [
                        ("story", "choose_story_option", ("assault",)),
                        ("start", "start_mission", ("gate",))]:
                    started = perf_counter()
                    actor.perform(request_id, op, *arguments)
                    durations.append(perf_counter() - started)
                for turn in range(commands):
                    started = perf_counter()
                    actor.perform("turn-%04d" % turn, "execute", {"kind": "end"})
                    durations.append(perf_counter() - started)
                    if turn % 8 == 0 or turn == commands - 1:
                        saved = actor.session.recording()
                        loaded = store.load(content, project)
                        require(loaded.recording() == saved,
                                "Soak save/replay divergence")
                require(len(actor.session.battle.commands) == commands,
                        "Soak command duplication detected")
                before_retry = actor.session.recording()
                duplicate = actor.perform("turn-%04d" % (commands - 1),
                                          "execute", {"kind": "end"})
                require(not duplicate.applied and
                        before_retry == actor.session.recording(),
                        "Soak retry duplicated tactical commands")
                checkpoint = store.store.load_with_status(content, project)
                cases.append({"seed": seed, "commands": commands,
                              "checkpoint_sequence": checkpoint.sequence,
                              "final_digest": actor.session.recording()["digest"],
                              "max_checkpoint_bytes": max(
                                  store.store.path.stat().st_size,
                                  store.store.backup.stat().st_size
                                  if store.store.backup.exists() else 0)})
                # Existing full three-mission gate covers completed campaigns
                # as well as reward idempotency, fronts and narrative branches.
                control = run_case(seed, folder, resume=False, ending="spare")
                resumed = run_case(seed, folder, resume=True,
                                   ending="spare", checkpoint_every=5)
                require(control["digest"] == resumed["digest"] and
                        control["trace"] == resumed["trace"],
                        "Completed campaign replay diverged")
                cases[-1]["campaign_digest"] = control["digest"]
        peak_bytes = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return {"version": 1, "gate": "R8.13", "verified": True,
            "iterations": iterations, "commands_per_iteration": commands,
            "elapsed_seconds": round(perf_counter() - total_start, 6),
            "operation_seconds": {
                "p50": round(percentile(durations, 50), 6),
                "p95": round(percentile(durations, 95), 6),
                "p99": round(percentile(durations, 99), 6),
                "max": round(max(durations), 6)},
            "python_peak_tracemalloc_bytes": peak_bytes,
            "cases": cases,
            "report_digest": digest(cases)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--commands", type=int, default=48)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_soak(iterations=args.iterations, commands=args.commands)
    write_json(args.output, report)
    print("R8.13 verified", len(report["cases"]), "cases:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

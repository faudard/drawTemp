"""R24.F: cooperative, bounded multi-seed Battle Lab with real replay proofs.

No alternate Battle/AI or worker thread. Each step invokes the existing R13
run_lab for ONE seed; cancellation takes effect between seeds. Wall/CPU
measurements are telemetry, not deterministic gameplay data or GPU evidence.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
from time import perf_counter_ns, process_time_ns

from sporebound.battle_lab import run_lab
from sporebound.balance3 import percentile
from sporebound.model import Content, require

SCHEMA = 1
MAX_SEEDS = 128
MAX_COMMANDS = 1500
MAX_TOTAL_COMMANDS = 50000


def _fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _round(value):
    return round(value, 4)


def _percentiles(values, prefix):
    if not values:
        return {prefix + key: None for key in ("_p50", "_p95", "_p99")}
    return {prefix + "_p50": _round(percentile(values, 50)),
            prefix + "_p95": _round(percentile(values, 95)),
            prefix + "_p99": _round(percentile(values, 99))}


class MassiveSimulationJob:
    """Explicit step/cancel budget; source Content and Campaign stay detached.

    Calling step is synchronous and bounded by ONE canonical Battle run; a
    cancellation cannot interrupt an in-flight Battle safely. The final
    report separates deterministic results from host-dependent timings.
    """

    def __init__(self, content, mission_id, *, seeds=tuple(range(1, 9)),
                 max_commands=50, rules=None, progress=None,
                 initial_state=None, max_total_commands=MAX_TOTAL_COMMANDS):
        require(isinstance(content, Content) and mission_id in content.missions,
                "Expected a canonical mission")
        require(type(seeds) in (list, tuple) and 1 <= len(seeds) <= MAX_SEEDS
                and all(type(seed) is int and 0 <= seed < 2**32 for seed in seeds)
                and len(seeds) == len(set(seeds)), "Expected 1..128 distinct unsigned seeds")
        require(type(max_commands) is int and 1 <= max_commands <= MAX_COMMANDS,
                "Command cap must be 1..1500")
        require(type(max_total_commands) is int and 1 <= max_total_commands <= MAX_TOTAL_COMMANDS
                and len(seeds) * max_commands <= max_total_commands,
                "Campaign command budget exceeded")
        require(initial_state is None or type(initial_state) is dict,
                "Expected an optional native initial-state dictionary")
        self._content = deepcopy(content)
        self._before = _fingerprint(content.to_dict())
        self._rules = deepcopy(rules)
        self._progress = deepcopy(progress)
        self._initial_state = deepcopy(initial_state)
        self.mission = mission_id
        self.seeds = tuple(seeds)
        self.max_commands = max_commands
        self._cursor = 0
        self._cancelled = False
        self._samples = []
        self._durations = []
        self._cpu_times = []
        self._content_sha256 = None
        self._rules_digest = None

    @property
    def remaining(self):
        return len(self.seeds) - self._cursor

    @property
    def finished(self):
        return self._cancelled or self.remaining == 0

    def cancel(self):
        """Cooperative cancellation; already verified samples are retained."""
        self._cancelled = True

    def step(self):
        """Advance one real replay-verified seed. Never change authored input."""
        if self.finished:
            return None
        seed = self.seeds[self._cursor]
        start_wall, start_cpu = perf_counter_ns(), process_time_ns()
        report = run_lab(self._content, self.mission, seeds=(seed,),
                         max_commands=self.max_commands, rules=self._rules,
                         progress=deepcopy(self._progress),
                         initial_state=deepcopy(self._initial_state))
        wall_ms = (perf_counter_ns() - start_wall) / 1e6
        cpu_ms = (process_time_ns() - start_cpu) / 1e6
        require(report["runs"] == 1 and report["seeds"] == [seed]
                and report["samples"][0]["replay_verified"] is True,
                "Native R13 replay certification failed")
        fingerprint = report["content_sha256"]
        rules_fp = _fingerprint(report["rules_manifest"])
        if self._content_sha256 is None:
            self._content_sha256, self._rules_digest = fingerprint, rules_fp
        require(fingerprint == self._content_sha256 and rules_fp == self._rules_digest,
                "Input or rules changed across seeds")
        require(_fingerprint(self._content.to_dict()) == self._before,
                "Simulation mutated the authored Content")
        row = deepcopy(report["samples"][0])
        self._samples.append(row)
        self._durations.append(_round(wall_ms))
        self._cpu_times.append(_round(cpu_ms))
        self._cursor += 1
        return deepcopy({
            "seed": seed, "result": row["result"],
            "replay_verified": True, "commands": row["commands"],
            "digest": row["digest"], "wall_ms": _round(wall_ms),
            "process_cpu_ms": _round(cpu_ms),
            "completed": self._cursor, "total": len(self.seeds),
        })

    def run(self):
        while not self.finished:
            self.step()
        return self.report()

    def report(self):
        """May be partial or cancelled; never falsely mark an incomplete run passed."""
        counts = {name: sum(x["result"] == name for x in self._samples)
                  for name in ("victory", "defeat", "draw", "limit")}
        result = {
            "kind": "r24f-massive-battle-lab", "schema": SCHEMA,
            "mission": self.mission, "content_sha256": self._before,
            "native_rules_sha256": self._rules_digest,
            "seeds_requested": list(self.seeds),
            "seeds_completed": list(self.seeds[:self._cursor]),
            "max_commands_per_seed": self.max_commands,
            "completed": self._cursor, "requested": len(self.seeds),
            "status": ("cancelled" if self._cancelled else
                       "completed" if self.remaining == 0 else "partial"),
            "all_replays_verified": all(x["replay_verified"] for x in self._samples),
            "outcomes": counts,
            "samples": deepcopy(self._samples),
            # Stable digest only covers domain-native outcomes, not timing.
            "deterministic_sha256": _fingerprint(self._samples),
            "telemetry": {
                "scope": "host-process CPU/wall, not gameplay ticks, GPU or human play minutes",
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                **_percentiles(self._durations, "wall_ms"),
                **_percentiles(self._cpu_times, "process_cpu_ms"),
                "per_seed": [{"seed": seed, "wall_ms": self._durations[i],
                              "process_cpu_ms": self._cpu_times[i]}
                             for i, seed in enumerate(self.seeds[:self._cursor])],
            },
        }
        return result


def compare_massive_runs(before, after):
    """Fail closed for different workloads; compare deterministic seed outcomes.

    Timings are intentionally *not* treated as reproducible evidence of game
    balance or a cross-machine CPU performance gate.
    """
    for report in (before, after):
        require(type(report) is dict and report.get("kind") == "r24f-massive-battle-lab"
                and report.get("schema") == SCHEMA and report.get("status") == "completed"
                and report.get("all_replays_verified") is True
                and type(report.get("samples")) is list
                and len(report["samples"]) == report.get("requested")
                and len(report["samples"]) == report.get("completed"),
                "Require full replay-verified R24.F reports")
    for key in ("mission", "seeds_requested", "max_commands_per_seed", "content_sha256",
                "native_rules_sha256"):
        require(before[key] == after[key], "Incompatible R24.F comparison: " + key)
    previous = [(x["seed"], x["digest"], x["result"], x["commands"])
                for x in before["samples"]]
    current = [(x["seed"], x["digest"], x["result"], x["commands"])
               for x in after["samples"]]
    issues = []
    if previous != current:
        issues.append("Canonical battle outcomes or replay digests differ")
    return {"kind": "r24f-massive-comparison", "schema": SCHEMA,
            "passed": not issues, "issues": issues,
            "samples": len(current), "content_sha256": after["content_sha256"],
            "note": "Host wall/CPU telemetry excluded from deterministic comparison"}


def save_massive_report(path, report):
    """Create-only reporting. Never overwrite authored Content, saves or baselines."""
    require(type(report) is dict and report.get("kind") == "r24f-massive-battle-lab"
            and report.get("schema") == SCHEMA, "Invalid simulation report")
    target = Path(path)
    require(not target.is_symlink(), "Report destination cannot be a symlink")
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, ensure_ascii=False, indent=2)
        stream.write("\n")
    return target

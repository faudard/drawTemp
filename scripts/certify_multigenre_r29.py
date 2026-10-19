#!/usr/bin/env python3
"""R29.A — bounded multi-genre release evidence (NOT a release certificate).

Examples:
  python scripts/certify_multigenre_r29.py --report build/r29-report.json
  python scripts/certify_multigenre_r29.py --aggregate build/r29-artifacts --report build/r29-matrix.json
  python scripts/certify_multigenre_r29.py --report build/r29-report.json --require-release

Only the already integrated tactical, R14 and R15 contracts run today.
Action fixed-tick, RPG turn, approved goldens, hardware and clean-machine
evidence remain blocked until real adapters and reviewable proof exist.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drawtemp.quality.r29 import (
    PROBES, aggregate_matrix, create_report, verify_report, write_json,
)

ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    "tactical_replay": ("tests_standalone.test_drawtemp5_r1e",),
    "visual_contract": ("tests_standalone.test_drawtemp5_r14_visual",),
    "save_recovery": ("tests_standalone.test_drawtemp5_r14_recovery",),
    "export_contract": ("tests_standalone.test_drawtemp5_r15",),
    "asset_contract": ("tests_standalone.test_drawtemp5_int03",),
    "replay_diagnostics": ("tests_standalone.test_drawtemp5_r13",),
    "path_coverage": ("tests_standalone.test_campaign_path_certification_r515",),
}
assert set(SUITES) == set(PROBES)


def source_revision():
    value = os.environ.get("GITHUB_SHA")
    if value:
        return value
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown-local-revision"


def _probe(name, destination, *, timeout=300):
    command = [sys.executable, "-m", "unittest", *SUITES[name], "-q"]
    log = destination / (name + ".log")
    try:
        process = subprocess.run(
            command, cwd=ROOT, text=True, encoding="utf-8",
            errors="replace", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout, check=False)
        output = process.stdout or "(unittest produced no output)\n"
        code = process.returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        output, code = "Probe could not complete: " + str(exc) + "\n", -1
    log.write_text(output, encoding="utf-8", errors="replace")
    return {
        "status": "pass" if code == 0 else "fail", "exit_code": code,
        "command": command, "log": log.name,
        "sha256": sha256(log.read_bytes()).hexdigest(),
    }


def produce(args):
    destination = args.report.parent
    destination.mkdir(parents=True, exist_ok=True)
    probes = {name: _probe(name, destination) for name in SUITES}
    runner = os.environ.get("RUNNER_OS", "local")
    report = create_report(probes, revision=source_revision(), runner=runner)
    write_json(args.report, report)
    verify_report(report, destination)
    print(json.dumps({
        "report": str(args.report), "decision": report["decision"],
        "modes": {key: val["status"] for key, val in report["modes"].items()},
        "failed_probes": [key for key, val in probes.items()
                          if val["status"] == "fail"],
        "release_ready": report["release_ready"],
    }, indent=2))
    if any(value["status"] == "fail" for value in probes.values()):
        return 1
    if args.require_release:
        return 2
    return 0


def aggregate(args):
    files = sorted(args.aggregate.glob("**/r29-report.json"))
    sources, parse_errors = [], []
    for path in files:
        try:
            sources.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, UnicodeError) as exc:
            parse_errors.append(str(path) + ": " + str(exc))
    expected = os.environ.get("GITHUB_SHA")
    matrix = aggregate_matrix(sources, expected_revision=expected)
    if parse_errors:
        matrix["errors"].extend(parse_errors)
        matrix["matrix_verified"] = False
    write_json(args.report, matrix)
    print(json.dumps(matrix, indent=2, ensure_ascii=False))
    if not matrix["matrix_verified"]:
        return 1
    if args.require_release:
        return 2
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path,
                        help="Root with downloaded per-OS r29-report.json and logs")
    parser.add_argument("--require-release", action="store_true",
                        help="Require complete R29 P0, human and hardware approval (currently NO-GO)")
    args = parser.parse_args(argv)
    return aggregate(args) if args.aggregate is not None else produce(args)


if __name__ == "__main__":
    raise SystemExit(main())

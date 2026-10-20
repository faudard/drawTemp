#!/usr/bin/env python3
"""R31.I local/CI evidence gate; never reports PASS for skipped tests.

Usage:
  python scripts/r31i_certify.py --suite headless --output r31i-headless.json
  QT_QPA_PLATFORM=offscreen python scripts/r31i_certify.py --suite qt --output r31i-qt.json

The attestation is generated only from a TestResult observed by this process.
It deliberately does not infer success from GitHub's workflow status.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from io import StringIO

ROOT = Path(__file__).resolve().parents[1]

HEADLESS = (
    "tests_standalone.test_drawtemp_r31_logic_graph",
    "tests_standalone.test_drawtemp_r31_logic_branches",
    "tests_standalone.test_drawtemp_r31_logic_qt.LogicDraftTests",
    "tests_standalone.test_drawtemp_r31_logic_debugger",
    "tests_standalone.test_drawtemp_r31_logic_sequence",
    "tests_standalone.test_drawtemp_r31_logic_variables",
    "tests_standalone.test_drawtemp_r31_logic_campaign",
    "tests_standalone.test_drawtemp_r31_logic_vertical_slice",
    "tests_standalone.test_drawtemp5_r9",
    "tests_standalone.test_drawtemp5_r1_authoring",
)
QT = ("tests_standalone.test_drawtemp_r31_logic_qt.VisualLogicQtTests",)


def _sha():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=ROOT, check=True, text=True, capture_output=True,
            timeout=5)
        value = result.stdout.strip()
        if len(value) == 40 and all(x in "0123456789abcdef" for x in value):
            return value
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        pass
    return None


def verdict(*, tested, failures, errors, skipped, successful):
    """Fail-closed, including unavailable Qt, missing tests or all skipped."""
    return ("pass" if tested > 0 and failures == errors == skipped == 0
            and successful else "fail")


def certify(suite, *, minimum=1):
    if suite not in ("headless", "qt"):
        raise ValueError("Unknown R31.I certification suite")
    if suite == "qt":
        # Set before importing QGuiApplication from the Qt test module.
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    modules = HEADLESS if suite == "headless" else QT
    loader = unittest.defaultTestLoader
    selected = loader.loadTestsFromNames(modules)
    stream = StringIO()
    run = unittest.TextTestRunner(stream=stream, verbosity=2).run(selected)
    status = verdict(tested=run.testsRun, failures=len(run.failures),
                     errors=len(run.errors), skipped=len(run.skipped),
                     successful=run.wasSuccessful())
    if run.testsRun < minimum:
        status = "fail"
    return {
        "schema_version": 1,
        "kind": "r31i-certification",
        "suite": suite,
        "status": status,
        "executed_utc": datetime.now(timezone.utc).isoformat(),
        "commit_sha": _sha(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "tests": {
            "run": run.testsRun,
            "failures": len(run.failures),
            "errors": len(run.errors),
            "skipped": len(run.skipped),
            "minimum": minimum,
        },
        "test_names": list(modules),
        "failure_details": [
            {"test": str(test), "traceback": trace[-12000:]}
            for test, trace in [*run.failures, *run.errors]
        ][:24],
        "skipped_details": [
            {"test": str(test), "reason": reason}
            for test, reason in run.skipped
        ][:24],
        "log": stream.getvalue()[-30000:],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="R31.I real test evidence")
    parser.add_argument("--suite", choices=("headless", "qt"), required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--min-tests", type=int, default=1)
    args = parser.parse_args(argv)
    if args.min_tests < 1:
        parser.error("--min-tests must be positive")
    report = certify(args.suite, minimum=args.min_tests)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(json.dumps({
        "suite": report["suite"], "status": report["status"],
        "commit_sha": report["commit_sha"], "tests": report["tests"],
        "output": str(args.output) if args.output else None,
    }, ensure_ascii=False))
    if report["status"] != "pass":
        sys.stderr.write(report["log"] + "\n")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

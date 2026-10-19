"""R23.B CLI: run measured headless endurance; aggregate same-SHA OS evidence.

Not a release certificate. Human playtest files are supplied explicitly by the
reviewer and never manufactured in CI.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from drawtemp.quality.r23b import (
    aggregate_ci, capture_ci_evidence, write_json,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    run = commands.add_parser("run", help="Run persistence and preference probes")
    run.add_argument("--revision", required=True)
    run.add_argument("--platform", required=True,
                     choices=("Linux", "Windows", "macOS"))
    run.add_argument("--iterations", type=int, default=1)
    run.add_argument("--commands", type=int, default=8)
    run.add_argument("--output", required=True, type=Path)

    combined = commands.add_parser("aggregate", help="Assess 3-OS evidence (NO-GO)")
    combined.add_argument("--revision", required=True)
    combined.add_argument("--directory", required=True, type=Path)
    combined.add_argument("--output", required=True, type=Path)
    combined.add_argument("--human-report", type=Path, action="append", default=[],
                          help="Explicit opt-in tester JSON, never synthesized")
    args = parser.parse_args(argv)
    try:
        if args.action == "run":
            report = capture_ci_evidence(
                revision=args.revision, platform=args.platform,
                iterations=args.iterations, commands=args.commands)
        else:
            sources = sorted(args.directory.rglob("r23b-ci.json"))
            if len(sources) != 3:
                raise ValueError("Expected exactly three R23.B platform evidence files")
            reports = [json.loads(path.read_text(encoding="utf-8"))
                       for path in sources]
            human = [json.loads(path.read_text(encoding="utf-8"))
                     for path in args.human_report]
            report = aggregate_ci(reports, revision=args.revision,
                                  human_reports=human)
        write_json(args.output, report)
        print(json.dumps({
            "kind": report["kind"], "revision": report["revision"],
            "decision": report.get("decision", "headless-probe-only"),
        }, sort_keys=True))
        return 0
    except (ValueError, OSError, UnicodeError, KeyError, TypeError) as exc:
        print("R23.B blocked: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""R23.F fail-closed Release Candidate JSON artifact aggregator."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from drawtemp.quality.r23f import candidate_assessment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--journey-directory", type=Path, required=True)
    parser.add_argument("--r23e", type=Path, required=True)
    parser.add_argument("--r23b", type=Path,
                        help="Optional independent same-commit R23.B evidence")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = sorted(args.journey_directory.rglob("r23f-journey.json"))
        if len(paths) != 3:
            raise ValueError("Expected three R23.F real-API acceptance journeys")
        def read(path):
            return json.loads(path.read_text(encoding="utf-8"))
        report = candidate_assessment(
            revision=args.revision,
            journeys=[read(path) for path in paths],
            r23e=read(args.r23e),
            r23b=read(args.r23b) if args.r23b else None)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, sort_keys=True, indent=2,
                                         ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"candidate": report["candidate"],
                          "decision": report["decision"],
                          "tag_allowed": report["tag_allowed"],
                          "revision": report["revision"]}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        print("R23.F candidate blocked: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

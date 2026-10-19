"""R23.D aggregate real clean-host installer reports, not a signing certificate."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from drawtemp.quality.r23d_release import native_assessment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--r23c", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = sorted(args.directory.rglob("r23d-clean.json"))
        if len(paths) != 3:
            raise ValueError("Expected exactly three independent OS install reports")
        def read(path):
            return json.loads(path.read_text(encoding="utf-8"))
        assessment = native_assessment(
            [read(path) for path in paths], revision=args.revision,
            r23c=read(args.r23c) if args.r23c else None)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(assessment, sort_keys=True, indent=2)
                               + "\n", encoding="utf-8")
        print(json.dumps({"decision": assessment["decision"],
                          "revision": assessment["revision"],
                          "release_certified": assessment["release_certified"]},
                         sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print("R23.D clean-machine evidence blocked: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

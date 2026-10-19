"""R23.C release gate aggregator: verify three independent OS probes and upstream ledgers."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from drawtemp.quality.r23c_release import aggregate_release


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--r23a", type=Path)
    parser.add_argument("--r23b", type=Path)
    args = parser.parse_args(argv)
    try:
        reports = sorted(args.directory.rglob("r23c-clean.json"))
        if len(reports) != 3:
            raise ValueError("Expected exactly three r23c-clean.json reports")
        read = lambda p: json.loads(p.read_text(encoding="utf-8"))
        data = aggregate_release([read(p) for p in reports],
                                 revision=args.revision,
                                 r23a=read(args.r23a) if args.r23a else None,
                                 r23b=read(args.r23b) if args.r23b else None)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False,
                                          sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"decision": data["decision"],
                          "certified": data["certified"],
                          "revision": data["revision"]}))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("R23.C release assessment blocked: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

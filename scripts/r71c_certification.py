"""R71.C: two-player private laboratory and explicit NO-GO release report.

No public multiplayer implementation or operational security certification.
"""
import argparse
import json

from sporebound.connected_certification_r71 import certification_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=71)
    parser.add_argument("--require-go", action="store_true",
                        help="Return failure unless all release gates are GO")
    args = parser.parse_args(argv)
    report = certification_report(seed=args.seed)
    print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    return 2 if args.require_go and report["decision"] != "GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())

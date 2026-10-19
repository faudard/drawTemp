"""CLI for R24.D software witness; never claims native/GPU certification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from drawtemp.quality.r24_platform import PlatformGateError, second_game_software_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="R24 second independent game software gate")
    parser.add_argument("--content", type=Path, help="Override the Content JSON path")
    parser.add_argument("--report", type=Path, help="Write the JSON witness to a new path")
    parser.add_argument("--require-release", action="store_true",
                        help="Fail unless every release gate is certified")
    args = parser.parse_args(argv)
    try:
        report = second_game_software_report(content_path=args.content)
        if args.report:
            if args.report.exists() or args.report.is_symlink():
                parser.error("Report destination already exists")
            args.report.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.require_release and not report["release_certified"]:
            print("R24 release gate remains OPEN: hardware/legal/native proof missing",
                  file=sys.stderr)
            return 2
        return 0
    except (PlatformGateError, OSError) as exc:
        print("R24 software gate failed: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

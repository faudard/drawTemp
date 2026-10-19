"""Inspect and build inert R30 creator packs; no archive extraction or code loading."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from drawtemp.export.creator_packs import build_pack, inspect_pack


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Verify and describe an existing pack")
    inspect.add_argument("archive", type=Path)
    build = commands.add_parser("build", help="Build from a checked resource manifest")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--manifest", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        document = json.loads(args.manifest.read_text(encoding="utf-8"))
        build_pack(args.source, args.output, document)
        report = inspect_pack(args.output)
    else:
        report = inspect_pack(args.archive)
    print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""R24.G Git-friendly, read-only semantic diff / three-way merge preview CLI.

This never runs git, writes authored source files, resolves conflicts
automatically, or changes save slots. Output reports are create-only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .r24g_semantic_vcs import (
    SemanticMergeError, preview_three_way, read_pair, semantic_diff,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("diff", "merge"), default="merge")
    parser.add_argument("--base", type=Path, required=True,
                        help="Base Content JSON (sibling .game.json required)")
    parser.add_argument("--ours", type=Path, required=True,
                        help="Current Content JSON")
    parser.add_argument("--theirs", type=Path,
                        help="Other branch Content JSON, required for merge")
    parser.add_argument("--report", type=Path,
                        help="Create-only semantic review JSON; never writes game data")
    args = parser.parse_args(argv)
    if args.mode == "merge" and args.theirs is None:
        parser.error("--theirs is required for --mode merge")
    if args.mode == "diff" and args.theirs is not None:
        parser.error("--theirs is not used with --mode diff")
    source_paths = [x for x in (args.base, args.ours, args.theirs) if x is not None]
    protected = {path.resolve() for path in source_paths}
    protected.update(path.with_suffix(".game.json").resolve() for path in source_paths)
    if args.report:
        if args.report.resolve() in protected or args.report.exists() or args.report.is_symlink():
            parser.error("Report cannot overwrite a Content, GameProject or existing file")
    try:
        base, ours = read_pair(args.base), read_pair(args.ours)
        if args.mode == "diff":
            report = semantic_diff(base, ours)
            conflicts = 0
        else:
            theirs = read_pair(args.theirs)
            report = preview_three_way(base, ours, theirs)
            # Never export raw merged content: reports contain only hashes,
            # semantic paths and conflict summaries.
            report.pop("merged", None)
            conflicts = len(report["conflicts"])
        if args.report:
            with args.report.open("x", encoding="utf-8") as target:
                json.dump(report, target, sort_keys=True, ensure_ascii=False, indent=2)
                target.write("\n")
        print(json.dumps({
            "mode": args.mode, "report": str(args.report) if args.report else None,
            "local_changes": (report["count"] if args.mode == "diff"
                              else len(report["local_diff"])),
            "remote_changes": (None if args.mode == "diff"
                               else len(report["remote_diff"])),
            "conflicts": conflicts,
            "can_merge": (None if args.mode == "diff" else report["can_merge"]),
        }, sort_keys=True))
        return 2 if conflicts else 0
    except (SemanticMergeError, ValueError, OSError, UnicodeError, KeyError) as exc:
        print("R24.G: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

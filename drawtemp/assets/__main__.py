"""CLI for importing directional/ambient atlases into an existing GameProject."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content

from .atlas import DirectionalLayout, plan_directional_import, plan_strip_import
from .project import import_into_project, validate_project_assets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("import-sheet", "import-strip", "validate", "browse"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--project", type=Path, required=True)
        cmd.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
        if name.startswith("import"):
            cmd.add_argument("--source", type=Path, required=True)
            cmd.add_argument("--id", required=True)
            cmd.add_argument("--frame-size", nargs=2, type=int, required=True,
                             metavar=("WIDTH", "HEIGHT"))
            cmd.add_argument("--pivot", nargs=2, type=int, default=(0, 0))
            cmd.add_argument("--license", default="UNVERIFIED")
        if name == "import-sheet":
            cmd.add_argument("--rows", required=True,
                             help='JSON map e.g. {"idle":[0,1],"move":[2,3]}')
            cmd.add_argument("--directions", nargs="+",
                             default=("south", "east", "north", "west"))
            cmd.add_argument("--footprint", nargs=2, type=int, default=(1, 1))
            cmd.add_argument("--frame-ms", type=int, default=120)
        if name == "import-strip":
            cmd.add_argument("--frames", type=int, required=True)
            cmd.add_argument("--frame-ms", type=int, default=125)
    args = parser.parse_args(argv)
    if args.command == "browse":
        from .qt_browser import main as open_browser
        return open_browser(["--project", str(args.project), "--content", str(args.content)])
    content = Content.load(args.content)
    if args.command == "validate":
        issues = validate_project_assets(args.project, content)
        print(json.dumps({"valid": not issues, "assets": issues}, indent=2))
        return 1 if issues else 0
    project = GameProject.load(args.project, content)
    registry = project.asset_registry()
    if args.command == "import-sheet":
        try:
            rows = json.loads(args.rows)
        except json.JSONDecodeError as exc:
            parser.error("Invalid --rows JSON: " + str(exc))
        plan = plan_directional_import(
            registry, args.source, args.id,
            DirectionalLayout(
                tuple(args.frame_size), rows, tuple(args.directions),
                tuple(args.pivot), tuple(args.footprint), args.frame_ms),
            license_id=args.license)
    else:
        plan = plan_strip_import(
            registry, args.source, args.id,
            frame_size=tuple(args.frame_size), count=args.frames,
            pivot=tuple(args.pivot), frame_ms=args.frame_ms,
            license_id=args.license)
    import_into_project(args.project, content, plan)
    print(json.dumps({
        "imported": args.id, "path": plan.relative_path,
        "sprites": len(plan.annotations), "manifest_version": 1,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

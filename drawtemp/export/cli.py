"""Command-line Creator export, preflight and integrity checks (R15)."""
import argparse
import json
from pathlib import Path
import sys

from .r15 import ExportError, export_game, preflight, verify_bundle
from .templates import create_template, TEMPLATES
from .migration import migration_preview, import_project
from .extensions import inspect_extension


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp 5.0 Creator Export")
    cmd = parser.add_subparsers(dest="command", required=True)
    check = cmd.add_parser("check", help="Pre-export project and asset validation")
    check.add_argument("--content", required=True, type=Path)
    check.add_argument("--require-licenses", action="store_true")
    export = cmd.add_parser("export", help="Bundle a prebuilt native Player and a project")
    export.add_argument("--content", required=True, type=Path)
    export.add_argument("--runtime-dir", required=True, type=Path)
    export.add_argument("--output", required=True, type=Path)
    export.add_argument("--require-licenses", action="store_true")
    export.add_argument("--r14-report", type=Path)
    verify = cmd.add_parser("verify", help="Verify a standalone Player bundle")
    verify.add_argument("--bundle", type=Path, required=True)
    create = cmd.add_parser("template", help="Create a validated Creator project")
    create.add_argument("--kind", choices=TEMPLATES, required=True)
    create.add_argument("--output", type=Path, required=True)
    migrate = cmd.add_parser("import", help="Safely import v1 documents with backups")
    migrate.add_argument("--content", type=Path, required=True)
    migrate.add_argument("--output", type=Path)
    plugin = cmd.add_parser("inspect-extension", help="Validate declarative extension API")
    plugin.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "template":
            print(create_template(args.kind, args.output))
            return 0
        if args.command == "import":
            result = migration_preview(args.content)
            if args.output is not None and result["supported"]:
                result["created"] = str(import_project(args.content, args.output))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["supported"] else 1
        if args.command == "inspect-extension":
            print(json.dumps(inspect_extension(args.manifest), ensure_ascii=False))
            return 0
        if args.command == "check":
            result = preflight(args.content, require_licenses=args.require_licenses)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["passed"] else 1
        if args.command == "export":
            result = export_game(args.content, args.runtime_dir, args.output,
                                 require_licenses=args.require_licenses,
                                 r14_report=args.r14_report)
            print(result)
            return 0
        manifest = verify_bundle(args.bundle)
        print(json.dumps({"verified": True, "files": len(manifest["files"])},
                         ensure_ascii=False))
        return 0
    except (OSError, ValueError, ExportError) as exc:
        print("R15: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

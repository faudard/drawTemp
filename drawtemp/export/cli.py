"""Command-line Creator export, preflight and integrity checks (R15)."""
import argparse
import json
from pathlib import Path
import sys

from .r15 import ExportError, export_game, preflight, verify_bundle
from .templates import create_template, TEMPLATES
from .migration import migration_preview, import_project
from .extensions import inspect_extension
from .publishing import GAME_FAMILIES, PC_TARGETS, publication_plan, build_provenance


def _publication_json(path):
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ExportError("Publication input exceeds 8 MiB")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ExportError("Duplicate publication JSON key: " + key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


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
    export.add_argument("--release", action="store_true",
                        help="Require strict rights + certified R14 evidence")
    export.add_argument("--r14-report", type=Path)
    verify = cmd.add_parser("verify", help="Verify a standalone Player bundle")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--require-release", action="store_true",
                        help="Reject preview bundles without release evidence")
    create = cmd.add_parser("template", help="Create a validated Creator project")
    create.add_argument("--kind", choices=TEMPLATES, required=True)
    create.add_argument("--output", type=Path, required=True)
    migrate = cmd.add_parser("import", help="Safely import v1 documents with backups")
    migrate.add_argument("--content", type=Path, required=True)
    migrate.add_argument("--output", type=Path)
    plugin = cmd.add_parser("inspect-extension", help="Validate declarative extension API")
    plugin.add_argument("--manifest", type=Path, required=True)
    publish = cmd.add_parser("publish-plan", help="R39 PC publication preflight (not certification)")
    publish.add_argument("--bundle", required=True, type=Path)
    publish.add_argument("--provenance", required=True, type=Path)
    publish.add_argument("--revision", required=True)
    publish.add_argument("--target", required=True, choices=PC_TARGETS)
    publish.add_argument("--family", required=True, choices=GAME_FAMILIES)
    provenance = cmd.add_parser("build-provenance", help="Generate a byte-bound R39 build declaration")
    provenance.add_argument("--bundle", required=True, type=Path)
    provenance.add_argument("--dependencies", required=True, type=Path)
    provenance.add_argument("--revision", required=True)
    provenance.add_argument("--target", required=True, choices=PC_TARGETS)
    args = parser.parse_args(argv)
    try:
        if args.command == "build-provenance":
            result = build_provenance(args.bundle, _publication_json(args.dependencies),
                                      revision=args.revision, target=args.target)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "publish-plan":
            provenance = _publication_json(args.provenance)
            result = publication_plan(args.bundle, provenance, revision=args.revision,
                                      target=args.target, family=args.family)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
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
                                 require_licenses=args.require_licenses or args.release,
                                 r14_report=args.r14_report,
                                 release=args.release)
            print(result)
            return 0
        manifest = verify_bundle(args.bundle, require_release=args.require_release)
        print(json.dumps({"verified": True, "files": len(manifest["files"])},
                         ensure_ascii=False))
        return 0
    except (OSError, ValueError, ExportError) as exc:
        print("R15: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

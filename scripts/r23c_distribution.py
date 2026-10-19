"""R23.C portable preview CLI. Distinguishes portable archives from signed installers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from drawtemp.export.r23c import (
    install_preview, package_preview, remove_preview, verify_portable,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack = commands.add_parser("package")
    pack.add_argument("--game", type=Path, required=True)
    pack.add_argument("--studio", type=Path, required=True)
    pack.add_argument("--output", type=Path, required=True)
    pack.add_argument("--revision", required=True)
    pack.add_argument("--platform", required=True, choices=("Linux", "Windows", "macOS"))
    install = commands.add_parser("install")
    install.add_argument("--archive", type=Path, required=True)
    install.add_argument("--destination", type=Path, required=True)
    install.add_argument("--sha256", required=True)
    install.add_argument("--revision")
    install.add_argument("--platform", choices=("Linux", "Windows", "macOS"))
    verify = commands.add_parser("verify")
    verify.add_argument("--destination", type=Path, required=True)
    verify.add_argument("--revision")
    verify.add_argument("--platform", choices=("Linux", "Windows", "macOS"))
    remove = commands.add_parser("remove")
    remove.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "package":
            result = package_preview(args.game, args.studio, args.output,
                                     revision=args.revision, platform=args.platform)
        elif args.command == "install":
            path = install_preview(args.archive, args.destination,
                                   expected_sha256=args.sha256,
                                   revision=args.revision, platform=args.platform)
            result = {"installed": str(path), "certification": "preview-NO-GO"}
        elif args.command == "verify":
            data = verify_portable(args.destination, revision=args.revision,
                                   platform=args.platform)
            result = {"verified": True, "files": len(data["files"]),
                      "revision": data["revision"], "certification": data["certification"]}
        else:
            removed = remove_preview(args.destination)
            result = {"uninstalled": str(removed)}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("R23.C preview blocked: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""R69 local Community Creator Hub CLI: no network and no implicit writes.

Use `drawtemp-community` to publish, search, withdraw or explicitly acquire
inert R30 packs. R30.B remains the sole project-copy asset importer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from drawtemp.sdk.community_hub import (
    HubError, acquire_pack, available_updates, publish_pack,
    search_catalog, withdraw_pack,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    publish = commands.add_parser("publish", help="Add a reviewed ZIP to a local catalogue")
    publish.add_argument("--catalog", type=Path, required=True)
    publish.add_argument("--pack", type=Path, required=True)
    publish.add_argument("--publisher", required=True)
    publish.add_argument("--declaration", required=True,
                         help="Author's explicit redistribution statement (not legal clearance)")
    publish.add_argument("--confirm", action="store_true")
    search = commands.add_parser("search", help="List and search an offline catalogue")
    search.add_argument("--catalog", type=Path, required=True)
    search.add_argument("--query", default="")
    search.add_argument("--include-withdrawn", action="store_true")
    update = commands.add_parser("updates", help="Check updates; never install them")
    update.add_argument("--catalog", type=Path, required=True)
    update.add_argument("--installed", type=Path, required=True,
                        help="Local JSON map of pack id to installed SemVer")
    acquire = commands.add_parser("acquire", help="Copy a selected release to a new ZIP")
    acquire.add_argument("--catalog", type=Path, required=True)
    acquire.add_argument("--id", required=True)
    acquire.add_argument("--version", required=True)
    acquire.add_argument("--output", type=Path, required=True)
    acquire.add_argument("--expected-sha256",
                         help="Optional digest pinned independently of the catalogue")
    acquire.add_argument("--confirm", action="store_true")
    withdraw = commands.add_parser("withdraw", help="Permanently tombstone a release")
    withdraw.add_argument("--catalog", type=Path, required=True)
    withdraw.add_argument("--id", required=True)
    withdraw.add_argument("--version", required=True)
    withdraw.add_argument("--reason", required=True)
    withdraw.add_argument("--confirm", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.action == "publish":
            result = publish_pack(args.catalog, args.pack,
                                  publisher=args.publisher,
                                  declaration=args.declaration,
                                  confirm=args.confirm)
        elif args.action == "search":
            result = search_catalog(args.catalog, args.query,
                                    include_withdrawn=args.include_withdrawn)
        elif args.action == "updates":
            with args.installed.open("rb") as stream:
                installed = json.loads(stream.read(65537).decode("utf-8"))
            result = available_updates(args.catalog, installed)
        elif args.action == "acquire":
            result = acquire_pack(args.catalog, args.id, args.version, args.output,
                                  expected_sha256=args.expected_sha256,
                                  confirm=args.confirm)
        else:
            result = withdraw_pack(args.catalog, args.id, args.version,
                                   reason=args.reason, confirm=args.confirm)
    except (HubError, OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "code": getattr(exc, "code", "invalid_input"),
                          "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False,
                     sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

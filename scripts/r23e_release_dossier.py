"""R23.E release ledger CLI: factual bundle rights inventory + NO-GO dossier."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from drawtemp.quality.r23e import (
    EvidenceError, asset_inventory, release_dossier,
)


def write_json(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                               indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    inv = actions.add_parser("inventory", help="Inventory R15 authored assets")
    inv.add_argument("--bundle", type=Path, required=True)
    inv.add_argument("--revision", required=True)
    inv.add_argument("--platform", choices=("Linux", "Windows", "macOS"), required=True)
    inv.add_argument("--report", type=Path, required=True)

    aggregate = actions.add_parser("dossier", help="Collect NO-GO release evidence")
    aggregate.add_argument("--r23d", type=Path, required=True)
    aggregate.add_argument("--asset-directory", type=Path, required=True)
    aggregate.add_argument("--revision", required=True)
    aggregate.add_argument("--external-submissions", type=Path,
                           help="Optional separate, unreviewed human reports index")
    aggregate.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "inventory":
            result = asset_inventory(args.bundle, revision=args.revision,
                                     platform=args.platform)
        else:
            files = sorted(args.asset_directory.rglob("r23e-assets.json"))
            if len(files) != 3:
                raise EvidenceError("Require three R23.E asset inventory reports")
            def read(path):
                return json.loads(path.read_text(encoding="utf-8"))
            upstream = read(args.r23d)
            external = (read(args.external_submissions)
                        if args.external_submissions else [])
            result = release_dossier(
                revision=args.revision, r23d=upstream,
                inventories=[read(path) for path in files], external=external)
        write_json(args.report, result)
        print(json.dumps({
            "kind": result["kind"], "revision": result["revision"],
            "decision": result.get("decision", "rights-inventory-only"),
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, UnicodeError, TypeError, KeyError) as exc:
        print("R23.E dossier blocked: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

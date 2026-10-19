"""R30.B Creator pack import, always to a new project directory.

The --confirm flag is deliberately mandatory. No live project is overwritten,
and no unverified resource is ever approved for distribution.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from drawtemp.export.pack_import import import_pack_to_copy, preview_pack_import


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", required=True, type=Path)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--bindings", required=True, type=Path,
                        help="Explicit list of {path,kind,name} selections in JSON")
    parser.add_argument("--output", type=Path, help="New directory, not an existing project")
    parser.add_argument("--confirm", action="store_true",
                        help="Apply the validated preview to a new project copy")
    args = parser.parse_args(argv)
    bindings = json.loads(args.bindings.read_text(encoding="utf-8"))
    preview = preview_pack_import(args.content, args.pack, bindings)
    if args.confirm:
        if args.output is None:
            parser.error("--confirm requires --output")
        output = import_pack_to_copy(preview, args.output)
        report = {**preview.to_dict(), "output": str(output), "applied": True}
    else:
        report = {**preview.to_dict(), "applied": False}
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

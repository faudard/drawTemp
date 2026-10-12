"""Authoring-only alpha-edge audit for Jeanne's watercolor sprites.

Requires Pillow: python -m pip install pillow
Example: python scripts/audit_watercolor_pack.py --bundle pack.zip --output audit.json
Edge occupancy is a review heuristic, not automatic proof of clipping.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from zipfile import ZipFile

PREFIX = "assets/watercolor/"


def analyse_alpha(image, cutoff=128):
    """Return opaque-border occupancy for each of the four canvas edges."""
    alpha = image.convert("RGBA").getchannel("A")
    width, height = alpha.size
    if min(width, height) < 2:
        raise ValueError("Frame must be at least 2x2")
    rectangles = {
        "top": (0, 0, width, 1),
        "right": (width - 1, 0, width, height),
        "bottom": (0, height - 1, width, height),
        "left": (0, 0, 1, height),
    }
    result = {}
    for side, rect in rectangles.items():
        line = alpha.crop(rect)
        histogram = line.histogram()
        ratio = sum(histogram[cutoff:]) / (width if side in ("top", "bottom") else height)
        result[side] = round(ratio, 4)
    return result


def audit(bundle, threshold=0.12):
    """Inspect every sprite from the indexed, portable ZIP without extracting."""
    from PIL import Image

    if not 0 < threshold <= 1:
        raise ValueError("threshold must be in (0, 1]")
    results = []
    with ZipFile(bundle) as archive:
        index = json.loads(archive.read(PREFIX + "index.json"))
        for sprite in index["sprites"]:
            entry = PREFIX + sprite["path"]
            with Image.open(io.BytesIO(archive.read(entry))) as original:
                original.load()
                borders = analyse_alpha(original)
                maximum = max(borders.values())
                results.append({
                    "id": sprite["id"],
                    "size": list(original.size),
                    "border_opaque_fraction": borders,
                    "max_border_opaque_fraction": round(maximum, 4),
                    "manual_review": maximum > threshold,
                })
    return {
        "schema_version": 1,
        "threshold": threshold,
        "sprite_count": len(results),
        "manual_review_count": sum(x["manual_review"] for x in results),
        "method": "opaque pixel occupancy on the outermost pixel of each edge (alpha >= 128)",
        "note": "Border contact is a conservative review flag, not proof of clipping; lighting effects and wide props may be intentional.",
        "sprites": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--threshold", type=float, default=0.12)
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 if any sprites require review")
    args = parser.parse_args(argv)
    report = audit(args.bundle, args.threshold)
    print(f"Checked {report['sprite_count']} sprites; {report['manual_review_count']} border review flags")
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.strict and report["manual_review_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

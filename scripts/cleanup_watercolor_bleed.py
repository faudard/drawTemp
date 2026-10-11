"""Remove detached neighbouring-cell artifacts from watercolor PNGs (authoring only).

Requirements: Pillow, numpy, opencv-python-headless (not required by Player).
Usage:
  python scripts/cleanup_watercolor_bleed.py --input pack_v2.zip --output pack_v3.zip

Only removes sufficiently large disconnected alpha components along cell edges.
Does not reconstruct art already clipped by the original 4x3/3x2 source grid.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import zipfile

PREFIX = "assets/watercolor/"
EXEMPT_GROUPS = {"vfx", "bestiary"}  # Detached visual particles may be intentional.
REPORT_PATH = PREFIX + "bleed_cleanup_report.json"


def border_fragments(stats, main, size, *, min_area=100, margin=12):
    """Find isolated near-border components. Pure function, no image dependencies.

    stats is the OpenCV [x, y, width, height, area] collection, with
    index 0 reserved for background.
    """
    width, height = size
    remove = []
    for index in range(1, len(stats)):
        if index == main:
            continue
        x, y, w, h, area = (int(v) for v in stats[index])
        if area >= min_area and (x <= margin or y <= margin or
                                x + w >= width - margin or
                                y + h >= height - margin):
            remove.append(index)
    return remove


def cleanup_frame(frame, *, min_area=100, margin=12):
    """Keep the dominant silhouette while removing detached near-edge bleed."""
    import cv2
    import numpy as np
    from PIL import Image

    rgba = np.array(frame.convert("RGBA"), copy=True)
    height, width = rgba.shape[:2]
    if min(width, height) < 16:
        return frame.copy(), 0
    mask = (rgba[:, :, 3] > 70).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if n < 3:
        return frame.copy(), 0
    main = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    rejects = border_fragments(stats, main, (width, height),
                               min_area=min_area, margin=margin)
    if not rejects:
        return frame.copy(), 0

    # Protect 1px antialiasing adjacent to the dominant silhouette.
    major_halo = cv2.dilate((labels == main).astype(np.uint8),
                            np.ones((3, 3), np.uint8)) > 0
    unwanted = np.zeros((height, width), np.uint8)
    for index in rejects:
        component = (labels == index).astype(np.uint8)
        unwanted |= cv2.dilate(component, np.ones((7, 7), np.uint8))
    rgba[(unwanted > 0) & (~major_halo), 3] = 0
    return Image.fromarray(rgba, "RGBA"), len(rejects)


def clean_archive(source, destination, *, min_area=100):
    """Write a new ZIP with unchanged index/registry and a QA provenance report."""
    from PIL import Image

    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output archives must differ")
    if destination.exists():
        raise FileExistsError(f"Output exists: {destination}")
    cleaned = []
    try:
        with zipfile.ZipFile(source) as zin:
            index = json.loads(zin.read(PREFIX + "index.json"))
            sprites = {PREFIX + item["path"]: item for item in index["sprites"]}
            if len(sprites) != 88:
                raise ValueError("Expected 88 uniquely indexed sprite paths")
            names = zin.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate ZIP member")
            if REPORT_PATH in names:
                raise ValueError("Archive already has a cleanup report")
            if not set(sprites).issubset(names):
                raise ValueError("Missing indexed PNG in archive")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(destination, "w") as zout:
                for name in names:
                    content = zin.read(name)
                    sprite = sprites.get(name)
                    if sprite and sprite["sheet"] not in EXEMPT_GROUPS:
                        with Image.open(io.BytesIO(content)) as src:
                            result, count = cleanup_frame(src, min_area=min_area)
                        if count:
                            output = io.BytesIO()
                            result.save(output, format="PNG", compress_level=6)
                            content = output.getvalue()
                            cleaned.append({"sprite": sprite["id"], "removed_components": count})
                    zout.writestr(name, content, compress_type=zipfile.ZIP_DEFLATED)
                report = {"version": 1, "source": source.name,
                          "cleaned_sprite_count": len(cleaned),
                          "removed_component_count": sum(x["removed_components"] for x in cleaned),
                          "modified_sprites": cleaned,
                          "note": "Heuristic alpha cleanup. Clipped weapons and poses need manual art fixes."}
                zout.writestr(REPORT_PATH, json.dumps(report, indent=2) + "\n")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = clean_archive(args.input, args.output)
    print(f"{report['cleaned_sprite_count']} sprites cleaned; "
          f"{report['removed_component_count']} fragments removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

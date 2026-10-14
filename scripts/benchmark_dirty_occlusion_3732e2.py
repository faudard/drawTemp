#!/usr/bin/env python3
"""Measure canonical full vs local terrain refresh alongside an authored house.

Both branches repaint identical validated scene changes with Tk idle flushing.
Performance evidence is descriptive, not a universal p95/p99 performance gate.
"""
import argparse
import json
import platform
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.profile_scale_3732 import percentiles
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.editor_refresh_scale import EditorContentProjection
from sporebound.iso_structures import place_structure
from sporebound.model import Content


def measure(size, zoom, samples):
    import tkinter as tk

    mid = "occlusion_perf"
    raw = add_blank_mission(
        Content.load(DEFAULT_CONTENT).to_dict(), mid,
        "Occlusion Performance", size, size)
    raw = place_structure(raw, mid, "Maison", (15, 15), 0)
    result = {"map_size": size, "tile_px": zoom, "samples": samples}
    for mode in ("full", "occlusion_dirty"):
        doc = Document(Content.from_dict(raw))
        # Tall non-building props remain in the same depth order throughout.
        doc.paint_many(mid, [(17, 16)], "feature:tree")
        projection = EditorContentProjection()
        root = tk.Tk()
        try:
            root.geometry("920x680")
            canvas = tk.Canvas(root)
            canvas.pack(expand=True, fill="both")
            root.update()
            renderer = EditorRenderCache(canvas)
            options = dict(cell_size=zoom, layers={}, selected_cell=(16, 16),
                           selected_tiles=())
            old = projection.get(doc.data).missions[mid]
            renderer.draw(old.board, old, old.units,
                          scene_revision=(projection.generation, mid), **options)
            durations, paths, affected = [], [], []
            for i in range(samples):
                doc.paint_many(mid, [(14, 15)],
                               "surface:water" if i % 2 == 0
                               else "surface:grass")
                if mode == "full":
                    renderer.invalidate()
                start = perf_counter()
                mission = projection.get(doc.data).missions[mid]
                renderer.draw(mission.board, mission, mission.units,
                              scene_revision=(projection.generation, mid),
                              **options)
                root.update_idletasks()
                durations.append((perf_counter() - start) * 1000)
                paths.append(renderer.stats.get("fast_path"))
                affected.append(renderer.stats.get("affected_cells", 0))
            if mode == "occlusion_dirty":
                assert set(paths) == {"dirty_tiles"}, paths
                assert max(affected) <= 9, affected
                assert renderer.stats.get("architecture_instances", 0) > 0
            result[mode] = {
                **percentiles(durations),
                "fast_paths": {label: paths.count(label) for label in set(paths)},
                "max_affected_tiles": max(affected),
                "canvas_items": len(canvas.find_all()),
            }
        finally:
            root.destroy()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="65,128")
    parser.add_argument("--zooms", default="24,54,96")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.quick:
        args.sizes, args.zooms, args.samples = "65,128", "54", 3
    sizes = [int(x) for x in args.sizes.split(",")]
    zooms = [int(x) for x in args.zooms.split(",")]
    if not sizes or not zooms or any(n not in (65, 128) for n in sizes) or \
            any(n not in (24, 54, 96) for n in zooms) or \
            not 2 <= args.samples <= 1000:
        parser.error("sizes 65/128, zooms 24/54/96, samples 2..1000")
    report = {
        "schema": "drawtemp-dirty-occlusion-3732e2-v1",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "disclaimer": "Tk idle timing, not input-to-photon; p95/p99 based on "
                      "fewer than 100 samples are exploratory.",
        "cases": [measure(size, zoom, args.samples) for size in sizes
                  for zoom in zooms],
    }
    raw = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
        print("Saved:", args.output)
    else:
        print(raw, end="")
    for row in report["cases"]:
        print("%d² %dpx: full p95 %.3fms, occlusion dirty p95 %.3fms" % (
            row["map_size"], row["tile_px"],
            row["full"]["p95_ms"], row["occlusion_dirty"]["p95_ms"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

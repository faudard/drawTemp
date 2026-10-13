#!/usr/bin/env python3
"""3.7.32D: same-process large-map Studio model+ISO refresh comparison.

This profiles two real Editor paths, not synthetic array loops:
  baseline: Content.from_dict + EditorRenderCache (conservative snapshots)
  candidate: EditorContentProjection + validated scene_revision cache
and Tk idle paint. No machine-wide budgets or asserted time improvements.
"""
import argparse
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor_refresh_scale import EditorContentProjection
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.model import Content
from scripts.profile_scale_3732 import percentiles, resident_set


def measure_case(size, cell_size, samples):
    import tkinter as tk

    raw = add_blank_mission(
        Content.load(DEFAULT_CONTENT).to_dict(), "scale_map",
        "Performance %d" % size, size, size)
    rows = {}
    for mode in ("legacy_parse_snapshot", "validated_revision"):
        root = tk.Tk()
        try:
            root.geometry("900x650")
            canvas = tk.Canvas(root)
            canvas.pack(fill="both", expand=True)
            root.update()
            renderer = EditorRenderCache(canvas)
            projection = EditorContentProjection()
            values = []
            operations = []
            for i in range(samples + 1):
                started = perf_counter()
                if mode == "validated_revision":
                    model = projection.get(raw)
                else:
                    model = Content.from_dict(raw)
                mission = model.missions["scale_map"]
                revision = ((projection.generation, mission.id)
                            if mode == "validated_revision" else None)
                renderer.draw(
                    mission.board, mission, mission.units,
                    cell_size=cell_size, layers={},
                    selected_cell=(i % size, 0), selected_tiles=(),
                    scene_revision=revision)
                root.update_idletasks()
                elapsed = (perf_counter() - started) * 1000
                if i:
                    values.append(elapsed)
                    operations.append(renderer.stats.get("fast_path", "retained"))
            rss, rss_kind = resident_set()
            rows[mode] = {
                **percentiles(values),
                "samples": len(values),
                "canvas_items": len(canvas.find_all()),
                "rss_bytes": rss,
                "rss_kind": rss_kind,
                "render_modes": {name: operations.count(name)
                                 for name in set(operations)},
                "projection_rebuilds": projection.rebuilds,
            }
        finally:
            root.destroy()
    return {"size": size, "cell_size": cell_size, "modes": rows}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sizes", default="32,64,128")
    p.add_argument("--cells", default="24,54,96")
    p.add_argument("--samples", type=int, default=100)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    if args.quick:
        args.sizes, args.cells, args.samples = "32,64,128", "54", 3
    sizes = [int(n) for n in args.sizes.split(",")]
    cells = [int(n) for n in args.cells.split(",")]
    if (not sizes or not cells
            or any(n not in (32, 64, 128) for n in sizes)
            or any(n not in (24, 54, 96) for n in cells)
            or not 2 <= args.samples <= 1000):
        p.error("Sizes must be 32/64/128, cells 24/54/96, samples 2..1000")
    result = {
        "schema": "drawtemp-studio-refresh-3732d-v1",
        "python": platform.python_version(), "platform": platform.platform(),
        "sizes": sizes, "cells": cells, "samples": args.samples,
        "notes": "Paired real Content/ISO Renderer/Tk-idle paths; excludes "
                 "physical input-to-photon and Studio panel handling. "
                 "p99 smoke with fewer than 100 samples is exploratory.",
        "cases": [measure_case(size, cell, args.samples)
                  for size in sizes for cell in cells],
    }
    raw = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
        print("Saved:", args.output)
        for row in result["cases"]:
            print("%s² %spx: baseline p95=%.3fms, candidate p95=%.3fms" %
                  (row["size"], row["cell_size"],
                   row["modes"]["legacy_parse_snapshot"]["p95_ms"],
                   row["modes"]["validated_revision"]["p95_ms"]))
    else:
        print(raw, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

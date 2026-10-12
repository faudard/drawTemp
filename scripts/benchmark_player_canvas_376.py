#!/usr/bin/env python3
"""3.7.6: measure the actual Tk tactical CanvasRenderer, not a sprite-blit proxy.

Authentic Jeanne mission content is projected through Battle/battle_frame.
Extra actors in stress mode are synthetic presentation-only copies; tactical
state and authoritative RNG remain unchanged. Tests and reports always
distinguish the authored scene from stress projections.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

# Running this standalone script prepends scripts/ rather than the repo root
# to sys.path. Support checkout execution without a wheel installation.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sporebound.engine import Battle
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame
from sporebound.tk_renderer import CanvasRenderer
from sporebound.visual_motion import MotionDirector

CONTENT = Path(__file__).resolve().parents[1] / "sporebound" / "content"

def quantile(values, fraction):
    values = sorted(values)
    offset = (len(values) - 1) * fraction
    low, high = int(offset), min(len(values) - 1, int(offset) + 1)
    return values[low] + (values[high] - values[low]) * (offset - low)



def build_scene(actors=None):
    """Use the authored battle; optionally scale density for renderer stress."""
    content = Content.load(CONTENT / "jeanne.json")
    project = GameProject.load(CONTENT / "jeanne.game.json", content)
    registry = project.asset_registry()
    battle = Battle(content, "p0_01_lame", seed=17)
    initial_digest = battle.digest()
    frame = battle_frame(battle, (2, 2), None)
    if actors is not None:
        if actors < len(frame.actors):
            raise ValueError("Stress population cannot drop authored actors")
        if not frame.actors:
            raise ValueError("Authored mission lacks combat actors")
        units = list(frame.actors)
        for i in range(actors - len(units)):
            prototype = frame.actors[i % len(frame.actors)]
            units.append(replace(
                prototype, id=f"stress_{i:04d}", name=f"Simulant {i}",
                pos=((i * 7 + 3) % frame.width,
                     (i * 11 + 2) % frame.height), active=False))
        frame = replace(frame, actors=tuple(units))
    if battle.digest() != initial_digest:
        raise RuntimeError("Battle mutated during rendering projection")
    if registry.diagnostics(CONTENT):
        raise RuntimeError("Jeanne atlas is invalid")
    return frame, registry, battle, initial_digest


def measure(frame, registry, *, cell_size=52, frames=120, pan=False):
    import tkinter as tk

    root = tk.Tk()
    root.title("3.7.6 complete battle canvas performance")
    root.geometry("800x600")
    canvas = tk.Canvas(root, width=800, height=600, highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    renderer = CanvasRenderer(canvas, registry=registry, asset_root=CONTENT)
    camera = Camera(cell_size, -180 if pan else 8, -120 if pan else 8)
    motion = MotionDirector()
    motion.observe(frame, 0)
    try:
        root.update()  # Ensure real viewport sizing and Tk image decode.
        for n in range(10):
            elapsed = n * 60
            renderer.draw(frame, camera, poses=motion.poses(elapsed),
                          elapsed_ms=motion.elapsed_ms(elapsed),
                          clock_ms=elapsed)
            root.update()
        tracemalloc.start()
        samples = []
        item_count = 0
        for n in range(frames):
            elapsed = (n + 10) * 60
            begin = time.perf_counter()
            renderer.draw(frame, camera, poses=motion.poses(elapsed),
                          elapsed_ms=motion.elapsed_ms(elapsed),
                          clock_ms=elapsed)
            root.update()
            samples.append((time.perf_counter() - begin) * 1000)
            item_count = len(canvas.find_all())
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return {
            "p50_ms": round(quantile(samples, 0.5), 3),
            "p95_ms": round(quantile(samples, 0.95), 3),
            "max_ms": round(max(samples), 3),
            "mean_ms": round(statistics.mean(samples), 3),
            "peak_python_mb": round(peak / (1024 * 1024), 3),
            "canvas_items": item_count,
            "terrain_items": len(canvas.find_withtag("terrain")),
            "dynamic_items": len(canvas.find_withtag("dynamic")),
            "overlay_rebuilds": renderer._overlay_rebuilds,
            "terrain_rebuilds": renderer._terrain_rebuilds,
            "actor_creations": renderer._actor_creations,
            "actor_updates": renderer._actor_updates,
            "retained_actors": len(renderer._actor_items),
            "actor_items": len(canvas.find_withtag("actor")),
            "cached_sources": len(renderer._sources),
            "cached_sprite_sizes": len(renderer._cell_images),
            "canvas_pixels": [canvas.winfo_width(), canvas.winfo_height()],
        }
    finally:
        renderer.dispose()
        root.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actors", type=int, default=0,
                        help="0 = authored battle; 20/80/200 = stress projection")
    parser.add_argument("--cell", type=int, default=52,
                        help="Camera cell width in pixels (16..128)")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--pan", action="store_true",
                        help="Start with battle clipped by the viewport")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.actors not in (0, 20, 80, 200):
        parser.error("Actors must be 0 (authored), 20, 80 or 200")
    if not 16 <= args.cell <= 128 or args.frames < 20:
        parser.error("Cell size must be 16..128 and frames >= 20")
    frame, registry, battle, digest = build_scene(args.actors or None)
    try:
        metrics = measure(frame, registry, cell_size=args.cell,
                          frames=args.frames, pan=args.pan)
    except Exception:
        if battle.digest() != digest:
            raise RuntimeError("Rendering mutated battle on failure")
        raise
    if battle.digest() != digest:
        raise RuntimeError("Rendering mutated authoritative Battle state")
    result = {
        "benchmark": "jeanne-actual-canvas-v1",
        "scene": "authored" if not args.actors else "stress_projection",
        "mission": "p0_01_lame",
        "actors": len(frame.actors),
        "authored_actors": len(battle.units),
        "tiles": len(frame.tiles),
        "threat_cells": len(frame.danger),
        "reachable_cells": len(frame.reachable),
        "pan": args.pan,
        "cell_size": args.cell,
        "frames": args.frames,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "scope": "Tk CanvasRenderer.draw + MotionDirector.poses + Tk event pump",
        "exclusions": ("Does not time AI turns, sound, campaign UI, "
                       "hardware GPU presentation or file I/O"),
        "memory_scope": "Python tracemalloc only, excluding native Tk allocations",
        **metrics,
    }
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(output, end="")
    else:
        args.output.write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

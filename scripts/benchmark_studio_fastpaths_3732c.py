#!/usr/bin/env python3
"""Before/after profiling of real Studio fast paths on the SAME machine.

Baseline paths are original StudioIndex construction and full Canvas repaint;
optimized paths are WorkspaceModelCache and event-graph retained selection.
The smoke output validates parity, but cannot establish a universal speedup.
"""
import argparse
import json
import platform
from pathlib import Path
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.profile_scale_3732 import make_event_graph, make_workspace, percentiles
from sporebound.model import Content
from sporebound.studio_index4 import StudioIndex, WorkspaceModelCache
from sporebound.tactical_rpg3 import authored_rules_for_document


def timed(action, samples):
    action()
    times = []
    for _ in range(samples):
        t = perf_counter()
        action()
        times.append((perf_counter() - t) * 1000)
    return percentiles(times)


def workspace_case(resources, samples):
    content, project = make_workspace(resources)
    raw = content.to_dict()
    cache = WorkspaceModelCache()

    def original():
        index = StudioIndex(Content.from_dict(
            raw, rules=authored_rules_for_document(raw)), project)
        return index.search("performance")

    def optimized():
        return cache.get(raw, project).search("performance")

    assert original() == optimized()
    before = timed(original, samples)
    after = timed(optimized, samples)
    assert cache.builds == 1, "Cache rebuilt for unchanged document"
    return {
        "resources": resources, "samples": samples,
        "before": before, "after": after,
        "cache_builds": cache.builds,
        "parity": "exact Workspace search results",
    }


def graph_case(events, samples):
    import tkinter as tk
    from types import SimpleNamespace
    from sporebound.studio_event_graph import EventGraphStudio

    data, mission = make_event_graph(events)
    root = tk.Tk()
    try:
        root.geometry("900x650")
        canvas = tk.Canvas(root)
        canvas.pack(fill="both", expand=True)
        root.update()
        editor = EventGraphStudio.__new__(EventGraphStudio)
        editor.owner = SimpleNamespace(
            doc=lambda: SimpleNamespace(data=data), mission=lambda: mission)
        editor.canvas = canvas
        editor.zoom = tk.StringVar(root, value="100%")
        editor.event_id = tk.StringVar(root, value="")
        editor.action_index = None
        editor.last_preview = None
        editor.status = tk.StringVar(root)
        editor._rendered_graph = None
        editor._rendered_scale = None
        editor._node_items = {}
        editor._node_styles = {}
        editor._rendered_item_count = 0
        event_ids = ["scale_trigger_%03d" % n for n in range(events)]
        counter = 0

        def draw(force_rebuild):
            nonlocal counter
            editor.event_id.set(event_ids[counter % len(event_ids)])
            counter += 1
            if force_rebuild:
                editor._rendered_graph = None
            editor.draw()
            root.update_idletasks()

        def snapshot():
            rows = []
            for item in canvas.find_all():
                kind = canvas.type(item)
                rows.append((
                    kind, tuple(canvas.coords(item)), tuple(canvas.gettags(item)),
                    canvas.itemcget(item, "fill"),
                    canvas.itemcget(item, "outline") if kind == "rectangle" else "",
                    canvas.itemcget(item, "width") if kind != "text" else "",
                    canvas.itemcget(item, "text") if kind == "text" else "",
                ))
            return tuple(rows)

        before = timed(lambda: draw(True), samples)
        after = timed(lambda: draw(False), samples)
        editor.event_id.set(event_ids[0])
        editor.draw()
        retained = snapshot()
        editor._rendered_graph = None
        editor.draw()
        assert retained == snapshot(), "Full vs retained Canvas divergence"
        return {
            "events": events, "samples": samples,
            "canvas_items": len(canvas.find_all()),
            "before": before, "after": after,
            "parity": "same types, coordinates, painter order, tags and styles",
        }
    finally:
        root.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("all", "headless", "gui"), default="all")
    parser.add_argument("--resources", type=int, default=200)
    parser.add_argument("--events", type=int, default=160)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.quick:
        args.resources, args.events, args.samples = 24, 20, 5
    if not 2 <= args.resources <= 500 or not 2 <= args.events <= 200:
        parser.error("Resources 2..500; events 2..200")
    if not 2 <= args.samples <= 1000:
        parser.error("Samples 2..1000")
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            stderr=subprocess.DEVNULL, timeout=3, text=True).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        commit = None
    report = {
        "schema": "drawtemp-fastpaths-3732c-v1",
        "source_sha": commit, "platform": platform.platform(),
        "python": platform.python_version(),
        "scope": "Same-process comparable paths, no end-to-end mouse-to-photon",
        "parameters": vars(args) | {"output": str(args.output) if args.output else None},
        "sample_warning": args.samples < 100,
    }
    if args.phase in ("all", "headless"):
        report["workspace"] = workspace_case(args.resources, args.samples)
    if args.phase in ("all", "gui"):
        report["event_graph"] = graph_case(args.events, args.samples)
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
        print("Saved:", args.output)
    else:
        print(raw, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

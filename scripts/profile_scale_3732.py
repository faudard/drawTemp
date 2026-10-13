#!/usr/bin/env python3
"""Reproducible Performance & Scale matrix for the existing drawTemp Studio.

No synthetic renderer or alternative save format: GUI probes invoke the
canonical EditorRenderCache/CanvasRenderer benchmarks in isolated processes.
Headless probes use validated Content, GameProject, StudioIndex, event/story
graph projections and StudioTransactionStore. No universal latency gate.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTENT_DIR = ROOT / "sporebound" / "content"


def percentiles(values):
    """Linear-interpolated p50/p95/p99; never drop outliers."""
    if not values:
        raise ValueError("At least one measurement is required")
    ordered = sorted(values)

    def p(frac):
        position = (len(ordered) - 1) * frac
        lo = int(position)
        hi = min(len(ordered) - 1, lo + 1)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)

    return {
        "samples": len(ordered),
        "p50_ms": round(p(.50), 3),
        "p95_ms": round(p(.95), 3),
        "p99_ms": round(p(.99), 3),
        "mean_ms": round(statistics.mean(ordered), 3),
        "max_ms": round(ordered[-1], 3),
    }


def resident_set():
    """Whole-process resident memory, including native/Tcl: not native-only."""
    if sys.platform.startswith("linux"):
        try:
            pages = int(Path("/proc/self/statm").read_text().split()[1])
            return pages * os.sysconf("SC_PAGE_SIZE"), "current"
        except (OSError, IndexError, ValueError):
            return None, "unavailable"
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class MemoryCounters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD),
                            ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            info = MemoryCounters()
            info.cb = ctypes.sizeof(info)
            proc = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                proc, ctypes.byref(info), info.cb)
            return (info.WorkingSetSize, "current") if ok else (None, "unavailable")
        except (AttributeError, OSError):
            return None, "unavailable"
    if sys.platform == "darwin":
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "peak"
        except (ImportError, OSError):
            return None, "unavailable"
    return None, "unavailable"


def measure(name, action, samples):
    """Separate traced memory pass from timings to reduce measurement bias."""
    action()  # warm-up; omit from the latency distribution
    times = []
    for _ in range(samples):
        begin = perf_counter()
        action()
        times.append((perf_counter() - begin) * 1000)
    rss, rss_kind = resident_set()
    tracemalloc.start()
    try:
        action()
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {
        "operation": name, **percentiles(times),
        "python_traced_current_bytes": current,
        "python_traced_peak_bytes": peak,
        "rss_bytes": rss, "rss_kind": rss_kind,
        "memory_note": "RSS includes Python and native memory; tracemalloc excludes native allocations.",
    }


def make_workspace(resource_count):
    """Grow a real validated mission/project pair, not a parallel inventory."""
    from sporebound.authoring import add_blank_mission
    from sporebound.game_project import GameProject
    from sporebound.model import Content
    from sporebound.tactical_rpg3 import authored_rules_for_document

    core = Content.load(CONTENT_DIR / "core.json")
    source = add_blank_mission(core.to_dict(), "scale_000", "Performance 000", 8, 8)
    prototype = next(row for row in source["missions"] if row["id"] == "scale_000")
    for n in range(1, resource_count):
        row = deepcopy(prototype)
        row["id"] = "scale_%03d" % n
        row["name"] = "Performance %03d" % n
        source["missions"].append(row)
    content = Content.from_dict(source, rules=authored_rules_for_document(source))
    project_data = GameProject.default(content).to_dict()
    for n in range(max(0, resource_count // 4)):
        project_data["campaigns"].append({
            "id": "scale_campaign_%03d" % n, "name": "Campaign %03d" % n,
            "description": "", "start_mission": "scale_%03d" % n,
        })
    project = GameProject.from_dict(project_data, content)
    return content, project


def make_event_graph(event_count):
    from sporebound.authoring import add_event
    from sporebound.model import Content
    core = Content.load(CONTENT_DIR / "core.json")
    raw = core.to_dict()
    mid = raw["missions"][0]["id"]
    authored = add_event(raw, mid, "scale_trigger_000", condition="tick",
                         action="message", pos=(1, 1), tick=1,
                         text="Profilage événementiel")
    mission = next(m for m in authored["missions"] if m["id"] == mid)
    template = deepcopy(mission["triggers"][-1])
    mission["triggers"] = []
    for n in range(event_count):
        trigger = deepcopy(template)
        trigger["id"] = "scale_trigger_%03d" % n
        mission["triggers"].append(trigger)
    return authored, mid


def make_story_graph(scene_count):
    """Broad branching graph exercises the existing bounded tree layout."""
    scenes = []
    for i in range(scene_count):
        choices = []
        for j in (2 * i + 1, 2 * i + 2):
            if j < scene_count:
                choices.append({
                    "id": "to_%03d" % j, "label": "Continuer %d" % j,
                    "next_scene": "scale_scene_%03d" % j,
                })
        scenes.append({
            "id": "scale_scene_%03d" % i,
            "title": "Scène %d" % i,
            "choices": choices,
        })
    return {"scenes": scenes}, "scale_scene_000"


def measure_headless(*, samples, resources, events, short_saves, long_saves):
    from sporebound.event_graph import build_event_graph
    from sporebound.game_project import GameProject
    from sporebound.model import Content
    from sporebound.story_graph import build_story_tree
    from sporebound.studio_index4 import StudioIndex
    from sporebound.studio_transaction import StudioHistory, StudioTransactionStore

    content, project = make_workspace(resources)
    content_dict = content.to_dict()
    project_dict = project.to_dict()
    source_digest = sha256(json.dumps(
        [content_dict, project_dict], sort_keys=True, default=str).encode()).hexdigest()

    def workspace_index():
        index = StudioIndex(content, project)
        assert len(index.nodes) >= resources
        index.search("performance")
        return index

    workspace = measure("studio_index_search", workspace_index, samples)
    workspace["nodes"] = len(workspace_index().nodes)
    workspace["resources_requested"] = resources

    def validate():
        parsed = Content.from_dict(content_dict)
        manifest = GameProject.from_dict(project_dict, parsed)
        assert len(parsed.missions) == len(content.missions)
        return manifest

    validation = measure("validate_content_and_project", validate, samples)

    event_data, mid = make_event_graph(events)
    event_digest = sha256(json.dumps(
        event_data, sort_keys=True, default=str).encode()).hexdigest()

    def tactical_graph():
        graph = build_event_graph(event_data, mid, max_events=1000, max_nodes=3000)
        assert graph["drawn_events"] == events and not graph["truncated"]
        return graph

    event_probe = measure("tactical_event_graph_layout", tactical_graph, samples)
    event_probe["nodes"] = len(tactical_graph()["nodes"])
    event_probe["events"] = events

    story, root = make_story_graph(events)

    def story_graph():
        graph = build_story_tree(story, root, max_depth=64, max_nodes=2000)
        assert len(graph["nodes"]) == events and not graph["truncated"]
        return graph

    narrative_probe = measure("narrative_graph_layout", story_graph, samples)
    narrative_probe["nodes"] = len(story_graph()["nodes"])

    core = Content.load(CONTENT_DIR / "core.json")
    save_content = core.to_dict()
    save_project = GameProject.default(core).to_dict()

    def session(steps):
        with TemporaryDirectory(prefix="drawtemp-perf-") as tmp:
            store = StudioTransactionStore(Path(tmp) / "session.json")
            history = StudioHistory(save_content, save_project, limit=min(steps + 1, 500))
            store.save(save_content, save_project)
            for n in range(steps):
                changed = dict(save_project)
                changed["title"] = "Studio profiling session %03d" % n
                assert history.record(save_content, changed)
                store.save(save_content, changed,
                           expected_previous=store.revisions())
            assert history.can_undo
            history.undo()
            history.redo()
            assert not store.pending
            assert all(p.is_file() for p in store.paths)

    short = measure("save_short_session", lambda: session(short_saves), samples)
    long = measure("save_long_session", lambda: session(long_saves), samples)
    short["save_operations_per_session"] = short_saves + 1
    long["save_operations_per_session"] = long_saves + 1

    final_digest = sha256(json.dumps(
        [content.to_dict(), project.to_dict()], sort_keys=True, default=str).encode()).hexdigest()
    assert source_digest == final_digest, "Profiling mutated source documents"
    assert event_digest == sha256(json.dumps(
        event_data, sort_keys=True, default=str).encode()).hexdigest()
    return [workspace, validation, event_probe, narrative_probe, short, long]


def benchmark_script(name, arguments):
    command = [sys.executable, str(ROOT / "scripts" / name), *arguments]
    execution = subprocess.run(command, capture_output=True, text=True, cwd=ROOT,
                               check=False)
    if execution.returncode:
        raise RuntimeError(
            "Benchmark failed: %s\n%s\n%s" %
            (" ".join(command), execution.stdout[-4000:], execution.stderr[-4000:]))
    return execution.stdout


def measure_gui(*, sizes, cells, frames, assets):
    editor = []
    player = []
    with TemporaryDirectory(prefix="drawtemp-gui-perf-") as tmp:
        for size in sizes:
            for cell in cells:
                output = Path(tmp) / ("editor_%s_%s.json" % (size, cell))
                benchmark_script("benchmark_editor_render_3718d.py", [
                    "--sizes", str(size), "--cell-size", str(cell),
                    "--frames", str(frames), "--output", str(output),
                    *(["--assets"] if assets else []),
                ])
                record = json.loads(output.read_text(encoding="utf-8"))["samples"][0]
                editor.append(record)
        for cell in cells:
            for actors in (0, 80):
                output = Path(tmp) / ("player_%s_%s.json" % (cell, actors))
                benchmark_script("benchmark_player_canvas_376.py", [
                    "--cell", str(cell), "--actors", str(actors),
                    "--frames", str(max(frames, 20)), "--output", str(output),
                ])
                player.append(json.loads(output.read_text(encoding="utf-8")))
    return {
        "editor": editor, "player": player,
        "interaction_scope": "Editor draw + Tk idle paint; Player draw + Tk event pump. "
                             "Neither measures physical input-to-photon latency.",
        "visual_parity": "Run the existing EditorRenderCache and Editor/Player visual fidelity GUI tests separately.",
    }


def git_head():
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, timeout=3)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("headless", "gui", "all"), default="all")
    parser.add_argument("--sizes", default="32,64,128")
    parser.add_argument("--cells", default="24,54,96")
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--resources", type=int, default=200)
    parser.add_argument("--events", type=int, default=160)
    parser.add_argument("--short-saves", type=int, default=5)
    parser.add_argument("--long-saves", type=int, default=60)
    parser.add_argument("--assets", action="store_true")
    parser.add_argument("--quick", action="store_true",
                        help="CI smoke: one map/zoom and smaller headless scenes")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        sizes = [int(s) for s in args.sizes.split(",")]
        cells = [int(s) for s in args.cells.split(",")]
    except ValueError:
        parser.error("Sizes/cells must be comma-separated integers")
    if not sizes or any(s not in (32, 64, 128) for s in sizes):
        parser.error("Map sizes must be drawn from 32,64,128")
    if not cells or any(c not in (24, 54, 96) for c in cells):
        parser.error("Cell sizes must be drawn from 24,54,96")
    if not 2 <= args.frames <= 100 or not 2 <= args.samples <= 1000:
        parser.error("Frames: 2..100; samples: 2..1000")
    if not 2 <= args.resources <= 500 or not 2 <= args.events <= 1000:
        parser.error("Resources: 2..500; events: 2..1000")
    if not 2 <= args.short_saves <= 499 or not 2 <= args.long_saves <= 499:
        parser.error("Session length: 2..499 saves")
    if args.quick:
        sizes, cells = [32], [24]
        args.frames, args.samples = min(args.frames, 5), min(args.samples, 5)
        args.resources, args.events = 24, 20
        args.short_saves, args.long_saves = 2, 5
    report = {
        "schema": "drawtemp-performance-scale-v1",
        "source_sha": git_head(),
        "environment": {
            "platform": platform.platform(), "python": platform.python_version(),
            "python_executable": sys.executable, "architecture": platform.machine(),
            "logical_cpus": os.cpu_count(), "tk_patchlevel": None,
            "hash_seed": os.environ.get("PYTHONHASHSEED", "random"),
        },
        "parameters": {
            "phase": args.phase, "sizes": sizes, "cells": cells,
            "frames": args.frames, "samples": args.samples,
            "resources": args.resources, "events": args.events,
            "short_saves": args.short_saves, "long_saves": args.long_saves,
            "assets": args.assets, "quick": args.quick,
        },
        "measurement_policy": {
            "no_fixed_thresholds": True,
            "p99_warning": "Use >=100 samples/frames for meaningful tail metrics.",
            "warmup": "One unmeasured headless iteration; GUI tools provide their own warmups.",
            "scope": "No hardware input-to-photon timing, OS-native heap breakdown or memory leak attribution.",
        },
    }
    if args.phase in ("headless", "all"):
        report["headless"] = measure_headless(
            samples=args.samples, resources=args.resources, events=args.events,
            short_saves=args.short_saves, long_saves=args.long_saves)
    if args.phase in ("gui", "all"):
        import tkinter
        report["environment"]["tk_patchlevel"] = tkinter.TkVersion
        report["gui"] = measure_gui(
            sizes=sizes, cells=cells, frames=args.frames, assets=args.assets)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print("Profiling report:", args.output)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

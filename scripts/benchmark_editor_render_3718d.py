"""Compare full and retained Studio ISO drawing on real Tk (not Player frames).

Run under Xvfb on Linux. Timings include Tk idle painting, exclude model parsing
(reported separately) and document commands. Python memory is sampled separately
so tracemalloc does not distort the timing comparison. No universal time budget.
"""
import argparse
import json
import platform
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.editor import Document
from sporebound.editor_render_cache import EditorRenderCache
from sporebound.iso_map import render_isometric, IsoTerrainAtlas
from sporebound.iso_props import IsoPropAtlas
from sporebound.iso_building_atlas import IsoBuildingAtlas
from sporebound.iso_fortification_atlas import IsoFortificationAtlas
from sporebound.iso_actor_atlas import IsoActorAtlas
from sporebound.model import Content
from examples.fortified_village_3717a import build_village_document, MISSION_ID


def summary(values):
    ordered = sorted(values)
    return dict(p50_ms=round(median(values), 3),
                p95_ms=round(ordered[min(len(ordered)-1, int(len(ordered)*.95))], 3))


def measure(size, frames, assets):
    import tkinter as tk
    source = Content.load(DEFAULT_CONTENT)
    if size == 'village':
        doc = build_village_document(source)
        mid = MISSION_ID
    else:
        mid = 'editor_benchmark'
        doc = Document(Content.from_dict(add_blank_mission(
            source.to_dict(), mid, 'Studio benchmark', int(size), int(size))))
        occupied = {tuple(u['pos']) for m in doc.data['missions']
                    if m['id'] == mid for u in m['units']}
        # Dense, varied authoring content exercises adjacency and relief.
        doc.paint_many(mid, [(x, y) for x in range(int(size))
                            for y in range(int(size)) if x % 9 == 0 and (x, y) not in occupied], 'surface:water')
        doc.paint_many(mid, [(x, y) for x in range(int(size))
                            for y in range(int(size)) if y % 13 == 0], 'height+')
    baseline = json.loads(json.dumps(doc.data))
    result = {'map': size, 'samples_per_operation': frames, 'assets': assets, 'modes': {}}
    for mode in ('full', 'retained'):
        root = tk.Tk()
        try:
            root.geometry('900x650')
            canvas = tk.Canvas(root)
            canvas.pack(fill='both', expand=True)
            root.update()
            renderer = EditorRenderCache(canvas)
            options = dict(cell_size=32, layers={}, selected_cell=(0, 0), selected_tiles=set())
            if assets:
                options.update(atlas=IsoTerrainAtlas(canvas), prop_atlas=IsoPropAtlas(canvas),
                               building_atlas=IsoBuildingAtlas(canvas),
                               fortification_atlas=IsoFortificationAtlas(canvas),
                               actor_atlas=IsoActorAtlas(canvas))
            doc = Document(Content.from_dict(baseline))
            parse_times = []

            def draw():
                start = perf_counter()
                mission = Content.from_dict(doc.data).missions[mid]
                parse_times.append((perf_counter()-start)*1000)
                start = perf_counter()
                if mode == 'retained':
                    renderer.draw(mission.board, mission, mission.units, **options)
                else:
                    render_isometric(canvas, mission.board, mission, mission.units, **options)
                root.update_idletasks()
                return (perf_counter()-start)*1000

            cold = draw()
            timings = {}
            for operation in ('noop', 'selection', 'paint', 'height', 'zoom', 'undo_redo', 'mass_selection'):
                values, changes = [], []
                for i in range(frames):
                    if operation == 'selection':
                        options['selected_cell'] = (i % 8, 2)
                    elif operation == 'paint':
                        doc.paint_many(mid, [(10, 10)], 'surface:' + ('water' if i % 2 else 'grass'))
                    elif operation == 'height':
                        doc.paint_many(mid, [(10, 10)], 'height+' if i % 2 == 0 else 'height-')
                    elif operation == 'zoom':
                        options['cell_size'] = 32 if i % 2 else 38
                    elif operation == 'undo_redo':
                        (doc.undo if i % 2 == 0 else doc.redo)()
                    elif operation == 'mass_selection':
                        options['selected_tiles'] = {(x, y) for x in range(20) for y in range(20)} if i % 2 else set()
                    values.append(draw())
                    if mode == 'retained':
                        changes.append(dict(renderer.stats))
                timings[operation] = summary(values)
                if changes:
                    timings[operation]['cache_mode'] = changes[-1]['mode']
                    timings[operation]['max_created_items'] = max((c['created'] for c in changes if c['created'] is not None), default=None)
                    timings[operation]['max_updated_items'] = max(c['updated'] for c in changes)
                    fast_paths = {}
                    for sample in changes:
                        key = sample.get('fast_path', 'retained')
                        fast_paths[key] = fast_paths.get(key, 0) + 1
                    timings[operation]['fast_paths'] = fast_paths
                    timings[operation]['fast_path_frames'] = {
                        name: sum(c.get('fast_path') == name for c in changes)
                        for name in ('unchanged', 'selection', 'full')
                    }
            # Retained Python memory, not Tcl image memory or process RSS.
            renderer.invalidate()
            tracemalloc.start()
            draw()
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            result['modes'][mode] = dict(cold_ms=round(cold, 3), operations=timings,
                                       model_parse=summary(parse_times),
                                       python_current_bytes=current, python_peak_bytes=peak,
                                       canvas_items=len(canvas.find_all()))
        finally:
            root.destroy()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', default='village,32,64,128')
    parser.add_argument('--frames', type=int, default=20)
    parser.add_argument('--assets', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    sizes = args.sizes.split(',')
    if not 2 <= args.frames <= 100 or any(s not in ('village', '32', '64', '128') for s in sizes):
        parser.error('frames: 2..100; sizes: village,32,64,128')
    report = dict(python=sys.version, platform=platform.platform(), samples=[])
    for size in sizes:
        sample = measure(size, args.frames, args.assets)
        report['samples'].append(sample)
        print(json.dumps(sample), flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

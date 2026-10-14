#!/usr/bin/env python3
"""Paired full-vs-dirty Canvas repaints for one validated terrain cell.

Both paths use the canonical Content model and identical Tk Canvas rendering.
Authoring edits are applied before timing; time covers projection lookup,
renderer.draw and Tk idle painting. CI --quick is not a p99 certification.
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
from sporebound.model import Content


def measure(size, zoom, samples):
    import tkinter as tk

    raw = add_blank_mission(Content.load(DEFAULT_CONTENT).to_dict(),
                            'dirty_map', 'Carte', size, size)
    result = {'size': size, 'zoom': zoom, 'samples': samples}
    for mode in ('full', 'dirty'):
        doc = Document(Content.from_dict(raw))
        projection = EditorContentProjection()
        root = tk.Tk()
        try:
            root.geometry('900x640')
            canvas = tk.Canvas(root)
            canvas.pack()
            root.update()
            renderer = EditorRenderCache(canvas)
            options = {
                'cell_size': zoom, 'layers': {},
                'selected_cell': None, 'selected_tiles': (),
            }
            mission = projection.get(doc.data).missions['dirty_map']
            renderer.draw(mission.board, mission, mission.units,
                          scene_revision=(projection.generation, mission.id),
                          **options)
            values, paths, dirty_count = [], [], []
            for i in range(samples):
                doc.paint_many('dirty_map', [(10, 10)],
                               'surface:water' if i % 2 == 0
                               else 'surface:grass')
                if mode == 'full':
                    renderer.invalidate()
                started = perf_counter()
                model = projection.get(doc.data).missions['dirty_map']
                renderer.draw(model.board, model, model.units,
                              scene_revision=(projection.generation, model.id),
                              **options)
                root.update_idletasks()
                values.append((perf_counter()-started)*1000)
                paths.append(renderer.stats.get('fast_path'))
                dirty_count.append(renderer.stats.get('affected_cells', 0))
            if mode == 'dirty':
                assert set(paths) == {'dirty_tiles'}, (
                    'Incremental painter unexpectedly fell back: %s' % paths)
                assert max(dirty_count) <= 9
            result[mode] = {
                **percentiles(values),
                'canvas_items': len(canvas.find_all()),
                'fast_paths': {key: paths.count(key) for key in set(paths)},
                'max_affected_cells': max(dirty_count),
            }
        finally:
            root.destroy()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', default='65,128')
    parser.add_argument('--zooms', default='24,54,96')
    parser.add_argument('--samples', type=int, default=100)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.quick:
        args.sizes, args.zooms, args.samples = '65,128', '54', 3
    sizes = [int(x) for x in args.sizes.split(',')]
    zooms = [int(x) for x in args.zooms.split(',')]
    if (any(n not in (65, 128) for n in sizes) or
            any(n not in (24, 54, 96) for n in zooms) or
            not 2 <= args.samples <= 1000):
        parser.error('Sizes 65/128, zooms 24/54/96, samples 2..1000')
    report = {
        'schema': 'drawtemp-dirty-tiles-3732e-v1',
        'platform': platform.platform(),
        'python': platform.python_version(),
        'notes': 'Identical one-cell authoring edits; Tk idle rendering, not '
                 'physical input-to-photon. Under 100 samples p99 is exploratory.',
        'cases': [measure(size, zoom, args.samples) for size in sizes
                  for zoom in zooms],
    }
    output = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding='utf-8')
        print('Saved:', args.output)
    else:
        print(output, end='')
    for row in report['cases']:
        print('%d² %dpx: full p95=%.3fms dirty p95=%.3fms' %
              (row['size'], row['zoom'], row['full']['p95_ms'],
               row['dirty']['p95_ms']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

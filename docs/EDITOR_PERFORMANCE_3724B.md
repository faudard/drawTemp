# 3.7.24B — Large-scene Studio rendering fast paths

## Scope

Keep the existing `EditorRenderCache` retained-command path on maps up to
4,096 cells. On larger maps, continue to use the geometry-only path (the full
command-list diff previously cost roughly 24 MiB Python at 128²), but avoid
issuing a full set of Tk drawing commands on every refresh.

- **Unchanged scene and UI state:** skip the Canvas redraw entirely.
- **Selection-only update:** delete/recreate only `selection` polygons, in
  painter order, then raise them above roofs as the canonical renderer does.
- **Any other change:** run `render_isometric` normally, including terrain,
  height, actors, architecture, layers, atlas identity, tactical overlays,
  animations, zoom and cutaway-affecting selection inputs.

To be safe with existing Studio panels that mutate authoring data in place,
we snapshot the typed board, mission, units and non-selection rendering options.
Tk-backed atlas objects are compared by identity, never copied. The snapshot
is kept **only for large maps**, cleared on invalidation and when switching
to retained mode. No document revision counter, save schema or gameplay code
is added.

The optimized selection outline uses the same polygon geometry, colors,
line widths and tag as `render_isometric`. The global geometry and hit-test
buckets continue to cover the entire board.

## Tests and profiling

The existing real-Tk parity suite is extended with large-scene cases
(forced on Valcroix for low-cost CI). Every step compares Canvas item
types, coordinates, options, painter order and scroll region against the
canonical full renderer. Scenarios cover an unchanged refresh, selection,
multi-selection, in-place actor mutation, terrain painting, layer changes,
zoom, invalidation and switching cache modes.

```sh
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_editor_render_cache_3718d_gui -v

xvfb-run -a python scripts/benchmark_editor_render_3718d.py \
  --sizes village,32,64,128 --frames 20 \
  --output /tmp/studio-performance-3724b.json
```

The benchmark now reports `fast_path_frames` for each operation. Compare
full versus retained/no-op/selection p50 and p95 at 32², 64², 128² and
Valcroix; preserve generated JSON with the specific tested commit SHA.
Timing excludes model parsing and whole-Studio UI refresh; do not extrapolate
to click-to-screen latency or native Tcl/RSS memory.

## Gate and boundaries

- Identical Canvas visual output, selection and picking versus the full
  renderer for all test states, and no changes to Content, Battle or replay.
- Confirm the no-op and selection shortcuts activate in the 128² run.
- Do not claim an FPS, millisecond or memory budget before CI and reference
  hardware measurements have been reviewed.
- Viewport culling, per-cell dirty regions, model refresh reduction and native
  Tcl/RSS profiling remain separate follow-up tasks.

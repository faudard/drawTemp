# 3.7.24B1 — Fast paths on large Studio maps

## Scope and measured baseline

The 3.7.18D profiling report records the following **existing** no-change
refresh values on Linux/Python 3.12/Tk/Xvfb (p95, milliseconds):

| Scene | Previous full draw | 3.7.18D cache |
| --- | ---: | ---: |
| 32 × 32 | 23.7 | 19.2 |
| 64 × 64 | 93.2 | 72.9 |
| 128 × 128 | 327.6 | 311.9 |

The 128² scene has 16,384 cells. The retained Canvas command diff was
intentionally disabled beyond 4,096 cells because it used too much memory and
regressed drawing. **Do not re-enable the full-scene command cache** without
new memory and latency evidence.

## This increment

`EditorRenderCache` keeps the previous large-scene Canvas drawing and checks
a value-based signature of the tactical board, mission, actor state, visible
layers, asset loaders, animation poses and overlays other than selection.
The signature is computed from values, never from model object identities,
because the Studio rebuilds `Content` on refresh and some panels may edit
mission dictionaries in place.

- **noop**: if the scene and both selection overlays have not changed, no
  Canvas repaint occurs.
- **selection**: if only selected cells differ, redraw just the selection
  contours. This preserves the normal painter ordering (`selection` above
  actors and roofs).
- **full**: terrain/relief, actors, objects, assets, zoom, layers, danger,
  and any change to a building's cutaway state still use the established
  full renderer. The exact architecture instances from the last painted
  frame are available to detect cutaway transitions.
- External Canvas overlays changing the item count also force a full pass.
  The cache remains single-frame and bounded: no retained command display
  list is built for large maps, and the signature is a 16-byte digest.

This change **does not** alter `Content`, `Battle`, tactical CT/AI,
pathfinding, JSON, saves or replays. Small scenes keep the 3.7.18D retained
path. This is an incremental update optimization, not yet viewport culling
or dirty-region rasterization.

## Reproduction and parity

Run on a machine with Tk/Xvfb:

```sh
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_editor_render_cache_3718d_gui -v
xvfb-run -a python3 scripts/benchmark_editor_render_3718d.py \
  --sizes 32,64,128,village --frames 20 \
  --output studio-render-3724b.json
xvfb-run -a python3 scripts/benchmark_editor_render_3718d.py \
  --sizes village,128 --assets --frames 20 \
  --output studio-render-3724b-assets.json
```

The benchmark now records `fast_paths` counts for each operation as well
as p50/p95, Canvas item counts, parse timings and Python memory metrics.
The GUI tests compare item types, coordinates, options and painter order
against the original full renderer. They cover unchanged redraws,
selection and multi-selection, edited actors and tiles, externally inserted
Canvas items, and selected cells crossing a roof cutaway boundary.

**Acceptance gate:** verify that 128² static refresh uses `noop`,
selection-only changes outside cutaway use `selection`, and all
other invalidations match the full-render output. Save the benchmark JSON
for the exact PR SHA. Do not claim a measured speedup until the CI run
provides data from the same machine and parameters; no baseline timing
is hard-coded as an assertion in CI.

## Known limitations / next increment

- A full paint, height edit, zoom or changed actor/object still creates
  a whole-frame draw on large maps; 128² is not yet a fluid painting target.
- Creating a value signature still traverses scene state (but avoids the
  full 16k Canvas drawing on eligible refreshes).
- The large-map branch checks Canvas item count, not arbitrary external
  in-place canvas mutations. Code that takes control of the canvas must call
  `invalidate()` as the flat renderer already does.
- GUI validation on Linux/Tk/Xvfb is automated. Windows/macOS GUI
  captures and manual parity checks are still required for release.
- Next candidate: viewport-based culling with scroll/resize invalidation
  and a stable architecture/actor margin. It requires explicit camera
  lifecycle tests; simply hiding distant cells without scroll redraw
  would be an incorrect optimization.

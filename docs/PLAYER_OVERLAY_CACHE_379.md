# 3.7.9 — Tactical overlay cache

## Motivation

The terrain (3.7.7) and unit items (3.7.8) already persist across idle
animation frames, but the Tk renderer still destroyed and recreated reachable
cells, warnings, selected-cell outlines, objective markers and victory labels
on *every* motion tick.

## Rendering and invalidation contract

- `CanvasRenderer._overlay_key` identifies the rendered tactical overlay.
  It includes mission, map dimensions, camera, viewport dimensions, selected
  cell, reachable cells, **effective danger kind per cell**, objects (including
  open/closed state) and the result label.
- Danger priority is unchanged: hazard < charge < prepared < cast. A lower
  priority warning newly overlaid by an existing stronger threat need not
  repaint. The cache never governs prediction or combat rules.
- As long as the key is identical, Tk retains the same `dynamic` item IDs
  and skips both the visible tile traversal and Canvas item construction.
- An authoritative selection/reachability/threat/object/result change triggers
  an immediate overlay repaint, without invalidating terrain or actor caches.
- Terrain changes, pan/zoom, viewport resize or `draw(None)` invalidate the
  overlay so it never displays stale positions or objects.
- Cached `actor` items are raised above the threats; the result banner has
  its own `result` tag and remains above actors even on later cached draws.
- This changes only UI state; battle digest, AI, RNG, replay and saves remain
  strictly untouched.

## Validation

```bash
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_player_canvas_377_gui \
  tests_standalone.test_player_actors_378_gui \
  tests_standalone.test_player_overlays_379_gui -v

xvfb-run -a python3 scripts/benchmark_player_canvas_376.py \
  --actors 80 --cell 52 --frames 120 --output overlays.json
```

CI stores the real Linux/Xvfb measurement in the
`player-canvas-379-ubuntu` artifact, including
`overlay_rebuilds` and p50/p95/max. On a completely static tactical
projection, one overlay rebuild across 120 samples is expected.

### Acceptance gates

- Threat priority, colors and selected/reachable cells remain live after
  combat changes; existing 3.7.7/3.7.8 tests keep passing.
- Mission, camera, viewport, object open/closed and end-of-battle result
  invalidations are exercised in actual Tk.
- 10 GUI/editor/rules jobs + distribution are green across Windows, Linux,
  macOS and Python 3.10/3.12/3.14.
- Compare 80-actor p95 to 3.7.8 (~2.78ms on its earlier Linux/Xvfb run) but
  avoid assuming identical machine conditions or production GPU frame times.

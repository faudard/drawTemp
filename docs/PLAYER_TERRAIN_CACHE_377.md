# 3.7.7 — Cached Player terrain, live tactical overlays

## Objective

The 3.7.6 benchmark timed the **real** Tk canvas and measured its
full redraw cost even for idle sprite animation. Keep static terrain items
alive across unchanged frames; only redraw foreground tactical information.

## Renderer contract

- `CanvasRenderer.draw(frame, camera)` now owns two Canvas tag layers:
  `terrain` (tiles, elevation, cover) and `dynamic` (reachable positions,
  selected cell, tactical telegraphs, objectives, sprites, health, result).
- Reuse terrain only when **all** of the scene width/height, immutable tile
  projections, camera zoom/pan and viewport dimensions match the prior draw.
- Every frame updates the dynamic layer from `BattleFrame`: movement, HP,
  charges, cast threats and selection **must not** be cached.
- A new mission with identical terrain is safe to reuse; it is the tile
  values, not a filename, that determine the backdrop. If any tile changes
  (doors, obstacles, hazards, elevation), invalidate the background.
- `draw(None)` clears both layers and invalidates the terrain key. Destroying
  a renderer releases its sprite caches and terrain key.
- `_terrain_rebuilds` is renderer-local diagnostic instrumentation, not
  gameplay state. Nothing is added to save files or replay digests.

## Acceptance and diagnostics

```sh
python -m unittest tests_standalone.test_renderer_audio -v

SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_player_canvas_376_gui \
  tests_standalone.test_player_canvas_377_gui -v

# Same real authored Jeanne battle and stress projection used in 3.7.6.
xvfb-run -a python scripts/benchmark_player_canvas_376.py \
  --actors 0 --cell 52 --frames 120 --output authored.json
xvfb-run -a python scripts/benchmark_player_canvas_376.py \
  --actors 80 --cell 52 --frames 120 --output stress.json
```

The benchmark reports `terrain_rebuilds`, `terrain_items`,
`dynamic_items`, p50/p95/max, memory from `tracemalloc`, and authoritative
Battle purity. The CI artifact `player-canvas-377-ubuntu` stores actual
authored and stress measurements.

## Gate before merge

- All GUI tests pass under Xvfb; repeated frames retain identical terrain
  item IDs, while dynamic items and warnings change correctly.
- Zoom/pan, Tk viewport resize and tile mutations rebuild terrain.
- Existing 3.7.6 pixel-art scaling, sprite cache and authoring tests remain green.
- Python 3.10/3.12/3.14, Windows/Linux/macOS gameplay and distribution green.
- Compare the measured 80-actor 52px p95 with 3.7.6's unlayered benchmark,
  but do **not** infer real GPU frame latency from Xvfb numbers.

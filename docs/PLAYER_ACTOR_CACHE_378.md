# 3.7.8 — Incremental Actor Rendering

## Why

The 3.7.7 cache retains the terrain, but every motion timer still deleted
and recreated 4–5 Tk Canvas objects per actor (sprite or vector fallback,
selection outline and two health-bar rectangles). This is particularly wasteful
for static units during idle animation of Jeanne.

## Contract

- `CanvasRenderer._actor_items` tracks UI-only Canvas IDs per visible actor.
  Actors and game state remain the immutable read-only `BattleFrame` inputs.
- At creation, allocate one active-state border, either one sprite image or
  an oval and name, and a background/foreground HP bar.
- If an actor's **render signature** (position, camera geometry, action,
  resolved sprite frame, team, name, HP, alive, active state) is unchanged,
  perform no Canvas configure/coordinate operation.
- On movement, directional animation, hit/defeat, health reduction, zoom or
  active-unit change, update those Canvas items **in place**, retaining IDs.
- Replace an actor group only if switching between sprite and vector fallback.
- Prune out-of-view actors and actors missing in the new frame. Clear all
  caches on a new background or `draw(None)`.
- Actor items use the `actor` Canvas tag; dynamic tactical overlays retain
  their `dynamic` tag and are rebuilt from authoritative data on every frame.
  The actor group stays above the threats but below the result banner.
- All caches are renderer-local, not saved or replayed.

## How to verify

```sh
python -m unittest tests_standalone.test_renderer_audio \
  tests_standalone.test_player_canvas_376 \
  tests_standalone.test_player_canvas_377_gui -v

SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_player_canvas_376_gui \
  tests_standalone.test_player_canvas_377_gui \
  tests_standalone.test_player_actors_378_gui -v

xvfb-run -a python scripts/benchmark_player_canvas_376.py \
  --actors 0 --cell 52 --frames 120 --output authored.json
xvfb-run -a python scripts/benchmark_player_canvas_376.py \
  --actors 80 --cell 52 --frames 120 --output stress.json
```

The CI artifact `player-canvas-378-ubuntu` records p50/p95/max, the
number of actor Canvas items, retained actor count, initial item creations
and subsequent coordinate/configuration updates, in addition to terrain metrics.

## Gates

- Verify item identity stays stable across repeated idle frames.
- Verify camera movement, interpolation, health-bar length and actor state
  update real Tk items without creating duplicate actors.
- Verify viewport eviction, actor deletion and sprite→vector fallback cleanup.
- Verify threat overlays refresh independently of actor caching and that
  result banners remain visually on top.
- Verify original gameplay unit digest and save/replay semantics stay unchanged.
- Pass full CI on Windows, Linux and macOS; compare 80-actor p95 with 3.7.7.
  Xvfb timings are benchmark scope only, not GPU frame-time guarantees.

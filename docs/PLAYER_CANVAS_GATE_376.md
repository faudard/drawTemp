# 3.7.6 — Player Canvas Quality & Performance Gate

## Scope

The 3.7.5 renderer matrix timed sprite blits. This milestone measures the
**actual Tk tactical CanvasRenderer** with Jeanne's authored terrain, sprites,
health bars, reachable cells, telegraphs and camera transforms.

## Runtime

- Fit tactical sprites to the camera's 16–128 px cells using native Tk
  nearest-neighbour PhotoImage operations. The standard 52 px cell no longer
  overflows with a 64 px Jeanne sprite.
- Cache scaled sprites per image and zoom level; never rescale on every
  idle-animation tick. Preserve original atlas and dialogue portrait sizes.
- Do not paint entirely offscreen terrain, objects or actors. Bypass culling
  while Tk reports unmapped 1×1 geometry so initial first frames are not empty.
- Leave tactical AI, combat rules, RNG, replay and save formats unchanged.

## How to reproduce

```sh
python -m unittest tests_standalone.test_player_canvas_376 -v

# Linux with Xvfb, or run the same test directly with a desktop display:
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_player_canvas_376_gui -v

# Actual authored battle (0 = use authored unit count):
xvfb-run -a python scripts/benchmark_player_canvas_376.py \
  --actors 0 --cell 52 --frames 120

# Extra presentation-only actors: stress the complete Canvas:
xvfb-run -a python scripts/benchmark_player_canvas_376.py \
  --actors 80 --cell 104 --pan --frames 120
```

On Linux CI, the `player-canvas-376-ubuntu` artifact contains a real
80-actor, 52px-cell rendering sample with p50/p95/max wall time, Python
tracemalloc peak, live Canvas item count and decoded/scaled image cache sizes.

The added actors in the stress projection are **not tactical units** and are
not present in saves: the authoritative Battle digest must be unchanged.
The benchmark times draw, pose projection and Tk event handling but does not
time combat AI, sound, dialogue UI, GPU display latency or file I/O.

## Gate

- Tk screenshot / visual smoke: sprites readable at 16, 52, 64, 104, 128 px
- Full-screen and panned camera: no missing initial paint, no excess Canvas items
- Directional animation and atlas caches: no repeated source PNG decoding
- Same Battle digest before and after stress rendering
- CI editor/rules on Python 3.10, 3.12, 3.14 and 3 operating systems
- Record the p95 and review repeated results before renderer migration

**Decision:** Retain Tk for Jeanne's current Player; do not infer Qt or
pygame superiority from the unrelated sprite-only benchmark.

# R36.C1 — Real R28 sprite atlas display and bounded CPU profiling

**Implementation:** [PR #375](https://github.com/faudard/drawTemp/pull/375).
**Status:** code proposed, **not** GPU certified or approved for release.

## Shared R4/R3 image pipeline

The optional R36 action Player uses the **existing** `PresentationAssets`
and `AssetResolver` from DrawTemp R4, not a new image/atlas cache or
second authoring manifest.

When the R26 simulation commits a tick, R36 resolves the actor's visual
state to its existing `GameProject.assets` animation/sprite ID. R3 scene
projection carries the ID to the shared renderer. The
`R36PresentationAssets` decorator resolves a real PNG file relative to
the **GameProject manifest directory** and exposes the same atlas crop,
pivot and provenance revision fields as R4.

The path resolver rejects traversal/symlink escapes, bad image signatures,
CRC/PNG chunk corruption, frames beyond atlas dimensions, and oversized
PNGs via existing R4 validators. The cache stores at most **256 resolved
frames**, keyed by R28 ID; a file size/mtime change invalidates that entry.

The **same** `sourceClipRect` contract used by `IsoViewport.qml` is used
by `TopDownViewport.qml`. Only actors bound to validated art create an
Image QML delegate (not one per terrain tile); the previous silhouette is
kept if the file is missing, corrupt or fails Qt decoding. Static pose
labels stay visible in either case.

This supports actual registered PNGs, including atlas regions and R4
pivot annotations. It does **not** yet produce directional animation
or equipment attachment automatically: those remain R36.4/C gates.

## Running the optional Player

```bash
python -m drawtemp.player.action_app \
  --content /path/to/content.json \
  --animation-project /path/to/content.game.json \
  --hero-controller hero_animation
```

For the sprite IDs referenced by the chosen controller, the PNG files
must be present at their registered R28 paths relative to the project
manifest (for example `art/s_idle.png`). Existing `.drawtemp/
r4-annotations.json` provides validated optional pivot metadata.

An absent PNG produces a **visible silhouette fallback**, with an
`assetError` on that R3 render row; missing art is not silent proof
that a game has passed an export asset-license gate. If the art changes
on disk while a Qt viewport is open, reopening that view is recommended
to ensure Qt's own image cache has refreshed.

## Opt-in CPU profiling

```bash
python -m drawtemp.player.action_app --profile-r36 /tmp/r36-cpu.json
```

`--profile-r36` collects at most 600 recent scene-publish observations
from the **actual** `RendererController.replace_scene()` call, using a
monotonic CPU nanosecond clock. On exit, it writes a small JSON report:

- p50/p95/p99 and max **CPU render-submit milliseconds**, nearest-rank;
- maximum QML item, actor, visual particle, light and FX counts;
- 128 particles / 8 halos / 96 FX / 33 actors explicit presentation caps.

Repeated redraws can share one logical tick; a checkpoint rewind resets
the telemetry window. It never touches game commands or recordings.

**These measurements are CPU-side publication timings, not GPU render time,
draw calls, latency-to-photon, actual frame rates or hardware p95/p99.**
No performance figures are certified until runs have executed on target
hardware and goldens have passed review.

## Tests / gates

```bash
python -m unittest tests_standalone.test_r36_sprite_rendering -v
python -m unittest tests_standalone.test_r36_frame_budget -v
python -m unittest tests_standalone.test_drawtemp5_r4_assets -v
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m unittest tests_standalone.test_r36_action_actor_qt -v
```

The Qt smoke now creates actual small RGBA PNGs for the saved R36
project and verifies that CPU telemetry is produced, while the headless
tests check crop coordinates, pivots, resource validity, cache hits,
file mutations and legacy actor fallback.

**CI caveat:** the repository's Actions workflows have been failing
before producing jobs. Passing runtime tests are not yet established.

## Still open for R36.C certification

- Actual multi-direction / multi-equipment/attachment R36 sprite
  composition, atlas import/export provenance and licensing approvals.
- Studio and Player visual parity goldens at 1x/2x DPR.
- Hardware-backed Qt scenegraph render testing (OpenGL/RHI backends),
  GPU timing, 30/60/120 FPS performance/stress and p95/p99 budgets.
- Proper GPU particles/occlusion/shadow maps; cell shadows and
  concentric halos are still software-friendly approximations.
- Full R26/R32/tactical character and hitbox parity, accessibility
  review and release gate approval.

**Do not merge/label R36 certified based on the CPU profiler or offscreen
QML smoke alone.**

# R26.C — R3 shared top-down renderer and deterministic Player pacing

**Status: incremental implementation in a stacked draft PR; not R26/6.2
certification.** Based on #318 (R26.B), which depends on #300 (R26.A).
Cross-mode GameSession release gates also depend on #298 (R25.A) and
#314 (R25.B, SceneRouter). All remain subject to branch integration and CI.

## One scene projection contract for tactical and action

- `drawtemp.render.TopDownProjection` adds an orthogonal grid to existing
  `Camera`, `TileChunkIndex`, `render_items`, and `pick`. It handles
  **fractional tile positions** and exact world↔screen inversion.
- `scene_from_action(runtime)` converts one detached action snapshot into
  the same R3 `mission/width/height/revision/tiles/actors/objects`
  records used by Player and Studio. It preserves continuous positions,
  living/dead actors, combat states, doors and terrain blockers.
- `make_controller(..., projection_mode="top_down")` chooses the projection.
  Default remains `"isometric"` for all existing Player and Studio
  callers; the top-down projection deliberately disables the **isometric
  atlas tile batcher** instead of drawing diamond textures on square tiles.
- `render/TopDownViewport.qml` draws the R3 `renderer.items` rows and
  consumes `renderer.cameraState`. `ActionPreview.qml` no longer creates
  its own separate terrain, actors or object model. The renderer controller
  performs camera follow and picking.
- Default tactical projection and all tactical save/replay formats remain
  unchanged. The shared projection infrastructure is now ready for
  R25 project/profile-driven Studio/Player integration.

This is **one R3 renderer controller and record model** with two
projection-specific Qt Quick delegates, not a second world or independent
simulation. A later R3 refactor may share more QML delegates for common art.

## Logical 60 Hz independent of screen FPS

The old experimental QML `Timer(interval: 16)` ran one logical tick per
timer callback, which is *not* a fixed 60 Hz clock. R26.C replaces that
assumption with:

1. `ActionStepClock`: integer nanosecond accumulator with exact rational
   60 Hz cadence; max 6 catch-up ticks to bound UI stalls.
2. Qt's timer now **polls** keyboard input; `ActionBridge.pulse()` uses
   `time.monotonic_ns()` only to choose how many fixed logical `step()`
   calls to execute. Wall time is never included in action commands or
   replay state.
3. Edge-triggered dodge/interact commands are latched across polls that
   produce zero simulation ticks, and dispatched once on the next tick.
   Pause/resume, reloading and respawning discard stale time.
4. A single R3 renderer update is published after each poll with one or
   more committed ticks, with camera follow in the same update pass.

This prevents timer frequency from changing travel speed or attack cadence,
while bounding catch-up after a stall. It does **not** certify input latency
or constant frame delivery under real GPU load.

## Verify

```bash
python -m unittest tests_standalone.test_action_projection_r26c -v
python -m unittest tests_standalone.test_action_runtime_r26 -v
python -m unittest tests_standalone.test_action_player_r26b -v
python -m unittest tests_standalone.test_game_session -v
# With PySide6:
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  python -m drawtemp.player.qt_app --action-demo --smoke
python -m drawtemp.player.qt_app --action-demo
```

The headless tests compare identical 60-tick outcomes for 30, 60, 120,
144 and 240 UI polls/s and check R3 projection inversion, tile picking,
culling, detached scenes and historical isometric geometry. The Qt CI
smoke instantiates the real QML root; it is **not** an onscreen GPU/golden
certification.

## Not complete

R25 scene transitions inside the default Player, a unified persistent
GameSession mid-action state, Studio camera/picking workflows, onscreen
image parity, gamepad, motion/audio/VFX, and R29 multi-OS native packaging
remain future gates. Do not merge this as proof of R26 final release.

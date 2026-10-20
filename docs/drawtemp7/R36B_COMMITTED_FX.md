# R36.B1 — Committed action effects & bounded Qt fallback

**Status:** incremental code in PR #375, not R36.B/C certified. Depends on
R26 `ActionRuntime.step()` and shared R3 `TopDownViewport`.

## User-visible path

Run the opt-in R26 action Player preview:

```bash
python -m drawtemp.player.action_app
```

Once the Player accepts the attack/dodge/interaction input, R36.B1 draws a
short-lived burst over the affected actor at the *committed* tick. Effects:
attack slash, dodge dust, guard halo, collision-confirmed impacts, defeats,
and successful interaction sparks. The main gameplay uses unchanged
`ActionRuntime` and `scene_from_action()`. In the QML Player, press **M**
to toggle reduced flashes; this does not change the game recording.

No new VFX image assets are added; the first fallback uses bounded Qt Quick
primitive shapes, so there is no unverified artwork licensing in this lot.

## Contract and safety

- `CommittedFxDirector.observe(runtime.snapshot(), events)` is called
  **only after** `ActionRuntime.step` returned successfully. It uses the
  engine's authoritative tick/event log, never animation-controller marker
  timing to decide whether an attack hit.
- Coordinates follow the same fixed-point -> cell-centre projection as R3
  `scene_from_action`. The effect follows the actor's committed position,
  **not** the exact collider contact polygon. R32 gameplay hitbox/surface
  authoring and verification are future work.
- Cosmetic events are bounded to the first 32 logged entries per tick,
  at most 96 live bursts, with fixed expirations of 7–25 ticks. An excessive
  burst is deterministically truncated rather than aborting committed
  simulation. No RNG or independent wall-clock animation timer is used.
- `state()["fx"]` is a detached presentation projection. Save, load,
  GameSession and ActionRuntime recording schemas remain unchanged.
  Load/respawn clears cosmetic history and resynchronizes from the restored
  logical tick.
- A rejected cosmetic projection is **fail-soft**: the visual history is
  cleared, `state()["fx_warning"]` reports the cause and the already committed
  action/replay remains intact. This is tested by forced renderer failure.
- The default renderer is the shared R3 top-down Qt Quick viewport;
  overlay camera/zoom uses the same projection. It is a **software-capable
  fallback**, *not* proof of GPU particle acceleration or performance.
- Reduced flashes hides impact/spark flashes, while keeping quiet motion
  effects. No changes to game commands, hitboxes, replay or physics.

## Gates provided

- `tests_standalone.test_r36_committed_fx`: authoritative impact tick;
  pure redraw; snapshot isolation; replay identity; save/load/invalid load;
  deterministic streams; 32/96 bounds; monotonic tick errors.
- `tests_standalone.test_r36_committed_fx_qt`: Qt offscreen smoke for
  ActionPreview QML overlay. This is **not** a hardware GPU certification.
- `.github/workflows/r36-animation-controller.yml`: regression suite
  R12/R28/R26 on Linux/Windows/macOS and separate Qt smoke.

## What remains open

- **R36.2/R36.3**: authorable per-frame events, scrubbing, typed curves,
  animation/hitbox preview tied to actual R32 colliders.
- **R36.5/R36.6/R36.7**: configurable particle systems CPU/GPU, lighting,
  occlusion, weather/water/fog and per-projection feature flags.
- **R36.8**: identical action/tactical animation and exact
  hitbox-to-impact trace, not just cosmetic event timestamps.
- **R36.9–12**: real hardware p95/p99 metrics, GPU and multi-DPI visual
  goldens, provenance/licensing fail-closed and human visual/a11y signoff.

**Release rule:** R36 is **not** complete while these gates remain unverified.
